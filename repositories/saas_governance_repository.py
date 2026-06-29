from services.supabase_client import supabase
import streamlit as st


class SaaSGovernanceRepository:

    @staticmethod
    @st.cache_data(ttl=300)
    def get_saas_cost():

        try:
            response = (
                supabase
                .table("saas_cost")
                .select("*")
                .execute()
            )
        except Exception:
            return []

        return response.data or []

    @staticmethod
    @st.cache_data(ttl=300)
    def get_license_cost():

        try:
            response = (
                supabase
                .table("license_cost")
                .select("*")
                .execute()
            )
        except Exception:
            return []

        return response.data or []
