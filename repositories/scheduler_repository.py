from __future__ import annotations

import os
import uuid
from typing import Any

from connectors.common.tenant_guard import resolve_organization_id
from services.supabase_client import supabase


class SchedulerRepository:
    _PERSIST = os.getenv("NEXORA_ENTERPRISE_SCHEDULER_DB", "").lower() in {"1", "true", "yes"}
    _MEMORY: dict[str, list[dict[str, Any]]] = {
        "scheduler_job": [],
        "scheduler_run": [],
        "scheduler_retry": [],
        "scheduler_dead_letter": [],
        "scheduler_dependency": [],
        "scheduler_rate_limit": [],
        "scheduler_operation_log": [],
    }

    @staticmethod
    def upsert_job(row: dict[str, Any]) -> dict[str, Any]:
        payload = SchedulerRepository._scoped(row)
        payload.setdefault("id", str(uuid.uuid4()))
        SchedulerRepository._memory_upsert("scheduler_job", payload, ("organization_id", "id"))
        SchedulerRepository._persist_upsert("scheduler_job", payload, "organization_id,id")
        return payload

    @staticmethod
    def get_job(job_id: str, organization_id: str | None = None) -> dict[str, Any]:
        org_id = resolve_organization_id(organization_id)
        return next(
            (
                row
                for row in SchedulerRepository._MEMORY["scheduler_job"]
                if row.get("organization_id") == org_id and row.get("id") == job_id
            ),
            {},
        )

    @staticmethod
    def list_jobs(organization_id: str | None = None, limit: int = 200) -> list[dict[str, Any]]:
        return SchedulerRepository.list_rows("scheduler_job", organization_id, limit)

    @staticmethod
    def insert_run(row: dict[str, Any]) -> dict[str, Any]:
        return SchedulerRepository.insert_row("scheduler_run", row)

    @staticmethod
    def list_runs(organization_id: str | None = None, limit: int = 200) -> list[dict[str, Any]]:
        return SchedulerRepository.list_rows("scheduler_run", organization_id, limit)

    @staticmethod
    def insert_retry(row: dict[str, Any]) -> dict[str, Any]:
        return SchedulerRepository.insert_row("scheduler_retry", row)

    @staticmethod
    def list_retries(organization_id: str | None = None, limit: int = 200) -> list[dict[str, Any]]:
        return SchedulerRepository.list_rows("scheduler_retry", organization_id, limit)

    @staticmethod
    def insert_dead_letter(row: dict[str, Any]) -> dict[str, Any]:
        return SchedulerRepository.insert_row("scheduler_dead_letter", row)

    @staticmethod
    def list_dead_letters(organization_id: str | None = None, limit: int = 200) -> list[dict[str, Any]]:
        return SchedulerRepository.list_rows("scheduler_dead_letter", organization_id, limit)

    @staticmethod
    def upsert_rate_limit(row: dict[str, Any]) -> dict[str, Any]:
        payload = SchedulerRepository._scoped(row)
        payload.setdefault("id", str(uuid.uuid4()))
        SchedulerRepository._memory_upsert("scheduler_rate_limit", payload, ("organization_id", "connector"))
        SchedulerRepository._persist_upsert("scheduler_rate_limit", payload, "organization_id,connector")
        return payload

    @staticmethod
    def list_rate_limits(organization_id: str | None = None, limit: int = 200) -> list[dict[str, Any]]:
        return SchedulerRepository.list_rows("scheduler_rate_limit", organization_id, limit)

    @staticmethod
    def upsert_dependency(row: dict[str, Any]) -> dict[str, Any]:
        payload = SchedulerRepository._scoped(row)
        payload.setdefault("id", str(uuid.uuid4()))
        SchedulerRepository._memory_upsert("scheduler_dependency", payload, ("organization_id", "stage"))
        SchedulerRepository._persist_upsert("scheduler_dependency", payload, "organization_id,stage")
        return payload

    @staticmethod
    def list_dependencies(organization_id: str | None = None, limit: int = 200) -> list[dict[str, Any]]:
        return SchedulerRepository.list_rows("scheduler_dependency", organization_id, limit)

    @staticmethod
    def insert_operation_log(row: dict[str, Any]) -> dict[str, Any]:
        return SchedulerRepository.insert_row("scheduler_operation_log", row)

    @staticmethod
    def list_operation_log(organization_id: str | None = None, limit: int = 200) -> list[dict[str, Any]]:
        return SchedulerRepository.list_rows("scheduler_operation_log", organization_id, limit)

    @staticmethod
    def insert_row(table_name: str, row: dict[str, Any]) -> dict[str, Any]:
        payload = SchedulerRepository._scoped(row)
        payload.setdefault("id", str(uuid.uuid4()))
        SchedulerRepository._MEMORY.setdefault(table_name, []).insert(0, payload)
        SchedulerRepository._persist_insert(table_name, payload)
        return payload

    @staticmethod
    def list_rows(table_name: str, organization_id: str | None = None, limit: int = 200) -> list[dict[str, Any]]:
        org_id = resolve_organization_id(organization_id)
        memory = [
            row
            for row in SchedulerRepository._MEMORY.get(table_name, [])
            if row.get("organization_id") == org_id
        ][:limit]
        if memory or not SchedulerRepository._PERSIST:
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
        rows = SchedulerRepository._MEMORY.setdefault(table_name, [])
        for index, row in enumerate(rows):
            if all(row.get(key) == payload.get(key) for key in keys):
                rows[index] = {**row, **payload}
                return
        rows.insert(0, payload)

    @staticmethod
    def _persist_insert(table_name: str, payload: dict[str, Any]) -> None:
        if not SchedulerRepository._PERSIST:
            return
        try:
            supabase.table(table_name).insert(payload).execute()
        except Exception:
            return

    @staticmethod
    def _persist_upsert(table_name: str, payload: dict[str, Any], on_conflict: str) -> None:
        if not SchedulerRepository._PERSIST:
            return
        try:
            supabase.table(table_name).upsert(payload, on_conflict=on_conflict).execute()
        except Exception:
            return
