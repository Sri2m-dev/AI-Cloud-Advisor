from __future__ import annotations

from typing import Any

from connectors.common.tenant_guard import resolve_organization_id
from services.supabase_client import supabase


class PredictivePerformanceRepository:
    TABLES = (
        "forecast_history",
        "forecast_actuals",
        "prediction_accuracy",
        "model_registry",
        "model_versions",
        "forecast_drift",
        "prediction_confidence_history",
        "capacity_forecast",
        "budget_forecast",
        "risk_forecast",
    )

    @staticmethod
    def list_rows(table_name: str, organization_id: str | None = None, limit: int = 200) -> list[dict[str, Any]]:
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
            try:
                return (
                    supabase.table(table_name)
                    .select("*")
                    .order("created_at", desc=True)
                    .limit(limit)
                    .execute()
                    .data
                    or []
                )
            except Exception:
                return []

    @staticmethod
    def insert_row(table_name: str, payload: dict[str, Any]) -> bool:
        try:
            supabase.table(table_name).insert(payload).execute()
            return True
        except Exception:
            return False
