"""Organization-scoped data access for leadership dashboards."""

from __future__ import annotations

from typing import Any

import streamlit as st

from services.supabase_client import supabase


ORGANIZATION_COLUMN = "organization_id"


def _require_organization_id(organization_id: str) -> str:
    value = str(organization_id or "").strip()
    if not value:
        raise ValueError("organization_id is required for leadership dashboard queries")
    return value


def _safe_data(query) -> list[dict[str, Any]]:
    try:
        response = query.execute()
        return response.data or []
    except Exception:
        return []


class LeadershipDashboardRepository:
    @staticmethod
    @st.cache_data(ttl=300, show_spinner=False)
    def fetch_cost_rows(organization_id: str) -> list[dict[str, Any]]:
        organization_id = _require_organization_id(organization_id)
        return _safe_data(
            supabase.table("unified_cloud_costs")
            .select("cloud,service_name,cost,amount,usage_date")
            .eq(ORGANIZATION_COLUMN, organization_id)
        )

    @staticmethod
    @st.cache_data(ttl=300, show_spinner=False)
    def fetch_recommendations(organization_id: str) -> list[dict[str, Any]]:
        organization_id = _require_organization_id(organization_id)
        return _safe_data(
            supabase.table("recommendations")
            .select("id,title,status,estimated_savings,recommendation_type,type,priority,created_at,updated_at")
            .eq(ORGANIZATION_COLUMN, organization_id)
        )

    @staticmethod
    @st.cache_data(ttl=300, show_spinner=False)
    def fetch_approvals(organization_id: str) -> list[dict[str, Any]]:
        organization_id = _require_organization_id(organization_id)
        return _safe_data(
            supabase.table("approval_queue")
            .select("id,status,created_at,completed_at,approved_at,rejected_at,updated_at,sla_due")
            .eq(ORGANIZATION_COLUMN, organization_id)
        )

    @staticmethod
    @st.cache_data(ttl=300, show_spinner=False)
    def fetch_security_findings(organization_id: str) -> list[dict[str, Any]]:
        organization_id = _require_organization_id(organization_id)
        return _safe_data(
            supabase.table("security_findings")
            .select("id,severity,status,created_at,updated_at")
            .eq(ORGANIZATION_COLUMN, organization_id)
        )

    @staticmethod
    @st.cache_data(ttl=300, show_spinner=False)
    def fetch_workspace_health(organization_id: str) -> list[dict[str, Any]]:
        organization_id = _require_organization_id(organization_id)
        return _safe_data(
            supabase.table("workspace_health_status")
            .select("metric_name,metric_value,metric_details,component,status,latency_seconds,records_processed,error_message,recorded_at")
            .eq(ORGANIZATION_COLUMN, organization_id)
            .order("recorded_at", desc=True)
            .limit(100)
        )

    @staticmethod
    @st.cache_data(ttl=300, show_spinner=False)
    def fetch_alert_history(organization_id: str) -> list[dict[str, Any]]:
        organization_id = _require_organization_id(organization_id)
        return _safe_data(
            supabase.table("alert_history")
            .select("alert_type,severity,status,created_at")
            .eq(ORGANIZATION_COLUMN, organization_id)
            .order("created_at", desc=True)
            .limit(200)
        )

    @staticmethod
    @st.cache_data(ttl=300, show_spinner=False)
    def fetch_governance_scores(organization_id: str) -> list[dict[str, Any]]:
        organization_id = _require_organization_id(organization_id)
        return _safe_data(
            supabase.table("governance_score_history")
            .select("raw_score,smoothed_score,components,recorded_at")
            .eq(ORGANIZATION_COLUMN, organization_id)
            .order("recorded_at", desc=True)
            .limit(30)
        )

