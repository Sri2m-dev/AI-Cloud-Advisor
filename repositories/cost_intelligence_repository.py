from services.supabase_client import supabase
import streamlit as st


class CostIntelligenceRepository:

    @staticmethod
    @st.cache_data(ttl=300)
    def get_enterprise_spend():
        response = supabase.table("mart_enterprise_spend").select("*").limit(1).execute()
        return response.data[0] if response.data else {}

    @staticmethod
    @st.cache_data(ttl=300)
    def get_enterprise_forecast():
        response = supabase.table("mart_enterprise_forecast").select("*").execute()
        return response.data or []

    @staticmethod
    @st.cache_data(ttl=300)
    def get_cost_trend():
        response = supabase.table("mart_cost_trend").select("*").execute()
        return response.data or []

    @staticmethod
    @st.cache_data(ttl=300)
    def get_cost_forecast():
        response = supabase.table("mart_cost_forecast").select("*").execute()
        return response.data or []

    @staticmethod
    @st.cache_data(ttl=300)
    def get_cost_anomalies():
        response = supabase.table("mart_cost_anomalies").select("*").execute()
        return response.data or []

    @staticmethod
    @st.cache_data(ttl=300)
    def get_optimization_opportunities():
        response = (
            supabase
            .table("mart_optimization_opportunities")
            .select("*")
            .order("total_cost", desc=True)
            .execute()
        )
        return response.data or []

    @staticmethod
    @st.cache_data(ttl=300)
    def get_recommendations():
        response = supabase.table("recommendations").select("*").execute()
        return response.data or []
