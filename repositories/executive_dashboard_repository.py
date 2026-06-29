from services.supabase_client import supabase
import streamlit as st


class ExecutiveDashboardRepository:

    @staticmethod
    @st.cache_data(ttl=300)
    def get_executive_summary():
        # Executive marts are enterprise-level snapshots and are intentionally unscoped.
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
        # Enterprise spend mart is currently a global snapshot.
        response = (
            supabase
            .table("mart_enterprise_spend_v2")
            .select("*")
            .limit(1)
            .execute()
        )
        return response.data[0] if response.data else {}

    @staticmethod
    @st.cache_data(ttl=300)
    def get_budget_vs_actual():
        # Budget mart is currently a global enterprise snapshot.
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
        # Forecast mart is currently a global enterprise snapshot.
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
        # Savings mart is currently a global enterprise snapshot.
        response = (
            supabase
            .table("mart_savings")
            .select("*")
            .limit(1)
            .execute()
        )
        return response.data[0] if response.data else {}
