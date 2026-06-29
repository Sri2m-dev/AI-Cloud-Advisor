from __future__ import annotations

import os
import uuid
from typing import Any

from connectors.common.tenant_guard import resolve_organization_id
from services.supabase_client import supabase


class SecurityRepository:
    _PERSIST = os.getenv("NEXORA_ENTERPRISE_SECURITY_DB", "").lower() in {"1", "true", "yes"}
    _MEMORY: dict[str, list[dict[str, Any]]] = {
        "security_validation_run": [],
        "security_validation_result": [],
        "credential_inventory": [],
        "credential_rotation": [],
        "token_expiry": [],
        "rbac_validation": [],
        "tenant_validation": [],
        "execution_security": [],
        "security_event": [],
        "security_recommendation": [],
    }

    @staticmethod
    def save_run(row: dict[str, Any]) -> dict[str, Any]:
        payload = SecurityRepository._scoped(row)
        payload.setdefault("id", str(uuid.uuid4()))
        SecurityRepository._memory_upsert("security_validation_run", payload, ("organization_id", "id"))
        SecurityRepository._persist_upsert("security_validation_run", payload, "organization_id,id")
        return payload

    @staticmethod
    def insert_results(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return SecurityRepository.insert_rows("security_validation_result", rows)

    @staticmethod
    def insert_credentials(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return SecurityRepository.insert_rows("credential_inventory", rows)

    @staticmethod
    def insert_rotations(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return SecurityRepository.insert_rows("credential_rotation", rows)

    @staticmethod
    def insert_token_expiry(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return SecurityRepository.insert_rows("token_expiry", rows)

    @staticmethod
    def insert_rbac(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return SecurityRepository.insert_rows("rbac_validation", [SecurityRepository._payload_row(row) for row in rows])

    @staticmethod
    def insert_tenant(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return SecurityRepository.insert_rows("tenant_validation", [SecurityRepository._payload_row(row) for row in rows])

    @staticmethod
    def insert_execution(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return SecurityRepository.insert_rows("execution_security", [SecurityRepository._payload_row(row) for row in rows])

    @staticmethod
    def insert_events(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return SecurityRepository.insert_rows("security_event", rows)

    @staticmethod
    def insert_recommendations(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return SecurityRepository.insert_rows("security_recommendation", rows)

    @staticmethod
    def latest_run(organization_id: str | None = None) -> dict[str, Any]:
        rows = SecurityRepository.list_rows("security_validation_run", organization_id, 1)
        return rows[0] if rows else {}

    @staticmethod
    def history(organization_id: str | None = None, limit: int = 30) -> list[dict[str, Any]]:
        return SecurityRepository.list_rows("security_validation_run", organization_id, limit)

    @staticmethod
    def insert_row(table_name: str, row: dict[str, Any]) -> dict[str, Any]:
        payload = SecurityRepository._scoped(row)
        payload.setdefault("id", str(uuid.uuid4()))
        SecurityRepository._MEMORY.setdefault(table_name, []).insert(0, payload)
        SecurityRepository._persist_insert(table_name, payload)
        return payload

    @staticmethod
    def insert_rows(table_name: str, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [SecurityRepository.insert_row(table_name, row) for row in rows]

    @staticmethod
    def list_rows(table_name: str, organization_id: str | None = None, limit: int = 200) -> list[dict[str, Any]]:
        org_id = resolve_organization_id(organization_id)
        memory = [
            row
            for row in SecurityRepository._MEMORY.get(table_name, [])
            if row.get("organization_id") == org_id
        ][:limit]
        if memory or not SecurityRepository._PERSIST:
            return memory
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

    @staticmethod
    def _scoped(row: dict[str, Any]) -> dict[str, Any]:
        payload = dict(row)
        payload["organization_id"] = resolve_organization_id(payload.get("organization_id"))
        return payload

    @staticmethod
    def _payload_row(row: dict[str, Any]) -> dict[str, Any]:
        keep = {
            "organization_id": row.get("organization_id"),
            "run_id": row.get("run_id"),
        }
        return {key: value for key, value in keep.items() if value is not None} | {"payload": dict(row)}

    @staticmethod
    def _memory_upsert(table_name: str, payload: dict[str, Any], keys: tuple[str, ...]) -> None:
        rows = SecurityRepository._MEMORY.setdefault(table_name, [])
        for index, row in enumerate(rows):
            if all(row.get(key) == payload.get(key) for key in keys):
                rows[index] = {**row, **payload}
                return
        rows.insert(0, payload)

    @staticmethod
    def _persist_insert(table_name: str, payload: dict[str, Any]) -> None:
        if not SecurityRepository._PERSIST:
            return
        try:
            supabase.table(table_name).insert(payload).execute()
        except Exception:
            return

    @staticmethod
    def _persist_upsert(table_name: str, payload: dict[str, Any], on_conflict: str) -> None:
        if not SecurityRepository._PERSIST:
            return
        try:
            supabase.table(table_name).upsert(payload, on_conflict=on_conflict).execute()
        except Exception:
            return
