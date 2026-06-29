import streamlit as st

from services.supabase_client import supabase


class TechnologyHealthRepository:

    @staticmethod
    @st.cache_data(ttl=300)
    def get_technology_inventory():
        try:
            response = (
                supabase
                .table("technology_inventory")
                .select("*")
                .execute()
            )
            return response.data or []
        except Exception:
            return []

    @staticmethod
    @st.cache_data(ttl=300)
    def get_technology_relationships():
        try:
            response = (
                supabase
                .table("technology_relationships")
                .select("*")
                .execute()
            )
            return response.data or []
        except Exception:
            return []

    @staticmethod
    @st.cache_data(ttl=300)
    def get_vendor_spend():
        try:
            response = (
                supabase
                .table("vw_vendor_spend")
                .select("*")
                .execute()
            )
            return response.data or []
        except Exception:
            return []

    @staticmethod
    @st.cache_data(ttl=300)
    def get_renewal_risks():
        try:
            response = (
                supabase
                .table("vw_saas_renewal_risk")
                .select("*")
                .execute()
            )
            return response.data or []
        except Exception:
            return []

    @staticmethod
    @st.cache_data(ttl=300)
    def get_inactive_saas_users():
        try:
            response = (
                supabase
                .table("vw_inactive_saas_users")
                .select("*")
                .execute()
            )
            return response.data or []
        except Exception:
            return []
