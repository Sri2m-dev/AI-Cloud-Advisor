from __future__ import annotations

from typing import Any

from connectors.common.tenant_guard import resolve_organization_id
from services.supabase_client import supabase


class SimulationRepository:
    ORG_TABLES = (
        "technology_relationships",
        "application_spend_mapping",
        "workflow_history",
        "approval_queue",
        "approval_requests",
        "impact_analysis_cache",
        "audit_events",
    )

    GLOBAL_TABLES = (
        "technology_inventory",
        "application_registry",
        "application_master",
        "business_services",
        "vw_vendor_spend",
    )

    @staticmethod
    def load_context(organization_id: str | None = None) -> dict[str, Any]:
        org_id = resolve_organization_id(organization_id)
        context: dict[str, Any] = {"organization_id": org_id}
        for table in SimulationRepository.ORG_TABLES:
            context[table] = SimulationRepository._fetch_table(table, org_id)
        for table in SimulationRepository.GLOBAL_TABLES:
            context[table] = SimulationRepository._fetch_table(table)
        return context

    @staticmethod
    def list_runs(organization_id: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
        org_id = resolve_organization_id(organization_id)
        try:
            return (
                supabase.table("simulation_runs")
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
    def list_results(organization_id: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
        org_id = resolve_organization_id(organization_id)
        try:
            return (
                supabase.table("simulation_results")
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
    def save_run(payload: dict[str, Any]) -> bool:
        try:
            supabase.table("simulation_runs").upsert(payload, on_conflict="id").execute()
            return True
        except Exception:
            return False

    @staticmethod
    def save_result(payload: dict[str, Any]) -> bool:
        try:
            supabase.table("simulation_results").upsert(payload, on_conflict="simulation_id").execute()
            return True
        except Exception:
            return False

    @staticmethod
    def _fetch_table(
        table_name: str,
        organization_id: str | None = None,
        limit: int = 1000,
    ) -> list[dict[str, Any]]:
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
