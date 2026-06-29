from __future__ import annotations

from functools import lru_cache
from typing import Any

from connectors.common.tenant_guard import resolve_organization_id
from services.supabase_client import supabase


class ForecastingRepository:
    TABLES = (
        "mart_enterprise_spend",
        "mart_enterprise_spend_v2",
        "mart_enterprise_forecast",
        "mart_cost_trend",
        "mart_cost_forecast",
        "mart_budget_vs_actual",
        "technology_inventory",
        "application_spend_mapping",
        "business_services",
        "vw_vendor_spend",
        "vw_department_spend",
        "vw_saas_renewal_risk",
        "vw_inactive_saas_users",
        "enterprise_cost_attribution",
        "impact_analysis_cache",
        "simulation_results",
        "ai_reasoning_history",
    )

    @staticmethod
    def load_context(organization_id: str | None = None) -> dict[str, Any]:
        org_id = resolve_organization_id(organization_id)
        return ForecastingRepository._cached_context(org_id)

    @staticmethod
    @lru_cache(maxsize=16)
    def _cached_context(org_id: str) -> dict[str, Any]:
        context: dict[str, Any] = {"organization_id": org_id}
        for table in ForecastingRepository.TABLES:
            context[table] = ForecastingRepository._fetch_table(table, org_id)
        return context

    @staticmethod
    def save_forecast(table_name: str, payload: dict[str, Any]) -> bool:
        try:
            supabase.table(table_name).insert(payload).execute()
            return True
        except Exception:
            return False

    @staticmethod
    def list_forecasts(table_name: str, organization_id: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
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

    @staticmethod
    def _fetch_table(table_name: str, organization_id: str | None = None, limit: int = 1000) -> list[dict[str, Any]]:
        try:
            query = supabase.table(table_name).select("*")
            if organization_id:
                query = query.eq("organization_id", organization_id)
            return query.limit(limit).execute().data or []
        except Exception:
            if organization_id:
                try:
                    return supabase.table(table_name).select("*").limit(limit).execute().data or []
                except Exception:
                    return []
            return []
