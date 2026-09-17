import streamlit as st

from services.supabase_client import supabase


class CostIntelligenceRepository:
    @staticmethod
    def get_enterprise_spend():
        from services.enterprise_spend_composition import (
            authenticated_tenant_context,
            enterprise_spend_service,
        )
        from services.financial_read_models import enterprise_spend_read_model

        context = authenticated_tenant_context(st.session_state)
        model = enterprise_spend_read_model(context, enterprise_spend_service())
        return {
            "total_spend": model.total.value,
            "cloud_spend": model.cloud.value,
            "currency": model.total.currency,
            "availability": model.total.availability,
            "provenance": model.total.provenance,
        }

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
            supabase.table("mart_optimization_opportunities")
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
