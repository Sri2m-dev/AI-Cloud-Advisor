from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from connectors.common.tenant_guard import resolve_organization_id
from connectors.connector_registry import CONNECTOR_CLASSES
from services.enterprise_asset_identity_service import EnterpriseAssetIdentityService
from services.supabase_client import supabase


class ConnectorOperationsService:
    @staticmethod
    def get_connector_operations(organization_id: str | None = None) -> list[dict[str, Any]]:
        organization_id = resolve_organization_id(organization_id)
        registry_rows = ConnectorOperationsService._load_connector_registry(organization_id)
        history_rows = ConnectorOperationsService._load_sync_history(organization_id)
        asset_counts = ConnectorOperationsService._load_asset_counts(organization_id)

        registry_by_name = {row.get("connector_name"): row for row in registry_rows if row.get("connector_name")}
        latest_history_by_name = ConnectorOperationsService._latest_history_by_connector(history_rows)
        connector_names = sorted(set(CONNECTOR_CLASSES.keys()) | set(registry_by_name.keys()))

        operations = []
        for connector_name in connector_names:
            registry = registry_by_name.get(connector_name, {})
            history = latest_history_by_name.get(connector_name, {})
            status = ConnectorOperationsService._display_status(registry, history)
            last_error = registry.get("last_error") or history.get("error_message") or ""
            last_sync = (
                registry.get("last_sync_at")
                or history.get("completed_at")
                or history.get("started_at")
                or ""
            )
            assets_discovered = int(asset_counts.get(connector_name, 0))
            health_score = ConnectorOperationsService._health_score(
                status=status,
                last_sync=last_sync,
                last_error=last_error,
                assets_discovered=assets_discovered,
            )

            operations.append(
                {
                    "Connector": connector_name,
                    "Status": status,
                    "Last Sync": ConnectorOperationsService._format_datetime(last_sync),
                    "Objects Synced": int(registry.get("objects_synced") or 0),
                    "Costs Synced": int(history.get("costs_synced") or 0),
                    "Resources Synced": int(history.get("resources_synced") or 0),
                    "Assets Discovered": assets_discovered,
                    "Last Error": last_error,
                    "Health Score": health_score,
                    "Recommended Action": ConnectorOperationsService._recommended_action(
                        connector_name=connector_name,
                        status=status,
                        health_score=health_score,
                        last_error=last_error,
                        assets_discovered=assets_discovered,
                    ),
                }
            )

        return operations

    @staticmethod
    def get_kpis(organization_id: str | None = None) -> dict[str, Any]:
        rows = ConnectorOperationsService.get_connector_operations(organization_id)
        connected = sum(1 for row in rows if row["Status"] == "Connected")
        failed = sum(1 for row in rows if row["Status"] == "Failed")
        not_configured = sum(1 for row in rows if row["Status"] == "Not Configured")
        assets = sum(int(row["Assets Discovered"] or 0) for row in rows)
        average_health = round(sum(int(row["Health Score"] or 0) for row in rows) / len(rows)) if rows else 0
        return {
            "Total Connectors": len(rows),
            "Connected": connected,
            "Failed": failed,
            "Not Configured": not_configured,
            "Assets Discovered": assets,
            "Average Health": average_health,
        }

    @staticmethod
    def get_executive_narrative(organization_id: str | None = None) -> str:
        kpis = ConnectorOperationsService.get_kpis(organization_id)
        return (
            f"{kpis['Connected']} of {kpis['Total Connectors']} enterprise connectors are currently connected. "
            f"{kpis['Assets Discovered']:,} assets have been discovered across configured sources, "
            f"with {kpis['Failed']} connector failures requiring attention and "
            f"{kpis['Not Configured']} connectors still awaiting onboarding."
        )

    @staticmethod
    def get_asset_identity_dashboard(organization_id: str | None = None) -> dict[str, Any]:
        metrics = EnterpriseAssetIdentityService.get_identity_coverage(organization_id)
        if (
            organization_id
            and not metrics.get("discovered_assets")
            and not metrics.get("identity_records")
        ):
            metrics = EnterpriseAssetIdentityService.get_identity_coverage()

        identities = EnterpriseAssetIdentityService.get_asset_identities(
            metrics.get("organization_id"),
            limit=25,
        )
        latest = sorted(
            identities,
            key=lambda row: ConnectorOperationsService._parse_datetime(
                row.get("last_seen_at") or row.get("first_seen_at")
            )
            or datetime.min.replace(tzinfo=timezone.utc),
            reverse=True,
        )[:10]

        return {
            "metrics": metrics,
            "coverage_by_provider": ConnectorOperationsService._coverage_by_provider_rows(metrics),
            "latest_asset_ids": ConnectorOperationsService._latest_asset_id_rows(latest),
        }

    @staticmethod
    def _load_connector_registry(organization_id: str) -> list[dict[str, Any]]:
        try:
            response = (
                supabase.table("connector_registry")
                .select("*")
                .eq("organization_id", organization_id)
                .execute()
            )
            return response.data or []
        except Exception as exc:
            print("CONNECTOR OPERATIONS REGISTRY LOAD FAILED:", exc)
            return []

    @staticmethod
    def _load_sync_history(organization_id: str) -> list[dict[str, Any]]:
        try:
            response = (
                supabase.table("connector_sync_history")
                .select("*")
                .eq("organization_id", organization_id)
                .order("started_at", desc=True)
                .limit(500)
                .execute()
            )
            return response.data or []
        except Exception as exc:
            print("CONNECTOR OPERATIONS HISTORY LOAD FAILED:", exc)
            return []

    @staticmethod
    def _load_asset_counts(organization_id: str) -> dict[str, int]:
        try:
            response = (
                supabase.table("discovered_assets")
                .select("connector_name")
                .eq("organization_id", organization_id)
                .execute()
            )
            assets = response.data or []
        except Exception as exc:
            print("CONNECTOR OPERATIONS ASSET LOAD FAILED:", exc)
            assets = []

        counts: dict[str, int] = {}
        for asset in assets:
            connector_name = asset.get("connector_name") or "Unknown"
            counts[connector_name] = counts.get(connector_name, 0) + 1
        return counts

    @staticmethod
    def _coverage_by_provider_rows(metrics: dict[str, Any]) -> list[dict[str, Any]]:
        provider_counts = metrics.get("by_provider") or {}
        total = int(metrics.get("identified_assets") or 0)
        rows = []
        for provider, count in sorted(provider_counts.items()):
            identified = int(count or 0)
            rows.append(
                {
                    "Provider": provider,
                    "Identified Assets": identified,
                    "Share": f"{round((identified / total) * 100, 1) if total else 0}%",
                }
            )
        return rows

    @staticmethod
    def _latest_asset_id_rows(identities: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [
            {
                "Enterprise Asset ID": row.get("asset_uid") or "-",
                "Source Asset ID": row.get("source_asset_id") or "-",
                "Provider": row.get("provider") or "-",
                "Connector": row.get("connector_name") or "-",
                "Asset Type": row.get("normalized_asset_type") or row.get("asset_type") or "-",
                "Last Seen": ConnectorOperationsService._format_datetime(row.get("last_seen_at")),
            }
            for row in identities
        ]

    @staticmethod
    def _latest_history_by_connector(history_rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
        latest = {}
        for row in history_rows:
            connector_name = row.get("connector_name")
            if connector_name and connector_name not in latest:
                latest[connector_name] = row
        return latest

    @staticmethod
    def _display_status(registry: dict[str, Any], history: dict[str, Any]) -> str:
        if not registry:
            return "Not Configured"
        if registry.get("enabled") is False:
            return "Not Configured"

        raw_status = str(registry.get("status") or history.get("sync_status") or "").upper()
        history_status = str(history.get("sync_status") or "").upper()
        if raw_status in {"CONNECTED", "SUCCESS"} or history_status == "SUCCESS":
            return "Connected"
        if raw_status in {"FAILED", "ERROR"} or history_status == "FAILED":
            return "Failed"
        return "Not Configured"

    @staticmethod
    def _health_score(status: str, last_sync: str | None, last_error: str, assets_discovered: int) -> int:
        if status == "Failed":
            return 20
        if status == "Not Configured":
            return 0

        score = 95
        if last_error:
            score -= 25
        if assets_discovered == 0:
            score -= 10
        if ConnectorOperationsService._is_stale(last_sync):
            score -= 20
        return max(score, 0)

    @staticmethod
    def _recommended_action(
        connector_name: str,
        status: str,
        health_score: int,
        last_error: str,
        assets_discovered: int,
    ) -> str:
        if status == "Not Configured":
            return f"Configure {connector_name} connector"
        if status == "Failed":
            return "Review last error, validate credentials, and rerun sync"
        if last_error:
            return "Clear residual error after confirming latest sync"
        if assets_discovered == 0 and connector_name in {"AWS", "Azure", "GCP"}:
            return "Validate resource discovery permissions"
        if health_score < 80:
            return "Run sync from saved config"
        return "Monitor"

    @staticmethod
    def _is_stale(value: str | None) -> bool:
        parsed = ConnectorOperationsService._parse_datetime(value)
        if not parsed:
            return True
        return (datetime.now(timezone.utc) - parsed).total_seconds() > 24 * 60 * 60

    @staticmethod
    def _format_datetime(value: str | None) -> str:
        parsed = ConnectorOperationsService._parse_datetime(value)
        if not parsed:
            return "-"
        return parsed.strftime("%Y-%m-%d %H:%M UTC")

    @staticmethod
    def _parse_datetime(value: str | None) -> datetime | None:
        if not value:
            return None
        try:
            normalized = str(value).replace("Z", "+00:00")
            parsed = datetime.fromisoformat(normalized)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc)
        except Exception:
            return None
