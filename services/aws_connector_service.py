from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from config import DEFAULT_ORG_ID
from connectors.aws.aws_production_connector import AWSProductionConnector
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


class AWSConnectorService:
    CONNECTOR_NAME = "AWS"

    @staticmethod
    def test_connection(
        role_arn=None,
        external_id=None,
        region="us-east-1",
        organization_id: str | None = None,
    ):
        try:
            connector = AWSProductionConnector(role_arn, external_id, region)
            result = connector.test_connection()
        except Exception as exc:
            result = {
                "status": "FAILED",
                "error": str(exc),
            }

        status = result.get("status", "FAILED")
        AWSConnectorService._upsert_connector_registry(
            status=status,
            objects_synced=0,
            error_message=result.get("error"),
            organization_id=organization_id,
        )

        return result

    @staticmethod
    def validate_permissions(role_arn=None, external_id=None, region="us-east-1"):
        try:
            connector = AWSProductionConnector(role_arn, external_id, region)
            return connector.validate_permissions()
        except Exception as exc:
            return [
                {
                    "permission": "AWS Connector Initialization",
                    "status": "FAILED",
                    "error": str(exc),
                    "impact": "Permission validation unavailable",
                }
            ]

    @staticmethod
    def sync_all(role_arn=None, external_id=None, region=None, organization_id: str | None = None):
        started_at = datetime.now(timezone.utc)
        organization_id = AWSConnectorService._resolve_organization_id(organization_id)
        config = AWSConnectorService.get_config(organization_id)
        effective_role_arn = role_arn if role_arn is not None else config.get("role_arn")
        effective_external_id = external_id if external_id is not None else config.get("external_id")
        effective_region = region or config.get("region") or "us-east-1"

        try:
            AWSConnectorService._upsert_connector_registry(
                status="SYNCING",
                objects_synced=0,
                error_message=None,
                organization_id=organization_id,
            )

            connector = AWSProductionConnector(effective_role_arn, effective_external_id, effective_region)

            accounts = connector.sync_accounts()
            costs = connector.sync_costs()
            resources = connector.sync_resources()
            recommendations = connector.sync_recommendations()

            AWSConnectorService._upsert_cloud_accounts(accounts)
            AWSConnectorService._upsert_rows(
                "unified_cloud_costs",
                costs,
                on_conflict="cloud,account_name,service_name,usage_date",
            )
            technology_rows = AWSConnectorService._resources_to_technology_inventory(resources)
            technology_rows = AWSConnectorService._with_organization(technology_rows, organization_id)
            AWSConnectorService._upsert_rows(
                "technology_inventory",
                technology_rows,
                on_conflict="technology_name",
            )
            relationships = AWSConnectorService._resources_to_relationships(
                resources=resources,
                accounts=accounts,
            )
            relationships = AWSConnectorService._with_organization(relationships, organization_id)
            AWSConnectorService._upsert_relationships(relationships)
            AWSConnectorService._upsert_relationship_graph(relationships)
            AWSConnectorService._insert_rows("recommendations", recommendations)

            assets = AWSConnectorService._resources_to_discovered_assets(
                resources=resources,
                accounts=accounts,
            )
            assets = AWSConnectorService._with_organization(assets, organization_id)
            AWSConnectorService._upsert_discovered_assets(assets)

            completed_at = datetime.now(timezone.utc)
            duration_seconds = (
                completed_at - started_at
            ).total_seconds()

            objects_synced = (
                len(accounts)
                + len(costs)
                + len(resources)
                + len(recommendations)
            )

            AWSConnectorService._insert_sync_history(
                sync_status="SUCCESS",
                started_at=started_at,
                completed_at=completed_at,
                duration_seconds=duration_seconds,
                accounts_synced=len(accounts),
                costs_synced=len(costs),
                resources_synced=len(resources),
                recommendations_synced=len(recommendations),
                assets_discovered=len(assets),
                error_message=None,
                organization_id=organization_id,
            )

            AWSConnectorService._upsert_connector_registry(
                status="CONNECTED",
                objects_synced=objects_synced,
                error_message=None,
                last_success=True,
                organization_id=organization_id,
            )

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
            completed_at = datetime.now(timezone.utc)
            duration_seconds = (
                completed_at - started_at
            ).total_seconds()

            error_message = str(exc)

            AWSConnectorService._insert_sync_history(
                sync_status="FAILED",
                started_at=started_at,
                completed_at=completed_at,
                duration_seconds=duration_seconds,
                accounts_synced=0,
                costs_synced=0,
                resources_synced=0,
                recommendations_synced=0,
                assets_discovered=0,
                error_message=error_message,
                organization_id=organization_id,
            )

            AWSConnectorService._upsert_connector_registry(
                status="FAILED",
                objects_synced=0,
                error_message=error_message,
                last_failure=True,
                organization_id=organization_id,
            )

            return {
                "status": "FAILED",
                "error": error_message,
            }

    @staticmethod
    def run_scheduled_sync() -> list[dict]:
        configs = []
        try:
            response = (
                supabase.table("connector_registry")
                .select("*")
                .eq("connector_name", "AWS")
                .eq("enabled", True)
                .execute()
            )
            configs = response.data or []
        except Exception as exc:
            print("AWS SCHEDULED CONFIG LOAD FAILED:", exc)
            return []

        results = []

        for config in configs:
            metadata = config.get("metadata") or {}

            try:
                result = AWSConnectorService.sync_all(
                    role_arn=metadata.get("role_arn"),
                    external_id=metadata.get("external_id"),
                    region=metadata.get("region") or "us-east-1",
                    organization_id=config.get("organization_id"),
                )
                if result.get("status") == "FAILED":
                    retry_result = AWSConnectorService.sync_all(
                        role_arn=metadata.get("role_arn"),
                        external_id=metadata.get("external_id"),
                        region=metadata.get("region") or "us-east-1",
                        organization_id=config.get("organization_id"),
                    )
                    if retry_result.get("status") == "FAILED":
                        AWSConnectorService._write_failure_alert(retry_result)
                    result = retry_result
                results.append(result)
            except Exception as exc:
                error_result = {
                    "status": "FAILED",
                    "error": str(exc),
                    "connector_name": "AWS",
                }
                try:
                    retry_result = AWSConnectorService.sync_all(
                        role_arn=metadata.get("role_arn"),
                        external_id=metadata.get("external_id"),
                        region=metadata.get("region") or "us-east-1",
                        organization_id=config.get("organization_id"),
                    )
                    if retry_result.get("status") == "FAILED":
                        AWSConnectorService._write_failure_alert(retry_result)
                    results.append(retry_result)
                except Exception as retry_exc:
                    error_result["retry_error"] = str(retry_exc)
                    AWSConnectorService._write_failure_alert(error_result)
                    results.append(error_result)

        return results

    @staticmethod
    def preview_live_sync(role_arn=None, external_id=None, region="us-east-1"):
        connector = AWSProductionConnector(role_arn, external_id, region)

        accounts = connector.sync_accounts()
        costs = connector.sync_costs(days=7)

        return {
            "accounts": len(accounts),
            "cost_rows_7_days": len(costs),
            "sample_account": accounts[0] if accounts else {},
            "sample_cost": costs[0] if costs else {},
        }

    @staticmethod
    def save_config(
        organization_id: str,
        configured_by: str,
        role_arn: str | None = None,
        external_id: str | None = None,
        region: str = "us-east-1",
        sync_frequency: str = "DAILY",
        enabled: bool = True,
    ) -> dict[str, Any]:
        now = datetime.now(timezone.utc).isoformat()
        existing = AWSConnectorService.get_config(organization_id)
        role_arn = role_arn if role_arn is not None else existing.get("role_arn")
        external_id = external_id if external_id is not None else existing.get("external_id")
        payload = {
            "connector_name": AWSConnectorService.CONNECTOR_NAME,
            "organization_id": organization_id,
            "configured_by": configured_by,
            "connector_type": "CLOUD",
            "provider": "AWS",
            "status": "CONFIGURED" if enabled else "DISABLED",
            "sync_frequency": sync_frequency,
            "enabled": enabled,
            "metadata": {
                "role_arn": role_arn,
                "external_id": external_id,
                "region": region,
            },
            "updated_at": now,
        }

        try:
            (
                supabase
                .table("connector_registry")
                .upsert(payload, on_conflict="organization_id,connector_name")
                .execute()
            )
        except Exception as exc:
            print("AWS CONNECTOR CONFIG SAVE FAILED:", exc)
            return {
                "status": "FAILED",
                "error": str(exc),
            }

        return {
            "status": "SAVED",
            "connector_name": AWSConnectorService.CONNECTOR_NAME,
            "enabled": enabled,
            "region": region,
            "sync_frequency": sync_frequency,
        }

    @staticmethod
    def get_config(organization_id: str | None = None) -> dict[str, Any]:
        status = AWSConnectorService.get_status(organization_id)
        metadata = status.get("metadata") or {}
        if not status:
            return {}

        return {
            "connector_name": status.get("connector_name", AWSConnectorService.CONNECTOR_NAME),
            "organization_id": status.get("organization_id"),
            "configured_by": status.get("configured_by"),
            "connector_type": status.get("connector_type", "CLOUD"),
            "provider": status.get("provider", "AWS"),
            "status": status.get("status"),
            "enabled": status.get("enabled", False),
            "sync_frequency": status.get("sync_frequency", "DAILY"),
            "role_arn": metadata.get("role_arn"),
            "external_id": metadata.get("external_id"),
            "region": metadata.get("region", "us-east-1"),
            "last_sync_at": status.get("last_sync_at"),
            "last_success_at": status.get("last_success_at"),
            "last_failure_at": status.get("last_failure_at"),
            "last_error": status.get("last_error"),
            "objects_synced": status.get("objects_synced", 0),
        }

    @staticmethod
    def enable_connector(organization_id: str | None = None) -> dict[str, Any]:
        return AWSConnectorService._set_connector_enabled(True, organization_id)

    @staticmethod
    def disable_connector(organization_id: str | None = None) -> dict[str, Any]:
        return AWSConnectorService._set_connector_enabled(False, organization_id)

    @staticmethod
    def get_status(organization_id: str | None = None):
        try:
            organization_id = AWSConnectorService._resolve_organization_id(organization_id)
            response = (
                supabase
                .table("connector_registry")
                .select("*")
                .eq("connector_name", AWSConnectorService.CONNECTOR_NAME)
                .eq("organization_id", organization_id)
                .limit(1)
                .execute()
            )
            rows = response.data or []
            return rows[0] if rows else {}
        except Exception:
            return {}

    @staticmethod
    def get_sync_history(limit: int = 10, organization_id: str | None = None):
        try:
            organization_id = AWSConnectorService._resolve_organization_id(organization_id)
            response = (
                supabase
                .table("connector_sync_history")
                .select("*")
                .eq("connector_name", AWSConnectorService.CONNECTOR_NAME)
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
            organization_id = AWSConnectorService._resolve_organization_id(organization_id)
            assets = (
                supabase.table("discovered_assets")
                .select("*")
                .eq("connector_name", "AWS")
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
            organization_id = AWSConnectorService._resolve_organization_id(organization_id)
            rels = (
                supabase.table("relationship_graph")
                .select("*")
                .eq("source_system", "AWS Connector")
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
    def _set_connector_enabled(enabled: bool, organization_id: str | None = None) -> dict[str, Any]:
        now = datetime.now(timezone.utc).isoformat()
        organization_id = AWSConnectorService._resolve_organization_id(organization_id)
        status_value = "CONFIGURED" if enabled else "DISABLED"
        payload = {
            "connector_name": AWSConnectorService.CONNECTOR_NAME,
            "organization_id": organization_id,
            "connector_type": "CLOUD",
            "provider": "AWS",
            "status": status_value,
            "enabled": enabled,
            "updated_at": now,
        }

        try:
            (
                supabase
                .table("connector_registry")
                .upsert(payload, on_conflict="organization_id,connector_name")
                .execute()
            )
        except Exception as exc:
            print("AWS CONNECTOR ENABLEMENT UPDATE FAILED:", exc)
            return {
                "status": "FAILED",
                "error": str(exc),
            }

        return {
            "status": status_value,
            "enabled": enabled,
            "connector_name": AWSConnectorService.CONNECTOR_NAME,
        }

    @staticmethod
    def _resolve_organization_id(organization_id: str | None = None) -> str:
        return resolve_organization_id(organization_id)

    @staticmethod
    def _with_organization(rows: list[dict[str, Any]], organization_id: str) -> list[dict[str, Any]]:
        return with_organization(rows, organization_id)

    @staticmethod
    def _write_failure_alert(result: dict[str, Any]) -> None:
        now = datetime.now(timezone.utc).isoformat()
        message = result.get("error") or result.get("retry_error") or "AWS scheduled sync failed after retry."
        payload_variants = [
            {
                "source": "AWS Connector",
                "severity": "HIGH",
                "status": "OPEN",
                "title": "AWS scheduled sync failed",
                "message": message,
                "created_at": now,
            },
            {
                "alert_source": "AWS Connector",
                "severity": "HIGH",
                "status": "OPEN",
                "description": message,
                "created_at": now,
            },
            {
                "message": f"AWS scheduled sync failed after retry: {message}",
                "created_at": now,
            },
        ]

        for payload in payload_variants:
            try:
                supabase.table("alert_history").insert(payload).execute()
                return
            except Exception:
                continue

    @staticmethod
    def _insert_rows(table_name: str, rows: list[dict[str, Any]]):
        if not rows:
            return

        try:
            insert_rows(table_name, rows)
        except Exception as exc:
            print(f"{table_name.upper()} INSERT FAILED:", exc)

    @staticmethod
    def _upsert_rows(table_name: str, rows: list[dict[str, Any]], on_conflict: str):
        if not rows:
            return

        try:
            upsert_rows(table_name, rows, on_conflict)
        except Exception as exc:
            print(f"{table_name.upper()} UPSERT FAILED:", exc)

    @staticmethod
    def _upsert_cloud_accounts(rows: list[dict[str, Any]]):
        if not rows:
            return

        try:
            (
                supabase
                .table("cloud_accounts")
                .upsert(rows, on_conflict="account_id")
                .execute()
            )
            return
        except Exception as exc:
            print("CLOUD_ACCOUNTS ACCOUNT_ID UPSERT FAILED:", exc)

        for row in rows:
            account_name = row.get("account_name")
            payload = {
                "cloud_provider": "AWS",
                "account_name": account_name,
                "region": row.get("region"),
            }
            try:
                existing = (
                    supabase
                    .table("cloud_accounts")
                    .select("id")
                    .eq("cloud_provider", "AWS")
                    .eq("account_name", account_name)
                    .limit(1)
                    .execute()
                )
                existing_rows = existing.data or []
                if existing_rows:
                    (
                        supabase
                        .table("cloud_accounts")
                        .update(payload)
                        .eq("id", existing_rows[0]["id"])
                        .execute()
                    )
                else:
                    supabase.table("cloud_accounts").insert(payload).execute()
            except Exception as exc:
                print("CLOUD_ACCOUNTS COMPATIBLE UPSERT FAILED:", exc)

    @staticmethod
    def _resources_to_technology_inventory(resources: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return resources_to_technology_inventory(resources, "AWS", "AWS", "AWS Connector")

    @staticmethod
    def _resources_to_relationships(
        resources: list[dict[str, Any]],
        accounts: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        return resources_to_relationships(resources, accounts, "AWS", "AWS")

    @staticmethod
    def _upsert_relationships(rows: list[dict[str, Any]]):
        if not rows:
            return

        try:
            organization_id = rows[0].get("organization_id") if rows else None
            upsert_technology_relationships(rows, AWSConnectorService._resolve_organization_id(organization_id))
        except Exception as exc:
            print("TECHNOLOGY_RELATIONSHIPS UPSERT FAILED:", exc)

    @staticmethod
    def _upsert_relationship_graph(rows: list[dict[str, Any]]):
        if not rows:
            return

        try:
            organization_id = rows[0].get("organization_id") if rows else None
            upsert_relationship_graph(rows, AWSConnectorService._resolve_organization_id(organization_id), "AWS Connector")
        except Exception as exc:
            print("RELATIONSHIP_GRAPH UPSERT FAILED:", exc)

    @staticmethod
    def _upsert_connector_registry(
        status: str,
        objects_synced: int,
        error_message: str | None,
        last_success: bool = False,
        last_failure: bool = False,
        organization_id: str | None = None,
    ):
        try:
            upsert_connector_registry(
                connector_name=AWSConnectorService.CONNECTOR_NAME,
                connector_type="CLOUD",
                provider="AWS",
                status=status,
                objects_synced=objects_synced,
                error_message=error_message,
                organization_id=AWSConnectorService._resolve_organization_id(organization_id),
                last_success=last_success,
                last_failure=last_failure,
            )
        except Exception as exc:
            print("CONNECTOR REGISTRY UPSERT FAILED:", exc)

    @staticmethod
    def _insert_sync_history(
        sync_status: str,
        started_at: datetime,
        completed_at: datetime,
        duration_seconds: float,
        accounts_synced: int,
        costs_synced: int,
        resources_synced: int,
        recommendations_synced: int,
        assets_discovered: int,
        error_message: str | None,
        organization_id: str | None = None,
    ):
        insert_sync_history(
            connector_name=AWSConnectorService.CONNECTOR_NAME,
            sync_status=sync_status,
            started_at=started_at,
            completed_at=completed_at,
            duration_seconds=duration_seconds,
            accounts_synced=accounts_synced,
            costs_synced=costs_synced,
            resources_synced=resources_synced,
            recommendations_synced=recommendations_synced,
            assets_discovered=assets_discovered,
            error_message=error_message,
            organization_id=AWSConnectorService._resolve_organization_id(organization_id),
        )

    @staticmethod
    def _resources_to_discovered_assets(
        resources: list[dict[str, Any]],
        accounts: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        return resources_to_discovered_assets(
            resources=resources,
            accounts=accounts,
            connector_name=AWSConnectorService.CONNECTOR_NAME,
            provider="AWS",
            source_system="AWS Connector",
            last_seen_at=datetime.now(timezone.utc).isoformat(),
        )

    @staticmethod
    def _upsert_discovered_assets(assets: list[dict[str, Any]]):
        if not assets:
            return

        try:
            organization_id = assets[0].get("organization_id") if assets else None
            upsert_discovered_assets(assets, AWSConnectorService._resolve_organization_id(organization_id))
        except Exception as exc:
            print("DISCOVERED_ASSETS UPSERT FAILED:", exc)
