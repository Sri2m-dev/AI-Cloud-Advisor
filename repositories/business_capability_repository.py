from __future__ import annotations

from typing import Any

import streamlit as st

from services.supabase_client import supabase


class BusinessCapabilityRepository:
    """Repository for the E7.1 enterprise business capability foundation."""

    @staticmethod
    def _fetch_table(table_name: str) -> list[dict[str, Any]]:
        try:
            response = supabase.table(table_name).select("*").execute()
            return response.data or []
        except Exception:
            return []

    @staticmethod
    @st.cache_data(ttl=300)
    def get_business_capabilities() -> list[dict[str, Any]]:
        return BusinessCapabilityRepository._fetch_table("business_capabilities")

    @staticmethod
    @st.cache_data(ttl=300)
    def get_business_services() -> list[dict[str, Any]]:
        return BusinessCapabilityRepository._fetch_table("business_services")

    @staticmethod
    @st.cache_data(ttl=300)
    def get_application_registry() -> list[dict[str, Any]]:
        return BusinessCapabilityRepository._fetch_table("application_registry")

    @staticmethod
    @st.cache_data(ttl=300)
    def get_application_spend() -> list[dict[str, Any]]:
        return BusinessCapabilityRepository._fetch_table("mart_application_spend")

    @staticmethod
    @st.cache_data(ttl=300)
    def get_business_service_relationships() -> list[dict[str, Any]]:
        return BusinessCapabilityRepository._fetch_table("business_service_relationships")
