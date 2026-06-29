from __future__ import annotations

from typing import Any

import pandas as pd
import plotly.express as px
import streamlit as st

from auth.connector_context import get_current_organization_id
from auth.guards import require_login
from auth.role_constants import normalize_role
from components.sidebar_navigation import render_sidebar_navigation
from services.capacity_intelligence_service import CapacityIntelligenceService
from services.financial_intelligence_service import FinancialIntelligenceService
from services.forecasting_service import ForecastingService
from services.predictive_ai_service import PredictiveAIService
from services.risk_prediction_service import RiskPredictionService


st.set_page_config(page_title="Predictive Center", layout="wide")

ALLOWED_ROLES = {"super_admin", "client_admin", "cio", "executive", "finance", "technical"}


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


def _require_access(role: str) -> None:
    if role not in ALLOWED_ROLES:
        st.error("Predictive Center is available to leadership, finance, and operations roles.")
        st.stop()


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
    predictive = PredictiveAIService.get_predictive_recommendations(organization_id)
    accuracy = forecast["model"]["accuracy"]

    st.title("Executive Predictive Center")
    st.caption("One screen for predicted spend, savings, risks, failures, accuracy, confidence, renewals, and capacity issues.")

    next_month = [row for row in forecast["forecasts"] if row["Horizon Days"] == 30]
    predicted_spend = sum(row["Forecast"] for row in next_month)
    predicted_savings = sum(row["Savings Potential"] for row in financial["savings_candidates"])
    predicted_risks = risks["summary"]["Predicted Risks"]
    predicted_failures = risks["summary"]["Predicted Failures"]
    ai_confidence = max([row["Confidence"] for row in predictive["recommendations"]] or [0])

    k1, k2, k3, k4, k5, k6 = st.columns(6)
    k1.metric("Predicted Spend", _currency(predicted_spend))
    k2.metric("Predicted Savings", _currency(predicted_savings))
    k3.metric("Predicted Risks", _number(predicted_risks))
    k4.metric("Predicted Failures", _number(predicted_failures))
    k5.metric("Forecast Accuracy", f"{accuracy['Forecast Accuracy']:.1f}%")
    k6.metric("AI Confidence", f"{ai_confidence:.1f}%")

    st.divider()
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Upcoming Budget Breaches")
        _show_table(financial["budget_risks"], "No budget breaches are forecasted.")
        st.subheader("Upcoming Renewals")
        _show_table([row for row in risks["predictions"] if row["Risk Category"] == "Unnecessary renewal"][:10], "No renewal risks are forecasted.")
    with c2:
        st.subheader("Upcoming Capacity Issues")
        _show_table([row for row in capacity["capacity"] if row["Days To 95%"] <= 30], "No capacity issues within 30 days.")
        st.subheader("Predictive AI")
        _show_table(predictive["recommendations"], "No predictive recommendations are available.")

    st.divider()
    st.subheader("Forecast Trend")
    df = pd.DataFrame(forecast["forecasts"])
    if not df.empty:
        fig = px.bar(df[df["Horizon Days"].isin([30, 90])], x="Metric", y="Forecast", color="Horizon Days", barmode="group")
        st.plotly_chart(fig, use_container_width=True)


if __name__ == "__main__":
    main()
