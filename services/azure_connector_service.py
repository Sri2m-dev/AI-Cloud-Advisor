from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from config import DEFAULT_ORG_ID
from connectors.azure.azure_production_connector import AzureProductionConnector
from connectors.common.normalization import (
    resources_to_discovered_assets,
    resources_to_relationships,
    resources_to_technology_inventory,
)
from connectors.common.persistence import (
    insert_rows,
    insert_sync_history,
    upsert_connector_registry,
    upsert_discovered_assets,
    upsert_relationship_graph,
    upsert_rows,
    upsert_technology_inventory,
    upsert_technology_relationships,
)
from connectors.common.tenant_guard import resolve_organization_id, with_organization
from services.supabase_client import supabase


class AzureConnectorService:
    CONNECTOR_NAME = "Azure"

    @staticmethod
    def test_connection(
        tenant_id: str | None = None,
        client_id: str | None = None,
        client_secret: str | None = None,
        subscription_id: str | None = None,
    ) -> dict[str, Any]:
        try:
            connector = AzureProductionConnector(tenant_id, client_id, client_secret, subscription_id)
            result = connector.test_connection()
        except Exception as exc:
            result = {"status": "FAILED", "error": str(exc)}

        AzureConnectorService._upsert_connector_registry(
            status=result.get("status", "FAILED"),
            objects_synced=0,
            error_message=result.get("error"),
        )
        return result

    @staticmethod
    def save_config(
        organization_id: str,
        configured_by: str,
        tenant_id: str | None = None,
        client_id: str | None = None,
        client_secret: str | None = None,
        subscription_id: str | None = None,
        sync_frequency: str = "DAILY",
        enabled: bool = True,
    ) -> dict[str, Any]:
        now = datetime.now(timezone.utc).isoformat()
        existing = AzureConnectorService.get_config(organization_id)
        tenant_id = tenant_id if tenant_id is not None else existing.get("tenant_id")
        client_id = client_id if client_id is not None else existing.get("client_id")
        client_secret = client_secret if client_secret is not None else existing.get("client_secret")
        subscription_id = subscription_id if subscription_id is not None else existing.get("subscription_id")
        payload = {
            "connector_name": AzureConnectorService.CONNECTOR_NAME,
            "organization_id": organization_id,
            "configured_by": configured_by,
            "connector_type": "CLOUD",
            "provider": "Azure",
            "status": "CONFIGURED" if enabled else "DISABLED",
            "sync_frequency": sync_frequency,
            "enabled": enabled,
            "metadata": {
                "tenant_id": tenant_id,
                "client_id": client_id,
                "client_secret": client_secret,
                "subscription_id": subscription_id,
            },
            "updated_at": now,
        }
        try:
            supabase.table("connector_registry").upsert(payload, on_conflict="organization_id,connector_name").execute()
        except Exception as exc:
            print("AZURE CONNECTOR CONFIG SAVE FAILED:", exc)
            return {"status": "FAILED", "error": str(exc)}
        return {"status": "SAVED", "connector_name": "Azure", "enabled": enabled}

    @staticmethod
    def get_config(organization_id: str | None = None) -> dict[str, Any]:
        status = AzureConnectorService.get_status(organization_id)
        metadata = status.get("metadata") or {}
        if not status:
            return {}
        return {
            "connector_name": status.get("connector_name", "Azure"),
            "organization_id": status.get("organization_id"),
            "configured_by": status.get("configured_by"),
            "status": status.get("status"),
            "enabled": status.get("enabled", False),
            "sync_frequency": status.get("sync_frequency", "DAILY"),
            "tenant_id": metadata.get("tenant_id"),
            "client_id": metadata.get("client_id"),
            "client_secret": metadata.get("client_secret"),
            "subscription_id": metadata.get("subscription_id"),
            "last_sync_at": status.get("last_sync_at"),
            "last_error": status.get("last_error"),
            "objects_synced": status.get("objects_synced", 0),
        }

    @staticmethod
    def sync_all(
        tenant_id: str | None = None,
        client_id: str | None = None,
        client_secret: str | None = None,
        subscription_id: str | None = None,
        organization_id: str | None = None,
    ) -> dict[str, Any]:
        organization_id = AzureConnectorService._resolve_organization_id(organization_id)
        config = AzureConnectorService.get_config(organization_id)
        effective_tenant_id = tenant_id if tenant_id is not None else config.get("tenant_id")
        effective_client_id = client_id if client_id is not None else config.get("client_id")
        effective_client_secret = client_secret if client_secret is not None else config.get("client_secret")
        effective_subscription_id = subscription_id if subscription_id is not None else config.get("subscription_id")
        started_at = datetime.now(timezone.utc)

        try:
            AzureConnectorService._upsert_connector_registry("SYNCING", 0, None, organization_id=organization_id)
            connector = AzureProductionConnector(
                effective_tenant_id,
                effective_client_id,
                effective_client_secret,
                effective_subscription_id,
            )
            accounts = connector.sync_accounts()
            costs = connector.sync_costs()
            resources = connector.sync_resources()
            recommendations = connector.sync_recommendations()

            AzureConnectorService._upsert_rows(
                "unified_cloud_costs",
                costs,
                on_conflict="cloud,account_name,service_name,usage_date",
            )
            technology_rows = resources_to_technology_inventory(
                resources,
                vendor_name="Azure",
                cloud_provider="Azure",
                source_system="Azure Connector",
            )
            upsert_technology_inventory(technology_rows, organization_id)

            relationships = resources_to_relationships(
                resources,
                accounts,
                provider="Azure",
                platform_name="Azure",
            )
            upsert_technology_relationships(relationships, organization_id)
            upsert_relationship_graph(relationships, organization_id, "Azure Connector")

            assets = resources_to_discovered_assets(
                resources=resources,
                accounts=accounts,
                connector_name=AzureConnectorService.CONNECTOR_NAME,
                provider="Azure",
                source_system="Azure Connector",
                last_seen_at=datetime.now(timezone.utc).isoformat(),
            )
            upsert_discovered_assets(assets, organization_id)
            AzureConnectorService._insert_rows("recommendations", recommendations)

            objects_synced = len(accounts) + len(costs) + len(resources) + len(recommendations)
            AzureConnectorService._insert_sync_history(
                "SUCCESS",
                started_at,
                len(accounts),
                len(costs),
                len(resources),
                len(recommendations),
                None,
                assets_discovered=len(assets),
                organization_id=organization_id,
            )
            AzureConnectorService._upsert_connector_registry("CONNECTED", objects_synced, None, last_success=True, organization_id=organization_id)
            return {
                "status": "SUCCESS",
                "accounts": len(accounts),
                "costs": len(costs),
                "resources": len(resources),
                "recommendations": len(recommendations),
                "assets_discovered": len(assets),
                "objects_synced": objects_synced,
            }
        except Exception as exc:
            error_message = str(exc)
            AzureConnectorService._insert_sync_history(
                "FAILED",
                started_at,
                0,
                0,
                0,
                0,
                error_message,
                assets_discovered=0,
                organization_id=organization_id,
            )
            AzureConnectorService._upsert_connector_registry("FAILED", 0, error_message, last_failure=True, organization_id=organization_id)
            return {"status": "FAILED", "error": error_message}

    @staticmethod
    def preview_live_sync(
        tenant_id: str | None = None,
        client_id: str | None = None,
        client_secret: str | None = None,
        subscription_id: str | None = None,
        organization_id: str | None = None,
    ) -> dict[str, Any]:
        config = AzureConnectorService.get_config(organization_id)
        effective_tenant_id = tenant_id if tenant_id is not None else config.get("tenant_id")
        effective_client_id = client_id if client_id is not None else config.get("client_id")
        effective_client_secret = client_secret if client_secret is not None else config.get("client_secret")
        effective_subscription_id = subscription_id if subscription_id is not None else config.get("subscription_id")

        try:
            connector = AzureProductionConnector(
                effective_tenant_id,
                effective_client_id,
                effective_client_secret,
                effective_subscription_id,
            )
            accounts = connector.sync_accounts()
            costs = connector.sync_costs(days=7)
            resources = connector.sync_resources()
        except Exception as exc:
            print("AZURE PREVIEW SYNC SKIPPED:", exc)
            accounts = []
            costs = []
            resources = []

        return {
            "accounts": len(accounts),
            "cost_rows_7_days": len(costs),
            "resources": len(resources),
            "sample_account": accounts[0] if accounts else {},
            "sample_cost": costs[0] if costs else {},
            "sample_resource": resources[0] if resources else {},
        }

    @staticmethod
    def get_status(organization_id: str | None = None) -> dict[str, Any]:
        try:
            organization_id = AzureConnectorService._resolve_organization_id(organization_id)
            response = (
                supabase.table("connector_registry")
                .select("*")
                .eq("connector_name", AzureConnectorService.CONNECTOR_NAME)
                .eq("organization_id", organization_id)
                .limit(1)
                .execute()
            )
            rows = response.data or []
            return rows[0] if rows else {}
        except Exception:
            return {}

    @staticmethod
    def get_sync_history(limit: int = 10, organization_id: str | None = None) -> list[dict[str, Any]]:
        try:
            organization_id = AzureConnectorService._resolve_organization_id(organization_id)
            response = (
                supabase.table("connector_sync_history")
                .select("*")
                .eq("connector_name", AzureConnectorService.CONNECTOR_NAME)
                .eq("organization_id", organization_id)
                .order("started_at", desc=True)
                .limit(limit)
                .execute()
            )
            return response.data or []
        except Exception:
            return []

    @staticmethod
    def get_discovery_summary(organization_id: str | None = None) -> dict:
        try:
            organization_id = AzureConnectorService._resolve_organization_id(organization_id)
            assets = (
                supabase.table("discovered_assets")
                .select("*")
                .eq("connector_name", AzureConnectorService.CONNECTOR_NAME)
                .eq("organization_id", organization_id)
                .execute()
                .data
                or []
            )
        except Exception:
            assets = []

        by_type = {}
        for asset in assets:
            asset_type = asset.get("asset_type") or "Unknown"
            by_type[asset_type] = by_type.get(asset_type, 0) + 1

        return {
            "assets_discovered": len(assets),
            "resource_types": len(by_type),
            "resources_by_type": by_type,
            "latest_assets": assets[:20],
        }

    @staticmethod
    def get_relationship_summary(organization_id: str | None = None) -> dict:
        try:
            organization_id = AzureConnectorService._resolve_organization_id(organization_id)
            rels = (
                supabase.table("relationship_graph")
                .select("*")
                .eq("source_system", "Azure Connector")
                .eq("organization_id", organization_id)
                .execute()
                .data
                or []
            )
        except Exception:
            rels = []

        return {
            "relationship_edges": len(rels),
            "latest_relationships": rels[:20],
        }

    @staticmethod
    def _upsert_connector_registry(
        status: str,
        objects_synced: int,
        error_message: str | None,
        last_success: bool = False,
        last_failure: bool = False,
        organization_id: str | None = None,
    ) -> None:
        try:
            upsert_connector_registry(
                connector_name=AzureConnectorService.CONNECTOR_NAME,
                connector_type="CLOUD",
                provider="Azure",
                status=status,
                objects_synced=objects_synced,
                error_message=error_message,
                organization_id=AzureConnectorService._resolve_organization_id(organization_id),
                last_success=last_success,
                last_failure=last_failure,
            )
        except Exception as exc:
            print("AZURE CONNECTOR REGISTRY UPSERT FAILED:", exc)

    @staticmethod
    def _insert_rows(table_name: str, rows: list[dict[str, Any]]) -> None:
        if not rows:
            return
        try:
            insert_rows(table_name, rows)
        except Exception as exc:
            print(f"{table_name.upper()} INSERT FAILED:", exc)

    @staticmethod
    def _upsert_rows(table_name: str, rows: list[dict[str, Any]], on_conflict: str) -> None:
        if not rows:
            return
        try:
            upsert_rows(table_name, rows, on_conflict)
        except Exception as exc:
            print(f"{table_name.upper()} UPSERT FAILED:", exc)

    @staticmethod
    def _insert_sync_history(
        sync_status: str,
        started_at: datetime,
        accounts_synced: int,
        costs_synced: int,
        resources_synced: int,
        recommendations_synced: int,
        error_message: str | None,
        assets_discovered: int | None = None,
        organization_id: str | None = None,
    ) -> None:
        completed_at = datetime.now(timezone.utc)
        insert_sync_history(
            connector_name=AzureConnectorService.CONNECTOR_NAME,
            sync_status=sync_status,
            started_at=started_at,
            completed_at=completed_at,
            duration_seconds=(completed_at - started_at).total_seconds(),
            accounts_synced=accounts_synced,
            costs_synced=costs_synced,
            resources_synced=resources_synced,
            recommendations_synced=recommendations_synced,
            assets_discovered=assets_discovered if assets_discovered is not None else resources_synced,
            error_message=error_message,
            organization_id=AzureConnectorService._resolve_organization_id(organization_id),
        )

    @staticmethod
    def _resolve_organization_id(organization_id: str | None = None) -> str:
        return resolve_organization_id(organization_id)

    @staticmethod
    def _with_organization(rows: list[dict[str, Any]], organization_id: str) -> list[dict[str, Any]]:
        return with_organization(rows, organization_id)
