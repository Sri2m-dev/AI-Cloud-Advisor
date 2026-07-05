from __future__ import annotations

from typing import Any

import streamlit as st

from services.supabase_client import supabase


class BusinessProcessRepository:
    """Repository for the E7.1.8 enterprise business process foundation."""

    @staticmethod
    def _fetch_table(table_name: str) -> list[dict[str, Any]]:
        try:
            response = supabase.table(table_name).select("*").execute()
            return response.data or []
        except Exception:
            return []

    @staticmethod
    @st.cache_data(ttl=300)
    def get_business_processes() -> list[dict[str, Any]]:
        return BusinessProcessRepository._fetch_table("business_processes")

    @staticmethod
    @st.cache_data(ttl=300)
    def get_business_services() -> list[dict[str, Any]]:
        return BusinessProcessRepository._fetch_table("business_services")

    @staticmethod
    @st.cache_data(ttl=300)
    def get_application_registry() -> list[dict[str, Any]]:
        return BusinessProcessRepository._fetch_table("application_registry")

    @staticmethod
    @st.cache_data(ttl=300)
    def get_application_spend() -> list[dict[str, Any]]:
        return BusinessProcessRepository._fetch_table("mart_application_spend")

    @staticmethod
    @st.cache_data(ttl=300)
    def get_technology_inventory() -> list[dict[str, Any]]:
        return BusinessProcessRepository._fetch_table("technology_inventory")

    @staticmethod
    @st.cache_data(ttl=300)
    def get_technology_relationships() -> list[dict[str, Any]]:
        return BusinessProcessRepository._fetch_table("technology_relationships")

    @staticmethod
    @st.cache_data(ttl=300)
    def get_recommendations() -> list[dict[str, Any]]:
        return BusinessProcessRepository._fetch_table("recommendations")
