import streamlit as st

from services.supabase_client import supabase


class SaaSIntelligenceRepository:
    @staticmethod
    def _fetch_table(table_name: str):
        try:
            response = supabase.table(table_name).select("*").execute()
            return response.data or []
        except Exception:
            return []

    @staticmethod
    @st.cache_data(ttl=300)
    def get_saas_inventory():
        return SaaSIntelligenceRepository._fetch_table("technology_inventory")

    @staticmethod
    @st.cache_data(ttl=300)
    def get_saas_costs():
        return SaaSIntelligenceRepository._fetch_table("saas_cost")

    @staticmethod
    @st.cache_data(ttl=300)
    def get_license_costs():
        return SaaSIntelligenceRepository._fetch_table("license_cost")

    @staticmethod
    @st.cache_data(ttl=300)
    def get_inactive_users():
        return SaaSIntelligenceRepository._fetch_table("vw_inactive_saas_users")

    @staticmethod
    @st.cache_data(ttl=300)
    def get_renewal_risk():
        return SaaSIntelligenceRepository._fetch_table("vw_saas_renewal_risk")

    @staticmethod
    def get_renewal_risks():
        return SaaSIntelligenceRepository.get_renewal_risk()

    @staticmethod
    def get_technology_inventory():
        return SaaSIntelligenceRepository.get_saas_inventory()
