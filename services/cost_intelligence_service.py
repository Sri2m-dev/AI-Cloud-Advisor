import pandas as pd

from repositories.cost_intelligence_repository import (
    CostIntelligenceRepository,
)


def _df(data):
    return pd.DataFrame(data or [])


def get_enterprise_spend():
    return CostIntelligenceRepository.get_enterprise_spend()


def get_enterprise_forecast():
    return {
        "success": True,
        "data": _df(CostIntelligenceRepository.get_enterprise_forecast())
    }


def get_cost_trend():
    return {
        "success": True,
        "data": _df(CostIntelligenceRepository.get_cost_trend())
    }


def get_cost_forecast():
    return {
        "success": True,
        "data": _df(CostIntelligenceRepository.get_cost_forecast())
    }


def get_cost_anomalies():
    return {
        "success": True,
        "data": _df(CostIntelligenceRepository.get_cost_anomalies())
    }


def get_optimization_opportunities():
    return {
        "success": True,
        "data": _df(CostIntelligenceRepository.get_optimization_opportunities())
    }


def get_recommendations():
    return {
        "success": True,
        "data": _df(CostIntelligenceRepository.get_recommendations())
    }
