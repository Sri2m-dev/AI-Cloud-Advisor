import streamlit as st

from services.supabase_client import supabase


class ApplicationPortfolioRepository:
    @staticmethod
    def _fetch_table(table_name: str):
        try:
            response = supabase.table(table_name).select("*").execute()
            return response.data or []
        except Exception:
            return []

    @staticmethod
    def get_applications():
        return []

    @staticmethod
    @st.cache_data(ttl=300)
    def get_application_spend():
        return []

    @staticmethod
    @st.cache_data(ttl=300)
    def get_application_dependencies():
        return ApplicationPortfolioRepository._fetch_table("business_service_relationships")

    @staticmethod
    @st.cache_data(ttl=300)
    def get_application_risks():
        return ApplicationPortfolioRepository._fetch_table("technology_relationships")

    @staticmethod
    @st.cache_data(ttl=300)
    def get_unallocated_spend():
        return []

    @staticmethod
    @st.cache_data(ttl=300)
    def get_application_spend_mapping():
        return []
