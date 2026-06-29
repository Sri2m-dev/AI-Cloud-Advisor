from __future__ import annotations

import os
import uuid
from typing import Any

from connectors.common.tenant_guard import resolve_organization_id
from services.supabase_client import supabase


class DataQualityRepository:
    _PERSIST = os.getenv("NEXORA_DATA_QUALITY_DB", "").lower() in {"1", "true", "yes"}
    _MEMORY: dict[str, list[dict[str, Any]]] = {
        "data_quality_run": [],
        "data_quality_result": [],
        "data_quality_rule": [],
        "data_quality_issue": [],
        "data_quality_recommendation": [],
        "data_freshness": [],
        "ai_trust_score": [],
        "graph_validation": [],
        "telemetry_validation": [],
        "cost_validation": [],
        "enterprise_event_bus": [],
    }

    @staticmethod
    def save_run(row: dict[str, Any]) -> dict[str, Any]:
        payload = DataQualityRepository._scoped(row)
        payload.setdefault("id", str(uuid.uuid4()))
        DataQualityRepository._memory_upsert("data_quality_run", payload, ("organization_id", "id"))
        DataQualityRepository._persist_upsert("data_quality_run", payload, "organization_id,id")
        return payload

    @staticmethod
    def insert_results(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return DataQualityRepository.insert_rows("data_quality_result", rows)

    @staticmethod
    def insert_rules(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return DataQualityRepository.insert_rows("data_quality_rule", rows)

    @staticmethod
    def insert_issues(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return DataQualityRepository.insert_rows("data_quality_issue", rows)

    @staticmethod
    def insert_recommendations(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return DataQualityRepository.insert_rows("data_quality_recommendation", rows)

    @staticmethod
    def insert_freshness(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return DataQualityRepository.insert_rows("data_freshness", rows)

    @staticmethod
    def insert_ai_trust_score(row: dict[str, Any]) -> dict[str, Any]:
        return DataQualityRepository.insert_row("ai_trust_score", row)

    @staticmethod
    def insert_graph_validation(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return DataQualityRepository.insert_rows("graph_validation", rows)

    @staticmethod
    def insert_telemetry_validation(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return DataQualityRepository.insert_rows("telemetry_validation", rows)

    @staticmethod
    def insert_cost_validation(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return DataQualityRepository.insert_rows("cost_validation", rows)

    @staticmethod
    def publish_events(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return DataQualityRepository.insert_rows("enterprise_event_bus", rows)

    @staticmethod
    def latest_run(organization_id: str | None = None) -> dict[str, Any]:
        rows = DataQualityRepository.list_rows("data_quality_run", organization_id, 1)
        return rows[0] if rows else {}

    @staticmethod
    def history(organization_id: str | None = None, limit: int = 30) -> list[dict[str, Any]]:
        return DataQualityRepository.list_rows("data_quality_run", organization_id, limit)

    @staticmethod
    def insert_row(table_name: str, row: dict[str, Any]) -> dict[str, Any]:
        payload = DataQualityRepository._scoped(row)
        payload.setdefault("id", str(uuid.uuid4()))
        DataQualityRepository._MEMORY.setdefault(table_name, []).insert(0, payload)
        DataQualityRepository._persist_insert(table_name, payload)
        return payload

    @staticmethod
    def insert_rows(table_name: str, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [DataQualityRepository.insert_row(table_name, row) for row in rows]

    @staticmethod
    def list_rows(table_name: str, organization_id: str | None = None, limit: int = 200) -> list[dict[str, Any]]:
        org_id = resolve_organization_id(organization_id)
        memory = [
            row
            for row in DataQualityRepository._MEMORY.get(table_name, [])
            if row.get("organization_id") == org_id
        ][:limit]
        if memory or not DataQualityRepository._PERSIST:
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
        rows = DataQualityRepository._MEMORY.setdefault(table_name, [])
        for index, row in enumerate(rows):
            if all(row.get(key) == payload.get(key) for key in keys):
                rows[index] = {**row, **payload}
                return
        rows.insert(0, payload)

    @staticmethod
    def _persist_insert(table_name: str, payload: dict[str, Any]) -> None:
        if not DataQualityRepository._PERSIST:
            return
        try:
            supabase.table(table_name).insert(payload).execute()
        except Exception:
            return

    @staticmethod
    def _persist_upsert(table_name: str, payload: dict[str, Any], on_conflict: str) -> None:
        if not DataQualityRepository._PERSIST:
            return
        try:
            supabase.table(table_name).upsert(payload, on_conflict=on_conflict).execute()
        except Exception:
            return
