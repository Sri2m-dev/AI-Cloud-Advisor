from __future__ import annotations

import uuid
import os
from typing import Any

from connectors.common.tenant_guard import resolve_organization_id
from services.supabase_client import supabase


class EnterpriseConnectorRepository:
    _PERSIST = os.getenv("NEXORA_CONNECTOR_PLATFORM_DB", "").lower() in {"1", "true", "yes"}
    _MEMORY: dict[str, list[dict[str, Any]]] = {
        "enterprise_connector_registry": [],
        "connector_credential_vault": [],
        "connector_sync_run": [],
        "enterprise_data_fabric": [],
        "connector_quality_event": [],
        "connector_certification": [],
        "connector_discovery": [],
        "connector_resource_summary": [],
        "connector_api_usage": [],
        "connector_certification_history": [],
        "connector_health_metrics": [],
    }

    @staticmethod
    def upsert_registry(row: dict[str, Any]) -> bool:
        payload = dict(row)
        payload.setdefault("id", str(uuid.uuid4()))
        EnterpriseConnectorRepository._memory_upsert("enterprise_connector_registry", payload, ("organization_id", "connector_name"))
        if not EnterpriseConnectorRepository._PERSIST:
            return True
        try:
            supabase.table("enterprise_connector_registry").upsert(
                payload,
                on_conflict="organization_id,connector_name",
            ).execute()
            return True
        except Exception:
            return False

    @staticmethod
    def list_registry(organization_id: str | None = None) -> list[dict[str, Any]]:
        memory = EnterpriseConnectorRepository._memory_list("enterprise_connector_registry", organization_id)
        if memory or not EnterpriseConnectorRepository._PERSIST:
            return memory
        return EnterpriseConnectorRepository._list("enterprise_connector_registry", organization_id)

    @staticmethod
    def save_credential_ref(row: dict[str, Any]) -> bool:
        payload = dict(row)
        payload.setdefault("id", str(uuid.uuid4()))
        EnterpriseConnectorRepository._memory_upsert("connector_credential_vault", payload, ("organization_id", "connector_name"))
        if not EnterpriseConnectorRepository._PERSIST:
            return True
        try:
            supabase.table("connector_credential_vault").upsert(
                payload,
                on_conflict="organization_id,connector_name",
            ).execute()
            return True
        except Exception:
            return False

    @staticmethod
    def get_credential_ref(connector_name: str, organization_id: str | None = None) -> dict[str, Any]:
        org_id = resolve_organization_id(organization_id)
        memory = next(
            (
                row
                for row in EnterpriseConnectorRepository._MEMORY["connector_credential_vault"]
                if row.get("organization_id") == org_id and row.get("connector_name") == connector_name
            ),
            {},
        )
        if memory or not EnterpriseConnectorRepository._PERSIST:
            return memory
        try:
            return (
                supabase.table("connector_credential_vault")
                .select("*")
                .eq("organization_id", org_id)
                .eq("connector_name", connector_name)
                .limit(1)
                .execute()
                .data
                or [{}]
            )[0]
        except Exception:
            return {}

    @staticmethod
    def insert_sync_run(row: dict[str, Any]) -> bool:
        payload = dict(row)
        payload.setdefault("id", str(uuid.uuid4()))
        EnterpriseConnectorRepository._MEMORY["connector_sync_run"].insert(0, payload)
        if not EnterpriseConnectorRepository._PERSIST:
            return True
        try:
            supabase.table("connector_sync_run").insert(payload).execute()
            return True
        except Exception:
            return False

    @staticmethod
    def list_sync_runs(organization_id: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        memory = EnterpriseConnectorRepository._memory_list("connector_sync_run", organization_id, limit)
        if memory or not EnterpriseConnectorRepository._PERSIST:
            return memory
        return EnterpriseConnectorRepository._list("connector_sync_run", organization_id, limit)

    @staticmethod
    def upsert_fabric_records(rows: list[dict[str, Any]]) -> bool:
        if not rows:
            return True
        for row in rows:
            EnterpriseConnectorRepository._memory_upsert("enterprise_data_fabric", row, ("organization_id", "fabric_key"))
        if not EnterpriseConnectorRepository._PERSIST:
            return True
        try:
            supabase.table("enterprise_data_fabric").upsert(
                rows,
                on_conflict="organization_id,fabric_key",
            ).execute()
            return True
        except Exception:
            return False

    @staticmethod
    def list_fabric(organization_id: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        memory = EnterpriseConnectorRepository._memory_list("enterprise_data_fabric", organization_id, limit)
        if memory or not EnterpriseConnectorRepository._PERSIST:
            return memory
        return EnterpriseConnectorRepository._list("enterprise_data_fabric", organization_id, limit)

    @staticmethod
    def insert_quality_event(row: dict[str, Any]) -> bool:
        payload = dict(row)
        payload.setdefault("id", str(uuid.uuid4()))
        EnterpriseConnectorRepository._MEMORY["connector_quality_event"].insert(0, payload)
        if not EnterpriseConnectorRepository._PERSIST:
            return True
        try:
            supabase.table("connector_quality_event").insert(payload).execute()
            return True
        except Exception:
            return False

    @staticmethod
    def upsert_certification(row: dict[str, Any]) -> bool:
        payload = dict(row)
        payload.setdefault("id", str(uuid.uuid4()))
        EnterpriseConnectorRepository._memory_upsert(
            "connector_certification",
            payload,
            ("organization_id", "connector_name", "connector_version"),
        )
        if not EnterpriseConnectorRepository._PERSIST:
            return True
        try:
            supabase.table("connector_certification").upsert(
                payload,
                on_conflict="organization_id,connector_name,connector_version",
            ).execute()
            return True
        except Exception:
            return False

    @staticmethod
    def list_certifications(organization_id: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        memory = EnterpriseConnectorRepository._memory_list("connector_certification", organization_id, limit)
        if memory or not EnterpriseConnectorRepository._PERSIST:
            return memory
        return EnterpriseConnectorRepository._list("connector_certification", organization_id, limit)

    @staticmethod
    def insert_generic(table_name: str, row: dict[str, Any]) -> bool:
        payload = dict(row)
        payload.setdefault("id", str(uuid.uuid4()))
        EnterpriseConnectorRepository._MEMORY.setdefault(table_name, []).insert(0, payload)
        if not EnterpriseConnectorRepository._PERSIST:
            return True
        try:
            supabase.table(table_name).insert(payload).execute()
            return True
        except Exception:
            return False

    @staticmethod
    def upsert_generic(table_name: str, row: dict[str, Any], on_conflict: str) -> bool:
        payload = dict(row)
        payload.setdefault("id", str(uuid.uuid4()))
        keys = tuple(key.strip() for key in on_conflict.split(","))
        EnterpriseConnectorRepository._memory_upsert(table_name, payload, keys)
        if not EnterpriseConnectorRepository._PERSIST:
            return True
        try:
            supabase.table(table_name).upsert(payload, on_conflict=on_conflict).execute()
            return True
        except Exception:
            return False

    @staticmethod
    def list_generic(table_name: str, organization_id: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        memory = EnterpriseConnectorRepository._memory_list(table_name, organization_id, limit)
        if memory or not EnterpriseConnectorRepository._PERSIST:
            return memory
        return EnterpriseConnectorRepository._list(table_name, organization_id, limit)

    @staticmethod
    def list_quality_events(organization_id: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        memory = EnterpriseConnectorRepository._memory_list("connector_quality_event", organization_id, limit)
        if memory or not EnterpriseConnectorRepository._PERSIST:
            return memory
        return EnterpriseConnectorRepository._list("connector_quality_event", organization_id, limit)

    @staticmethod
    def _memory_upsert(table_name: str, payload: dict[str, Any], keys: tuple[str, ...]) -> None:
        rows = EnterpriseConnectorRepository._MEMORY.setdefault(table_name, [])
        for index, row in enumerate(rows):
            if all(row.get(key) == payload.get(key) for key in keys):
                rows[index] = {**row, **payload}
                return
        rows.insert(0, payload)

    @staticmethod
    def _memory_list(table_name: str, organization_id: str | None = None, limit: int = 200) -> list[dict[str, Any]]:
        org_id = resolve_organization_id(organization_id)
        rows = [
            row
            for row in EnterpriseConnectorRepository._MEMORY.get(table_name, [])
            if row.get("organization_id") == org_id
        ]
        return rows[:limit]

    @staticmethod
    def _list(table_name: str, organization_id: str | None = None, limit: int = 200) -> list[dict[str, Any]]:
        org_id = resolve_organization_id(organization_id)
        try:
            return (
                supabase.table(table_name)
                .select("*")
                .eq("organization_id", org_id)
                .order("created_at", desc=True)
                .limit(limit)
                .execute()
                .data
                or []
            )
        except Exception:
            return []
