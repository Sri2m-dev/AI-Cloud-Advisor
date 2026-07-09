from __future__ import annotations

from typing import Any

import streamlit as st

from services.supabase_client import supabase


class BusinessServiceRepository:
    """Repository for the E7.1 enterprise business service foundation."""

    @staticmethod
    def _fetch_table(table_name: str) -> list[dict[str, Any]]:
        try:
            response = supabase.table(table_name).select("*").execute()
            return response.data or []
        except Exception:
            return []

    @staticmethod
    @st.cache_data(ttl=300)
    def get_business_services() -> list[dict[str, Any]]:
        return BusinessServiceRepository._fetch_table("business_services")

    @staticmethod
    def get_business_service(service_id: str) -> dict[str, Any] | None:
        service_key = str(service_id or "").strip().lower()
        if not service_key:
            return None

        for row in BusinessServiceRepository.get_business_services():
            candidates = [
                row.get("id"),
                row.get("service_id"),
                row.get("service_code"),
                row.get("service_name"),
                row.get("business_service_name"),
                row.get("name"),
            ]
            if service_key in {str(value or "").strip().lower() for value in candidates}:
                return row
        return None

    @staticmethod
    @st.cache_data(ttl=300)
    def get_business_service_relationships() -> list[dict[str, Any]]:
        return BusinessServiceRepository._fetch_table("business_service_relationships")

    @staticmethod
    @st.cache_data(ttl=300)
    def get_application_registry() -> list[dict[str, Any]]:
        return BusinessServiceRepository._fetch_table("application_registry")

    @staticmethod
    @st.cache_data(ttl=300)
    def get_application_spend_mapping() -> list[dict[str, Any]]:
        return BusinessServiceRepository._fetch_table("application_spend_mapping")

    @staticmethod
    @st.cache_data(ttl=300)
    def get_application_spend() -> list[dict[str, Any]]:
        return BusinessServiceRepository._fetch_table("mart_application_spend")

    @staticmethod
    @st.cache_data(ttl=300)
    def get_technology_inventory() -> list[dict[str, Any]]:
        return BusinessServiceRepository._fetch_table("technology_inventory")

    @staticmethod
    @st.cache_data(ttl=300)
    def get_technology_relationships() -> list[dict[str, Any]]:
        return BusinessServiceRepository._fetch_table("technology_relationships")

    @staticmethod
    @st.cache_data(ttl=300)
    def get_recommendations() -> list[dict[str, Any]]:
        return BusinessServiceRepository._fetch_table("recommendations")

    @staticmethod
    @st.cache_data(ttl=300)
    def get_approval_queue() -> list[dict[str, Any]]:
        return BusinessServiceRepository._fetch_table("approval_queue")

    @staticmethod
    @st.cache_data(ttl=300)
    def get_savings() -> list[dict[str, Any]]:
        return BusinessServiceRepository._fetch_table("mart_savings")

    @staticmethod
    @st.cache_data(ttl=300)
    def get_operations_events() -> list[dict[str, Any]]:
        return BusinessServiceRepository._fetch_table("operations_events")
