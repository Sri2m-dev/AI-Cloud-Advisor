import streamlit as st

from services.supabase_client import supabase


class BusinessServiceCostRepository:
    @staticmethod
    def _fetch_table(table_name: str):
        try:
            response = supabase.table(table_name).select("*").execute()
            return response.data or []
        except Exception:
            return []

    @staticmethod
    @st.cache_data(ttl=300)
    def get_business_services():
        return BusinessServiceCostRepository._fetch_table("business_services")

    @staticmethod
    @st.cache_data(ttl=300)
    def get_application_mappings():
        return []

    @staticmethod
    @st.cache_data(ttl=300)
    def get_application_spend():
        return []

    @staticmethod
    @st.cache_data(ttl=300)
    def get_technology_inventory():
        return []

    @staticmethod
    @st.cache_data(ttl=300)
    def get_service_relationships():
        return BusinessServiceCostRepository._fetch_table("business_service_relationships")

    @staticmethod
    @st.cache_data(ttl=300)
    def get_application_spend_mapping():
        return []
