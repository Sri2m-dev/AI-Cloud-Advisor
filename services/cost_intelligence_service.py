import pandas as pd

from auth.authenticated_tenant import AuthenticatedTenantContext
from repositories.cost_intelligence_repository import (
    CostIntelligenceRepository,
)
from services.supabase_client import TenantScopeRequiredError


def _df(data):
    return pd.DataFrame(data or [])


def _tenant_result(loader, context: AuthenticatedTenantContext):
    try:
        return {"success": True, "data": _df(loader(context)), "message": ""}
    except TenantScopeRequiredError as exc:
        return {"success": False, "data": _df([]), "message": str(exc)}


def get_enterprise_spend():
    return CostIntelligenceRepository.get_enterprise_spend()


def get_enterprise_forecast(context: AuthenticatedTenantContext):
    return _tenant_result(CostIntelligenceRepository.get_enterprise_forecast, context)


def get_cost_trend(context: AuthenticatedTenantContext):
    return _tenant_result(CostIntelligenceRepository.get_cost_trend, context)


def get_cost_forecast(context: AuthenticatedTenantContext):
    return _tenant_result(CostIntelligenceRepository.get_cost_forecast, context)


def get_cost_anomalies(context: AuthenticatedTenantContext):
    return _tenant_result(CostIntelligenceRepository.get_cost_anomalies, context)


def get_optimization_opportunities(context: AuthenticatedTenantContext):
    return _tenant_result(
        CostIntelligenceRepository.get_optimization_opportunities,
        context,
    )


def get_recommendations(context: AuthenticatedTenantContext):
    return _tenant_result(CostIntelligenceRepository.get_recommendations, context)
