from services.supabase_client import supabase
import streamlit as st


class LeadershipDashboardRepository:

    @staticmethod
    @st.cache_data(ttl=300)
    def get_enterprise_spend():
        response = supabase.table("mart_enterprise_spend").select("*").limit(1).execute()
        return response.data[0] if response.data else {}

    @staticmethod
    @st.cache_data(ttl=300)
    def get_enterprise_spend_breakdown():
        response = supabase.table("mart_enterprise_spend_breakdown").select("*").limit(1).execute()
        return response.data[0] if response.data else {}

    @staticmethod
    @st.cache_data(ttl=300)
    def get_savings():
        response = supabase.table("mart_savings").select("*").limit(1).execute()
        return response.data[0] if response.data else {}

    @staticmethod
    @st.cache_data(ttl=300)
    def get_approval_requests():
        response = supabase.table("approval_requests").select("*").execute()
        return response.data or []

    @staticmethod
    @st.cache_data(ttl=300)
    def get_optimization_opportunities():
        response = (
            supabase
            .table("mart_optimization_opportunities")
            .select("*")
            .order("total_cost", desc=True)
            .limit(10)
            .execute()
        )
        return response.data or []

    @staticmethod
    @st.cache_data(ttl=300)
    def get_cost_anomalies():
        response = supabase.table("mart_cost_anomalies").select("*").limit(20).execute()
        return response.data or []

    @staticmethod
    @st.cache_data(ttl=300)
    def get_recommendations():
        response = supabase.table("recommendations").select("*").limit(20).execute()
        return response.data or []