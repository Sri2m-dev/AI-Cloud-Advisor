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
from shared.layout import render_page_header
from shared.charts import render_chart
from components.sidebar import render_sidebar
from services.dashboard_metrics import get_executive_dashboard_metrics

configure_page(
    page_title="Service Explorer | AI Cloud Advisor",
    page_icon="📊",
)

init_session()

require_role([
    "executive",
    "technical",
    "super_admin",
])

render_sidebar(role=st.session_state.get("role", "Unknown"))

org_id = st.session_state.get("organization_id")

dashboard = get_executive_dashboard_metrics(org_id)

render_page_header(
    "Service Explorer",
    "Cloud Service Cost Intelligence and Optimization"
)

# -----------------------------------------------------
# Spend by Cloud
# -----------------------------------------------------

cloud_data = dashboard.get("spend_by_cloud", [])

if cloud_data:
    cloud_df = pd.DataFrame(cloud_data)

    fig = px.pie(
        cloud_df,
        names="cloud",
        values="spend",
        hole=0.5,
        title="Cloud Spend Distribution"
    )

    render_chart(
        "Spend by Cloud",
        fig
    )

# -----------------------------------------------------
# Top Services
# -----------------------------------------------------

top_services = dashboard.get("top_services", [])

st.subheader("Top Services by Spend")

if top_services:

    service_df = pd.DataFrame(top_services)

    fig = px.bar(
        service_df,
        x="service",
        y="spend",
        title="Top Services"
    )

    render_chart(
        "Top Services",
        fig
    )

    st.dataframe(
        service_df,
        use_container_width=True,
        hide_index=True
    )

else:
    st.info("No service cost data available.")

# -----------------------------------------------------
# Daily Spend Trend
# -----------------------------------------------------

trend_data = dashboard.get(
    "daily_spend_trend",
    []
)

st.subheader("Daily Spend Trend")

if trend_data:

    trend_df = pd.DataFrame(trend_data)

    fig = px.line(
        trend_df,
        x="date",
        y="spend",
        title="Daily Spend"
    )

    render_chart(
        "Daily Spend Trend",
        fig
    )

# -----------------------------------------------------
# Recommendations
# -----------------------------------------------------

st.subheader(
    "Optimization Opportunities"
)

recommendations = dashboard.get(
    "top_recommendations",
    []
)

if isinstance(recommendations, pd.DataFrame):
    has_recommendations = not recommendations.empty
else:
    has_recommendations = len(recommendations) > 0

if has_recommendations:

    rec_df = (
        recommendations
        if isinstance(recommendations, pd.DataFrame)
        else pd.DataFrame(recommendations)
    )

    st.dataframe(
        rec_df,
        use_container_width=True,
        hide_index=True
    )

else:
    st.info(
        "No recommendations available."
    )