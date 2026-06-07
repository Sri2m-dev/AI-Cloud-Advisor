from services.supabase_client import supabase
import streamlit as st


class ExecutiveDashboardRepository:

    @staticmethod
    @st.cache_data(ttl=300)
    def get_executive_summary():
        response = (
            supabase
            .table("mart_executive_summary")
            .select("*")
            .limit(1)
            .execute()
        )
        return response.data[0] if response.data else {}

    @staticmethod
    @st.cache_data(ttl=300)
    def get_enterprise_spend():
        response = (
            supabase
            .table("mart_enterprise_spend")
            .select("*")
            .limit(1)
            .execute()
        )
        return response.data[0] if response.data else {}

    @staticmethod
    @st.cache_data(ttl=300)
    def get_budget_vs_actual():
        response = (
            supabase
            .table("mart_budget_vs_actual")
            .select("*")
            .execute()
        )
        return response.data or []

    @staticmethod
    @st.cache_data(ttl=300)
    def get_spend_forecast():
        response = (
            supabase
            .table("mart_enterprise_forecast")
            .select("*")
            .execute()
        )
        return response.data or []

    @staticmethod
    @st.cache_data(ttl=300)
    def get_savings():
        response = (
            supabase
            .table("mart_savings")
            .select("*")
            .limit(1)
            .execute()
        )
        return response.data[0] if response.data else {}
