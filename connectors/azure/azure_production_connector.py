from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from azure.mgmt.costmanagement import CostManagementClient

from connectors.azure.azure_credential_manager import AzureCredentialManager
from connectors.azure.azure_resource_discovery import AzureResourceDiscovery


class AzureProductionConnector:
    def __init__(
        self,
        tenant_id: str | None = None,
        client_id: str | None = None,
        client_secret: str | None = None,
        subscription_id: str | None = None,
    ):
        self.credential_manager = AzureCredentialManager(tenant_id, client_id, client_secret, subscription_id)
        self.credential = self.credential_manager.credential()
        self.subscription_id = subscription_id

    def test_connection(self) -> dict[str, Any]:
        return self.credential_manager.test_connection()

    def sync_accounts(self) -> list[dict[str, Any]]:
        if not self.subscription_id:
            return []
        return [
            {
                "cloud": "azure",
                "account_id": self.subscription_id,
                "account_name": f"azure-{self.subscription_id}",
                "status": "ACTIVE",
                "region": "global",
            }
        ]

    def sync_costs(self, days: int = 30) -> list[dict[str, Any]]:
        subscription_id = self._effective_subscription_id()
        if not subscription_id:
            return []

        client = CostManagementClient(self.credential)
        end = date.today()
        start = end - timedelta(days=days)
        scope = f"/subscriptions/{subscription_id}"
        parameters = {
            "type": "Usage",
            "timeframe": "Custom",
            "time_period": {
                "from": start.isoformat(),
                "to": end.isoformat(),
            },
            "dataset": {
                "granularity": "Daily",
                "aggregation": {
                    "totalCost": {
                        "name": "PreTaxCost",
                        "function": "Sum",
                    }
                },
                "grouping": [
                    {
                        "type": "Dimension",
                        "name": "ServiceName",
                    }
                ],
            },
        }

        try:
            result = client.query.usage(scope, parameters)
        except Exception as exc:
            print("AZURE COST SYNC SKIPPED:", exc)
            return []

        columns = [column.name for column in result.columns or []]
        rows = []
        for item in result.rows or []:
            row = dict(zip(columns, item))
            service_name = row.get("ServiceName") or row.get("Service") or "Azure Service"
            usage_date = str(row.get("UsageDate") or row.get("Date") or start.isoformat())
            rows.append(
                    {
                        "cloud": "azure",
                        "account_name": subscription_id,
                        "service_name": service_name,
                        "region": "global",
                    "usage_date": usage_date[:10],
                    "cost": float(row.get("PreTaxCost") or row.get("Cost") or 0),
                    "currency": row.get("Currency") or "USD",
                    "service_category": self._classify_service(service_name),
                }
            )
        return rows

    def sync_resources(self) -> list[dict[str, Any]]:
        subscription_id = self._effective_subscription_id()
        if not subscription_id:
            return []
        return AzureResourceDiscovery(self.credential, subscription_id).discover_all()

    def sync_recommendations(self) -> list[dict[str, Any]]:
        return []

    def _effective_subscription_id(self) -> str | None:
        return self.subscription_id

    def _classify_service(self, service_name: str) -> str:
        name = service_name.lower()
        if "virtual machine" in name or "compute" in name:
            return "Compute"
        if "storage" in name:
            return "Storage"
        if "sql" in name or "database" in name:
            return "Database"
        if "monitor" in name:
            return "Monitoring"
        if "network" in name or "bandwidth" in name:
            return "Networking"
        return "Other"
