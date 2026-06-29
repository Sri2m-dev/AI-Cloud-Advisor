from __future__ import annotations

from typing import Any

import streamlit as st

from services.supabase_client import supabase


class AIGovernanceRepository:
    @staticmethod
    def _fetch_ai_inventory() -> list[dict[str, Any]]:
        try:
            response = (
                supabase.table("technology_inventory")
                .select("*")
                .eq("technology_type", "AI")
                .execute()
            )
            return response.data or []
        except Exception:
            return []

    @staticmethod
    @st.cache_data(ttl=300)
    def get_ai_tools() -> list[dict[str, Any]]:
        return AIGovernanceRepository._fetch_ai_inventory()

    @staticmethod
    @st.cache_data(ttl=300)
    def get_ai_spend() -> list[dict[str, Any]]:
        return AIGovernanceRepository._fetch_ai_inventory()

    @staticmethod
    @st.cache_data(ttl=300)
    def get_ai_vendors() -> list[dict[str, Any]]:
        return AIGovernanceRepository._fetch_ai_inventory()

    @staticmethod
    @st.cache_data(ttl=300)
    def get_ai_license_summary() -> list[dict[str, Any]]:
        return AIGovernanceRepository._fetch_ai_inventory()

    @staticmethod
    @st.cache_data(ttl=300)
    def get_ai_risk_summary() -> list[dict[str, Any]]:
        return AIGovernanceRepository._fetch_ai_inventory()
