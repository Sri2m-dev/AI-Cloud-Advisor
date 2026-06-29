from __future__ import annotations

import os
import sys

import pandas as pd
import plotly.express as px
import streamlit as st

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from shared.auth import require_role
from shared.session import init_session
from shared.styles import configure_page
from shared.layout import render_page_header, render_section
from components.sidebar_navigation import render_sidebar_navigation
from components.tables import data_table

from services.cost_intelligence_service import (
    get_enterprise_spend,
    get_enterprise_forecast,
    get_cost_trend,
    get_cost_forecast,
    get_cost_anomalies,
    get_optimization_opportunities,
    get_recommendations,
)

configure_page(
    page_title="Cost Intelligence | Nexora",
    page_icon="📈",
)

init_session()

require_role([
    "executive",
    "cio",
    "technical",
    "finance",
    "super_admin",
])

role = st.session_state.get("role", "Unknown")
render_sidebar_navigation(role)

render_page_header(
    "Cost Intelligence",
    "Executive FinOps analytics, forecasting, optimization and anomaly detection",
)

enterprise_spend = get_enterprise_spend()
enterprise_forecast_resp = get_enterprise_forecast()
trend_resp = get_cost_trend()
forecast_resp = get_cost_forecast()
anomaly_resp = get_cost_anomalies()
optimization_resp = get_optimization_opportunities()
recommendation_resp = get_recommendations()

enterprise_forecast_df = enterprise_forecast_resp["data"]
trend_df = trend_resp["data"]
forecast_df = forecast_resp["data"]
anomaly_df = anomaly_resp["data"]
optimization_df = optimization_resp["data"]
recommendation_df = recommendation_resp["data"]

current_cost = float(enterprise_spend.get("total_spend", 0) or 0)

forecast_cost = 0
if not enterprise_forecast_df.empty:
    for column in ["forecast_cost", "predicted_cost", "total_forecast", "total_spend"]:
        if column in enterprise_forecast_df.columns:
            forecast_cost = pd.to_numeric(
                enterprise_forecast_df[column],
                errors="coerce",
            ).fillna(0).sum()
            break

if not forecast_cost and not forecast_df.empty and "forecast_cost" in forecast_df.columns:
    forecast_cost = pd.to_numeric(
        forecast_df["forecast_cost"],
        errors="coerce",
    ).fillna(0).sum()

anomaly_count = len(anomaly_df) if not anomaly_df.empty else 0
optimization_count = len(optimization_df) if not optimization_df.empty else 0

potential_savings = 0
if not recommendation_df.empty and "estimated_savings" in recommendation_df.columns:
    potential_savings = pd.to_numeric(
        recommendation_df["estimated_savings"],
        errors="coerce",
    ).fillna(0).sum()

k1, k2, k3, k4, k5 = st.columns(5)

k1.metric("Current Cost", f"${current_cost:,.0f}")
k2.metric("Forecast Cost", f"${forecast_cost:,.0f}")
k3.metric("Anomalies", f"{anomaly_count}")
k4.metric("Optimization Items", f"{optimization_count}")
k5.metric("Potential Savings", f"${potential_savings:,.0f}")

st.divider()

col1, col2 = st.columns(2)

with col1:
    render_section("Cost Trend")

    if not trend_df.empty and {"service_name", "total_cost"}.issubset(trend_df.columns):
        top_trend_df = (
            trend_df
            .copy()
            .assign(total_cost=pd.to_numeric(trend_df["total_cost"], errors="coerce").fillna(0))
            .sort_values("total_cost", ascending=False)
            .head(10)
        )

        fig = px.bar(
            top_trend_df,
            x="service_name",
            y="total_cost",
            title="Top Services by Cost",
        )

        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No cost trend data available.")

with col2:
    render_section("Top Optimization Opportunities")

    if not optimization_df.empty and {"service_name", "total_cost"}.issubset(optimization_df.columns):
        top_optimization_df = (
            optimization_df
            .copy()
            .assign(total_cost=pd.to_numeric(optimization_df["total_cost"], errors="coerce").fillna(0))
            .sort_values("total_cost", ascending=False)
            .head(10)
        )

        fig = px.bar(
            top_optimization_df,
            x="service_name",
            y="total_cost",
            color="cloud" if "cloud" in top_optimization_df.columns else None,
            title="Top 10 Optimization Targets",
        )

        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No optimization opportunity data available.")

render_section("Forecast vs Actual")

if not forecast_df.empty and {"actual_cost", "forecast_cost"}.issubset(forecast_df.columns):
    forecast_chart_df = forecast_df.copy()

    forecast_chart_df["actual_cost"] = pd.to_numeric(
        forecast_chart_df["actual_cost"],
        errors="coerce",
    ).fillna(0)

    forecast_chart_df["forecast_cost"] = pd.to_numeric(
        forecast_chart_df["forecast_cost"],
        errors="coerce",
    ).fillna(0)

    x_axis = "date" if "date" in forecast_chart_df.columns else forecast_chart_df.index

    fig = px.bar(
        forecast_chart_df,
        x=x_axis,
        y=["actual_cost", "forecast_cost"],
        barmode="group",
        title="Forecast vs Actual Cost",
    )

    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("No forecast data available.")

st.divider()

render_section("Executive Insights")

insight_lines = [
    f"Current enterprise cost is ${current_cost:,.0f}.",
    f"Forecasted cost is ${forecast_cost:,.0f}.",
    f"{anomaly_count} cost anomaly records are available for review.",
    f"{optimization_count} optimization opportunities have been identified.",
    f"Potential savings currently tracked is ${potential_savings:,.0f}.",
]

for line in insight_lines:
    st.markdown(f"- {line}")

st.divider()

render_section("Cost Anomalies")
data_table(anomaly_df)

render_section("Optimization Opportunities")
data_table(optimization_df)

render_section("Recommendations")
data_table(recommendation_df)

render_section("Cost Trend Detail")
data_table(trend_df)

render_section("Forecast Detail")
data_table(forecast_df)
