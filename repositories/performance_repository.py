from __future__ import annotations

import os
import uuid
from typing import Any

from connectors.common.tenant_guard import resolve_organization_id
from services.supabase_client import supabase


class PerformanceRepository:
    _PERSIST = os.getenv("NEXORA_PERFORMANCE_DB", "").lower() in {"1", "true", "yes"}
    _MEMORY: dict[str, list[dict[str, Any]]] = {
        "performance_run": [],
        "performance_metric": [],
        "performance_benchmark": [],
        "performance_bottleneck": [],
        "performance_recommendation": [],
        "cache_metric": [],
        "load_test_result": [],
        "slow_query_log": [],
        "throughput_metric": [],
    }

    @staticmethod
    def save_run(row: dict[str, Any]) -> dict[str, Any]:
        payload = PerformanceRepository._scoped(row)
        payload.setdefault("id", str(uuid.uuid4()))
        PerformanceRepository._memory_upsert("performance_run", payload, ("organization_id", "id"))
        PerformanceRepository._persist_upsert("performance_run", payload, "organization_id,id")
        return payload

    @staticmethod
    def insert_metrics(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return PerformanceRepository.insert_rows("performance_metric", rows)

    @staticmethod
    def insert_benchmarks(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return PerformanceRepository.insert_rows("performance_benchmark", rows)

    @staticmethod
    def insert_bottlenecks(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return PerformanceRepository.insert_rows("performance_bottleneck", rows)

    @staticmethod
    def insert_recommendations(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return PerformanceRepository.insert_rows("performance_recommendation", rows)

    @staticmethod
    def insert_cache_metrics(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return PerformanceRepository.insert_rows("cache_metric", rows)

    @staticmethod
    def insert_load_tests(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return PerformanceRepository.insert_rows("load_test_result", rows)

    @staticmethod
    def insert_slow_queries(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return PerformanceRepository.insert_rows("slow_query_log", rows)

    @staticmethod
    def insert_throughput(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return PerformanceRepository.insert_rows("throughput_metric", rows)

    @staticmethod
    def latest_run(organization_id: str | None = None) -> dict[str, Any]:
        rows = PerformanceRepository.list_rows("performance_run", organization_id, 1)
        return rows[0] if rows else {}

    @staticmethod
    def history(organization_id: str | None = None, limit: int = 30) -> list[dict[str, Any]]:
        return PerformanceRepository.list_rows("performance_run", organization_id, limit)

    @staticmethod
    def insert_row(table_name: str, row: dict[str, Any]) -> dict[str, Any]:
        payload = PerformanceRepository._scoped(row)
        payload.setdefault("id", str(uuid.uuid4()))
        PerformanceRepository._MEMORY.setdefault(table_name, []).insert(0, payload)
        PerformanceRepository._persist_insert(table_name, payload)
        return payload

    @staticmethod
    def insert_rows(table_name: str, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [PerformanceRepository.insert_row(table_name, row) for row in rows]

    @staticmethod
    def list_rows(table_name: str, organization_id: str | None = None, limit: int = 200) -> list[dict[str, Any]]:
        org_id = resolve_organization_id(organization_id)
        memory = [
            row
            for row in PerformanceRepository._MEMORY.get(table_name, [])
            if row.get("organization_id") == org_id
        ][:limit]
        if memory or not PerformanceRepository._PERSIST:
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
        rows = PerformanceRepository._MEMORY.setdefault(table_name, [])
        for index, row in enumerate(rows):
            if all(row.get(key) == payload.get(key) for key in keys):
                rows[index] = {**row, **payload}
                return
        rows.insert(0, payload)

    @staticmethod
    def _persist_insert(table_name: str, payload: dict[str, Any]) -> None:
        if not PerformanceRepository._PERSIST:
            return
        try:
            supabase.table(table_name).insert(payload).execute()
        except Exception:
            return

    @staticmethod
    def _persist_upsert(table_name: str, payload: dict[str, Any], on_conflict: str) -> None:
        if not PerformanceRepository._PERSIST:
            return
        try:
            supabase.table(table_name).upsert(payload, on_conflict=on_conflict).execute()
        except Exception:
            return
