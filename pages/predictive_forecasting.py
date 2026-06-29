from __future__ import annotations

from typing import Any

import pandas as pd
import plotly.express as px
import streamlit as st

from auth.connector_context import get_current_organization_id
from auth.guards import require_login
from auth.role_constants import normalize_role
from components.sidebar_navigation import render_sidebar_navigation
from services.forecasting_service import ForecastingService
from services.risk_prediction_service import RiskPredictionService
from services.capacity_intelligence_service import CapacityIntelligenceService
from services.financial_intelligence_service import FinancialIntelligenceService


st.set_page_config(page_title="Predictive Forecasting", layout="wide")

ALLOWED_ROLES = {"super_admin", "client_admin", "cio", "executive", "finance", "technical"}


def _require_access(role: str) -> None:
    if role not in ALLOWED_ROLES:
        st.error("Predictive Forecasting is available to leadership, finance, and operations roles.")
        st.stop()


def _currency(value: Any) -> str:
    try:
        return f"${float(value or 0):,.0f}"
    except (TypeError, ValueError):
        return "$0"


def _number(value: Any) -> str:
    try:
        return f"{float(value or 0):,.0f}"
    except (TypeError, ValueError):
        return "0"


def _show_table(rows: list[dict[str, Any]], empty_message: str) -> None:
    if rows:
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    else:
        st.info(empty_message)


def main() -> None:
    user = require_login()
    role = normalize_role(st.session_state.get("role") or user.get("role") or "cio")
    render_sidebar_navigation(role)
    _require_access(role)

    organization_id = get_current_organization_id()
    forecast = ForecastingService.forecast_enterprise_metrics(organization_id)
    risks = RiskPredictionService.predict_risks(organization_id)
    capacity = CapacityIntelligenceService.forecast_capacity(organization_id)
    financial = FinancialIntelligenceService.get_financial_forecast(organization_id)
    summary = forecast["summary"]

    st.title("Predictive Forecasting")
    st.caption("Forecast enterprise spend, budget consumption, risk, capacity, and financial exposure across planning horizons.")

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Predicted Spend", _currency(summary["Predicted Spend"]))
    k2.metric("Top Metric", summary["Top Forecast Metric"])
    k3.metric("Top Forecast", _currency(summary["Top Forecast Value"]))
    k4.metric("Avg Confidence", f"{summary['Average Confidence']:.1f}%")

    st.divider()
    st.subheader("Forecast Horizons")
    df = pd.DataFrame(forecast["forecasts"])
    if not df.empty:
        fig = px.line(df, x="Horizon Days", y="Forecast", color="Metric", markers=True)
        st.plotly_chart(fig, use_container_width=True)
    _show_table(forecast["forecasts"], "No forecast rows are available.")

    st.divider()
    r1, r2 = st.columns(2)
    with r1:
        st.subheader("Risk Predictions")
        _show_table(risks["predictions"][:15], "No risk predictions are available.")
    with r2:
        st.subheader("Capacity Intelligence")
        _show_table(capacity["capacity"], "No capacity forecast is available.")

    st.divider()
    st.subheader("Financial Intelligence")
    f1, f2, f3 = st.columns(3)
    f1.metric("15% Savings Target", _currency(financial["summary"]["Savings Target 15%"]))
    f2.metric("Can Achieve 15%", financial["summary"]["Can Achieve 15% Savings"])
    f3.metric("First Budget Breach", financial["summary"]["First Budget Breach"])
    _show_table(financial["savings_candidates"], "No financial savings candidates are available.")


if __name__ == "__main__":
    main()
