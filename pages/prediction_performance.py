from __future__ import annotations

from typing import Any

import pandas as pd
import plotly.express as px
import streamlit as st

from auth.connector_context import get_current_organization_id
from auth.guards import require_login
from auth.role_constants import normalize_role
from components.sidebar_navigation import render_sidebar_navigation
from services.predictive_accuracy_service import PredictiveAccuracyService


st.set_page_config(page_title="Prediction Performance", layout="wide")

ALLOWED_ROLES = {"super_admin", "client_admin", "cio", "executive", "finance", "technical"}


def _require_access(role: str) -> None:
    if role not in ALLOWED_ROLES:
        st.error("Prediction Performance is available to leadership, finance, and operations roles.")
        st.stop()


def _number(value: Any) -> str:
    try:
        return f"{float(value or 0):,.1f}%"
    except (TypeError, ValueError):
        return "0.0%"


def _currency(value: Any) -> str:
    try:
        return f"${float(value or 0):,.0f}"
    except (TypeError, ValueError):
        return "$0"


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
    performance = PredictiveAccuracyService.get_prediction_performance(organization_id)
    kpis = performance["kpis"]
    health = performance["prediction_health_score"]
    confidence = performance["confidence_calibration"]
    drift = performance["drift"]

    st.title("Prediction Performance")
    st.caption("Measure forecast accuracy, confidence calibration, drift, model governance, and enterprise prediction health.")

    k1, k2, k3, k4, k5, k6 = st.columns(6)
    k1.metric("Prediction Health", f"{health['Score']:.1f}")
    k2.metric("Avg Accuracy", _number(kpis["Average Forecast Accuracy"]))
    k3.metric("Spend Accuracy", _number(kpis["Spend Prediction Accuracy"]))
    k4.metric("Capacity Accuracy", _number(kpis["Capacity Prediction Accuracy"]))
    k5.metric("Risk Accuracy", _number(kpis["Risk Prediction Accuracy"]))
    k6.metric("AI Confidence", _number(kpis["AI Confidence Trend"]))

    st.info(performance["executive_summary"])

    st.divider()
    left, right = st.columns([1.2, 1])
    with left:
        st.subheader("Executive Forecast Review")
        reviews = performance["forecast_reviews"]
        display_rows = [
            {
                **row,
                "Forecast": _currency(row["Forecast"]),
                "Actual": _currency(row["Actual"]),
                "Variance": _currency(row["Variance"]),
            }
            for row in reviews
        ]
        _show_table(display_rows, "No forecast reviews are available.")
    with right:
        st.subheader("Prediction Health Score")
        components = pd.DataFrame(health["Components"])
        if not components.empty:
            fig = px.bar(components, x="Metric", y="Score", color="Weight")
            fig.update_layout(yaxis_range=[0, 100])
            st.plotly_chart(fig, use_container_width=True)
        _show_table(health["Components"], "No prediction health components are available.")

    st.divider()
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Confidence Calibration")
        st.metric("Calibrated Confidence", _number(confidence["Confidence"]))
        if confidence["Reasons"]:
            st.write("Why confidence is strong")
            for reason in confidence["Reasons"]:
                st.write(f"- {reason}")
        if confidence["Concerns"]:
            st.write("Confidence constraints")
            for concern in confidence["Concerns"]:
                st.write(f"- {concern}")
        trend = pd.DataFrame(confidence["Trend"])
        if not trend.empty:
            fig = px.line(trend, x="Measured At", y="Confidence", color="Metric", markers=True)
            fig.update_layout(yaxis_range=[0, 100])
            st.plotly_chart(fig, use_container_width=True)
    with c2:
        st.subheader("Forecast Drift Detection")
        st.metric("Drift Status", drift["status"], f"{drift['drift_count']} metric(s)")
        _show_table(drift["rows"], "No significant model drift detected.")

    st.divider()
    st.subheader("Model Registry")
    _show_table(performance["model_registry"], "No model registry records are available.")


if __name__ == "__main__":
    main()
