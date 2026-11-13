import streamlit as st

from auth.authenticated_tenant import AuthenticatedTenantContext
from services.supabase_client import supabase


def _tenant_rows(
    table_name: str,
    context: AuthenticatedTenantContext,
    tenant_column: str,
    order_column: str | None = None,
) -> list[dict]:
    if not isinstance(context, AuthenticatedTenantContext):
        raise TypeError("AuthenticatedTenantContext is required")
    query = (
        supabase.tenant_table(table_name, context)
        .select("*")
        .eq(tenant_column, context.organization_id)
    )
    if order_column:
        query = query.order(order_column, desc=True)
    return query.execute().data or []


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
    def get_enterprise_forecast(context: AuthenticatedTenantContext):
        return _tenant_rows("mart_enterprise_forecast", context, "organization_id")

    @staticmethod
    @st.cache_data(ttl=300)
    def get_cost_trend(context: AuthenticatedTenantContext):
        return _tenant_rows("mart_cost_trend", context, "organization_id")

    @staticmethod
    @st.cache_data(ttl=300)
    def get_cost_forecast(context: AuthenticatedTenantContext):
        return _tenant_rows("mart_cost_forecast", context, "organization_id")

    @staticmethod
    @st.cache_data(ttl=300)
    def get_cost_anomalies(context: AuthenticatedTenantContext):
        return _tenant_rows("mart_cost_anomalies", context, "org_id")

    @staticmethod
    @st.cache_data(ttl=300)
    def get_optimization_opportunities(context: AuthenticatedTenantContext):
        return _tenant_rows(
            "mart_optimization_opportunities",
            context,
            "org_id",
            order_column="total_cost",
        )

    @staticmethod
    @st.cache_data(ttl=300)
    def get_recommendations(context: AuthenticatedTenantContext):
        return _tenant_rows("recommendations", context, "org_id")
