from __future__ import annotations

from typing import Any

from connectors.common.tenant_guard import resolve_organization_id
from services.supabase_client import supabase


class ImpactRepository:
    ORG_TABLES = (
        "technology_relationships",
        "application_spend_mapping",
        "approval_queue",
        "approval_requests",
        "workflow_history",
        "ai_workflow_actions",
        "audit_events",
        "execution_log",
    )

    GLOBAL_TABLES = (
        "technology_inventory",
        "application_registry",
        "application_master",
        "business_services",
        "cost_recommendations",
        "ai_recommendation_history",
        "vw_vendor_spend",
        "vw_department_spend",
    )

    @staticmethod
    def load_context(organization_id: str | None = None) -> dict[str, Any]:
        org_id = resolve_organization_id(organization_id)
        context: dict[str, Any] = {"organization_id": org_id}
        for table in ImpactRepository.ORG_TABLES:
            context[table] = ImpactRepository._fetch_table(table, org_id)
        for table in ImpactRepository.GLOBAL_TABLES:
            context[table] = ImpactRepository._fetch_table(table)
        return context

    @staticmethod
    def get_cached_analysis(
        asset_id: str,
        asset_type: str,
        organization_id: str | None = None,
    ) -> dict[str, Any] | None:
        org_id = resolve_organization_id(organization_id)
        try:
            rows = (
                supabase.table("impact_analysis_cache")
                .select("*")
                .eq("organization_id", org_id)
                .eq("asset_id", asset_id)
                .eq("asset_type", asset_type)
                .order("generated_at", desc=True)
                .limit(1)
                .execute()
                .data
                or []
            )
            return rows[0] if rows else None
        except Exception:
            return None

    @staticmethod
    def save_cached_analysis(payload: dict[str, Any]) -> bool:
        try:
            supabase.table("impact_analysis_cache").upsert(
                payload,
                on_conflict="organization_id,asset_id,asset_type",
            ).execute()
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
