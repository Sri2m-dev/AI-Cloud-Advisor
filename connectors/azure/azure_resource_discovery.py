from __future__ import annotations

from typing import Any

from azure.core.exceptions import AzureError
from azure.mgmt.resource.resources import ResourceManagementClient


class AzureResourceDiscovery:
    RESOURCE_TYPE_MAP = {
        "microsoft.compute/virtualmachines": "Azure VM",
        "microsoft.storage/storageaccounts": "Azure Storage Account",
        "microsoft.network/virtualnetworks": "Azure VNet",
        "microsoft.sql/servers/databases": "Azure SQL Database",
        "microsoft.containerservice/managedclusters": "Azure AKS Cluster",
        "microsoft.network/loadbalancers": "Azure Load Balancer",
    }

    def __init__(self, credential: Any, subscription_id: str | None):
        self.credential = credential
        self.subscription_id = subscription_id

    def discover_all(self) -> list[dict[str, Any]]:
        if not self.subscription_id:
            return []

        resources: list[dict[str, Any]] = []
        resources.extend(self._safe_discover(self.discover_resource_groups))
        resources.extend(self._safe_discover(self.discover_platform_resources))
        return resources

    def discover_resource_groups(self) -> list[dict[str, Any]]:
        client = ResourceManagementClient(self.credential, self.subscription_id)
        rows = []
        for resource_group in client.resource_groups.list():
            rows.append(
                self._row(
                    resource_id=f"/subscriptions/{self.subscription_id}/resourceGroups/{resource_group.name}",
                    resource_type="Azure Resource Group",
                    name=resource_group.name,
                    resource_group=resource_group.name,
                    region=resource_group.location,
                    status=resource_group.properties.provisioning_state
                    if getattr(resource_group, "properties", None)
                    else "ACTIVE",
                    tags=resource_group.tags or {},
                )
            )
        return rows

    def discover_platform_resources(self) -> list[dict[str, Any]]:
        client = ResourceManagementClient(self.credential, self.subscription_id)
        rows = []
        for resource in client.resources.list():
            resource_type = self._normalized_resource_type(resource.type)
            if not resource_type:
                continue
            rows.append(
                self._row(
                    resource_id=resource.id,
                    resource_type=resource_type,
                    name=resource.name,
                    resource_group=self._resource_group_from_id(resource.id),
                    region=resource.location,
                    status="ACTIVE",
                    tags=resource.tags or {},
                    raw_payload={
                        "id": resource.id,
                        "name": resource.name,
                        "type": resource.type,
                        "location": resource.location,
                        "tags": resource.tags or {},
                    },
                )
            )
        return rows

    def _safe_discover(self, discover) -> list[dict[str, Any]]:
        try:
            return discover()
        except AzureError as exc:
            print(f"AZURE {discover.__name__.replace('discover_', '').upper()} DISCOVERY SKIPPED:", exc)
            return []
        except Exception as exc:
            print(f"AZURE {discover.__name__.replace('discover_', '').upper()} DISCOVERY SKIPPED:", exc)
            return []

    def _normalized_resource_type(self, raw_type: str | None) -> str | None:
        if not raw_type:
            return None
        return self.RESOURCE_TYPE_MAP.get(raw_type.lower())

    def _resource_group_from_id(self, resource_id: str | None) -> str:
        if not resource_id:
            return ""
        parts = resource_id.split("/")
        for index, part in enumerate(parts):
            if part.lower() == "resourcegroups" and index + 1 < len(parts):
                return parts[index + 1]
        return ""

    def _row(
        self,
        resource_id: str | None,
        resource_type: str,
        name: str | None,
        resource_group: str | None,
        region: str | None,
        status: str | None,
        tags: dict[str, Any] | None,
        raw_payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        asset_id = resource_id or name or "unknown-azure-resource"
        asset_name = name or asset_id
        return {
            "resource_id": asset_id,
            "resource_type": resource_type,
            "name": asset_name,
            "provider": "Azure",
            "subscription_id": self.subscription_id,
            "resource_group": resource_group or "",
            "region": region or "global",
            "status": status or "ACTIVE",
            "tags": tags or {},
            "technology_name": asset_name,
            "technology_type": "Cloud Resource",
            "vendor_name": "Azure",
            "category": resource_type,
            "cloud_provider": "Azure",
            "owner_department": "CloudOps",
            "business_owner": "CloudOps Lead",
            "technical_owner": "Cloud Architect",
            "annual_cost": 0,
            "source_system": "Azure Connector",
            "asset_id": asset_id,
            "asset_name": asset_name,
            "asset_type": resource_type,
            "raw_payload": raw_payload or {},
        }
