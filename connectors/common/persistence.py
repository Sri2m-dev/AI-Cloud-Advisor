from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from services.supabase_client import supabase
from connectors.common.tenant_guard import ensure_payload_organization, require_organization_id, with_organization


def insert_rows(table_name: str, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    try:
        supabase.table(table_name).insert(rows).execute()
    except Exception as exc:
        print(f"{table_name.upper()} INSERT FAILED:", exc)


def upsert_rows(table_name: str, rows: list[dict[str, Any]], on_conflict: str) -> None:
    if not rows:
        return
    try:
        supabase.table(table_name).upsert(rows, on_conflict=on_conflict).execute()
    except Exception as exc:
        print(f"{table_name.upper()} UPSERT FAILED:", exc)


def upsert_connector_registry(
    connector_name: str,
    connector_type: str,
    provider: str,
    status: str,
    objects_synced: int,
    error_message: str | None,
    organization_id: str,
    sync_frequency: str = "DAILY",
    enabled: bool = True,
    configured_by: str | None = None,
    metadata: dict[str, Any] | None = None,
    last_success: bool = False,
    last_failure: bool = False,
) -> None:
    now = datetime.now(timezone.utc).isoformat()
    payload = ensure_payload_organization(
        {
            "connector_name": connector_name,
            "connector_type": connector_type,
            "provider": provider,
            "status": status,
            "last_sync_at": now,
            "objects_synced": objects_synced,
            "sync_frequency": sync_frequency,
            "enabled": enabled,
            "last_error": error_message,
            "updated_at": now,
        },
        organization_id,
    )
    if configured_by is not None:
        payload["configured_by"] = configured_by
    if metadata is not None:
        payload["metadata"] = metadata
    if last_success:
        payload["last_success_at"] = now
    if last_failure:
        payload["last_failure_at"] = now
    upsert_rows("connector_registry", [payload], "organization_id,connector_name")


def insert_sync_history(
    connector_name: str,
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
    organization_id: str,
) -> None:
    payload = ensure_payload_organization(
        {
            "connector_name": connector_name,
            "sync_status": sync_status,
            "started_at": started_at.isoformat(),
            "completed_at": completed_at.isoformat(),
            "duration_seconds": duration_seconds,
            "accounts_synced": accounts_synced,
            "costs_synced": costs_synced,
            "resources_synced": resources_synced,
            "recommendations_synced": recommendations_synced,
            "assets_discovered": assets_discovered,
            "error_message": error_message,
        },
        organization_id,
    )
    try:
        supabase.table("connector_sync_history").insert(payload).execute()
    except Exception as exc:
        print("CONNECTOR SYNC HISTORY INSERT FAILED:", exc)
        fallback = {
            "connector_name": connector_name,
            "organization_id": require_organization_id(organization_id),
            "sync_status": sync_status,
            "started_at": started_at.isoformat(),
            "error_message": error_message,
        }
        insert_rows("connector_sync_history", [fallback])


def upsert_discovered_assets(rows: list[dict[str, Any]], organization_id: str) -> None:
    upsert_rows(
        "discovered_assets",
        with_organization(rows, organization_id),
        "connector_name,provider,asset_id",
    )


def upsert_technology_inventory(rows: list[dict[str, Any]], organization_id: str) -> None:
    upsert_rows("technology_inventory", with_organization(rows, organization_id), "technology_name")


def upsert_technology_relationships(rows: list[dict[str, Any]], organization_id: str) -> None:
    upsert_rows(
        "technology_relationships",
        with_organization(rows, organization_id),
        "organization_id,source_type,source_name,relationship_type,target_type,target_name",
    )


def upsert_relationship_graph(rows: list[dict[str, Any]], organization_id: str, source_system: str) -> None:
    graph_rows = []
    for row in with_organization(rows, organization_id):
        graph_rows.append(
            {
                "source_type": row.get("source_type"),
                "source_name": row.get("source_name"),
                "relationship_type": row.get("relationship_type"),
                "target_type": row.get("target_type"),
                "target_name": row.get("target_name"),
                "organization_id": row.get("organization_id"),
                "source_system": source_system,
            }
        )
    upsert_rows(
        "relationship_graph",
        graph_rows,
        "organization_id,source_type,source_name,relationship_type,target_type,target_name",
    )

