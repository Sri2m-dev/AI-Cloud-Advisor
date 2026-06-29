from __future__ import annotations

import os
import uuid
from typing import Any

from connectors.common.tenant_guard import resolve_organization_id
from services.supabase_client import supabase


class ComplianceRepository:
    _PERSIST = os.getenv("NEXORA_COMPLIANCE_DB", "").lower() in {"1", "true", "yes"}
    _MEMORY: dict[str, list[dict[str, Any]]] = {
        "compliance_run": [],
        "compliance_framework": [],
        "compliance_control": [],
        "compliance_evidence": [],
        "audit_package": [],
        "dr_readiness": [],
        "operational_readiness": [],
        "release_readiness": [],
        "production_readiness": [],
        "version_readiness_report": [],
        "readiness_recommendation": [],
    }

    @staticmethod
    def save_run(row: dict[str, Any]) -> dict[str, Any]:
        payload = ComplianceRepository._scoped(row)
        payload.setdefault("id", str(uuid.uuid4()))
        ComplianceRepository._memory_upsert("compliance_run", payload, ("organization_id", "id"))
        ComplianceRepository._persist_upsert("compliance_run", payload, "organization_id,id")
        return payload

    @staticmethod
    def insert_rows(table_name: str, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [ComplianceRepository.insert_row(table_name, row) for row in rows]

    @staticmethod
    def insert_row(table_name: str, row: dict[str, Any]) -> dict[str, Any]:
        payload = ComplianceRepository._scoped(row)
        payload.setdefault("id", str(uuid.uuid4()))
        ComplianceRepository._MEMORY.setdefault(table_name, []).insert(0, payload)
        ComplianceRepository._persist_insert(table_name, payload)
        return payload

    @staticmethod
    def latest_run(organization_id: str | None = None) -> dict[str, Any]:
        rows = ComplianceRepository.list_rows("compliance_run", organization_id, 1)
        return rows[0] if rows else {}

    @staticmethod
    def history(organization_id: str | None = None, table_name: str = "compliance_run", limit: int = 30) -> list[dict[str, Any]]:
        return ComplianceRepository.list_rows(table_name, organization_id, limit)

    @staticmethod
    def list_rows(table_name: str, organization_id: str | None = None, limit: int = 200) -> list[dict[str, Any]]:
        org_id = resolve_organization_id(organization_id)
        memory = [
            row
            for row in ComplianceRepository._MEMORY.get(table_name, [])
            if row.get("organization_id") == org_id
        ][:limit]
        if memory or not ComplianceRepository._PERSIST:
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
    def _memory_upsert(table_name: str, payload: dict[str, Any], keys: tuple[str, ...]) -> None:
        rows = ComplianceRepository._MEMORY.setdefault(table_name, [])
        for index, row in enumerate(rows):
            if all(row.get(key) == payload.get(key) for key in keys):
                rows[index] = {**row, **payload}
                return
        rows.insert(0, payload)

    @staticmethod
    def _persist_insert(table_name: str, payload: dict[str, Any]) -> None:
        if not ComplianceRepository._PERSIST:
            return
        try:
            supabase.table(table_name).insert(payload).execute()
        except Exception:
            return

    @staticmethod
    def _persist_upsert(table_name: str, payload: dict[str, Any], on_conflict: str) -> None:
        if not ComplianceRepository._PERSIST:
            return
        try:
            supabase.table(table_name).upsert(payload, on_conflict=on_conflict).execute()
        except Exception:
            return
