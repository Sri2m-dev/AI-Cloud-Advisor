from __future__ import annotations

from typing import Any

import streamlit as st

from services.supabase_client import supabase


class SavingsGovernanceRepository:
    @staticmethod
    def _fetch_table(table_name: str) -> list[dict[str, Any]]:
        try:
            response = supabase.table(table_name).select("*").execute()
            return response.data or []
        except Exception:
            return []

    @staticmethod
    @st.cache_data(ttl=300)
    def get_optimization_pipeline() -> list[dict[str, Any]]:
        rows = SavingsGovernanceRepository._fetch_table("recommendations")
        opportunities = SavingsGovernanceRepository._fetch_table("mart_optimization_opportunities")
        return rows or opportunities

    @staticmethod
    @st.cache_data(ttl=300)
    def get_realized_savings() -> list[dict[str, Any]]:
        return SavingsGovernanceRepository._fetch_table("mart_savings")

    @staticmethod
    @st.cache_data(ttl=300)
    def get_savings_by_owner() -> list[dict[str, Any]]:
        rows = SavingsGovernanceRepository._fetch_table("recommendations")
        return rows or SavingsGovernanceRepository._fetch_table("mart_optimization_opportunities")

    @staticmethod
    @st.cache_data(ttl=300)
    def get_savings_by_domain() -> list[dict[str, Any]]:
        rows = SavingsGovernanceRepository._fetch_table("mart_optimization_opportunities")
        return rows or SavingsGovernanceRepository._fetch_table("recommendations")

    @staticmethod
    @st.cache_data(ttl=300)
    def get_savings_trend() -> list[dict[str, Any]]:
        return SavingsGovernanceRepository._fetch_table("mart_savings")

    @staticmethod
    @st.cache_data(ttl=300)
    def get_implementation_backlog() -> list[dict[str, Any]]:
        recommendations = SavingsGovernanceRepository._fetch_table("recommendations")
        approvals = SavingsGovernanceRepository._fetch_table("approval_queue")
        audit = SavingsGovernanceRepository._fetch_table("audit_timeline")
        return recommendations or approvals or audit
