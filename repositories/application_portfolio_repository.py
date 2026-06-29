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
        try:
            response = (
                supabase
                .table("application_registry")
                .select(
                    "app_code,app_name,business_unit,department,team_name,"
                    "owner_name,owner_email,environment,criticality,cloud_provider,"
                    "cost_center,allocation_enabled,active"
                )
                .eq("active", True)
                .execute()
            )
            return response.data or []
        except Exception:
            return []

    @staticmethod
    @st.cache_data(ttl=300)
    def get_application_spend():
        return ApplicationPortfolioRepository._fetch_table("mart_application_spend")

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
        return ApplicationPortfolioRepository._fetch_table("technology_inventory")

    @staticmethod
    @st.cache_data(ttl=300)
    def get_application_spend_mapping():
        return ApplicationPortfolioRepository._fetch_table("application_spend_mapping")
