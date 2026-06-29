from __future__ import annotations

import os
import uuid
from typing import Any

from connectors.common.tenant_guard import resolve_organization_id
from services.supabase_client import supabase


class PlatformHealthRepository:
    _PERSIST = os.getenv("NEXORA_PLATFORM_HEALTH_DB", "").lower() in {"1", "true", "yes"}
    _MEMORY: dict[str, list[dict[str, Any]]] = {
        "platform_health_snapshot": [],
        "platform_health_history": [],
        "platform_operations_log": [],
    }

    @staticmethod
    def save_snapshot(snapshot: dict[str, Any]) -> bool:
        payload = dict(snapshot)
        payload.setdefault("id", str(uuid.uuid4()))
        org_id = resolve_organization_id(payload.get("organization_id"))
        payload["organization_id"] = org_id
        PlatformHealthRepository._memory_upsert("platform_health_snapshot", payload, ("organization_id",))
        PlatformHealthRepository._MEMORY["platform_health_history"].insert(0, payload)
        if not PlatformHealthRepository._PERSIST:
            return True
        try:
            supabase.table("platform_health_snapshot").upsert(payload, on_conflict="organization_id").execute()
            supabase.table("platform_health_history").insert(payload).execute()
            return True
        except Exception:
            return False

    @staticmethod
    def latest_snapshot(organization_id: str | None = None) -> dict[str, Any]:
        rows = PlatformHealthRepository.list_rows("platform_health_snapshot", organization_id, 1)
        return rows[0] if rows else {}

    @staticmethod
    def history(organization_id: str | None = None, limit: int = 30) -> list[dict[str, Any]]:
        return PlatformHealthRepository.list_rows("platform_health_history", organization_id, limit)

    @staticmethod
    def write_operations_log(rows: list[dict[str, Any]]) -> bool:
        if not rows:
            return True
        payloads = []
        for row in rows:
            payload = dict(row)
            payload.setdefault("id", str(uuid.uuid4()))
            payload["organization_id"] = resolve_organization_id(payload.get("organization_id"))
            payloads.append(payload)
        PlatformHealthRepository._MEMORY["platform_operations_log"] = payloads + PlatformHealthRepository._MEMORY["platform_operations_log"]
        if not PlatformHealthRepository._PERSIST:
            return True
        try:
            supabase.table("platform_operations_log").insert(payloads).execute()
            return True
        except Exception:
            return False

    @staticmethod
    def operations_log(organization_id: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        return PlatformHealthRepository.list_rows("platform_operations_log", organization_id, limit)

    @staticmethod
    def list_rows(table_name: str, organization_id: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        org_id = resolve_organization_id(organization_id)
        memory = [
            row
            for row in PlatformHealthRepository._MEMORY.get(table_name, [])
            if row.get("organization_id") == org_id
        ][:limit]
        if memory or not PlatformHealthRepository._PERSIST:
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
    def _memory_upsert(table_name: str, payload: dict[str, Any], keys: tuple[str, ...]) -> None:
        rows = PlatformHealthRepository._MEMORY.setdefault(table_name, [])
        for index, row in enumerate(rows):
            if all(row.get(key) == payload.get(key) for key in keys):
                rows[index] = {**row, **payload}
                return
        rows.insert(0, payload)
