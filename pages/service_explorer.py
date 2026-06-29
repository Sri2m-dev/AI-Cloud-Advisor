from __future__ import annotations

import os
import sys

import pandas as pd
import plotly.express as px
import streamlit as st

ROOT_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..")
)

if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from shared.auth import require_role
from shared.session import init_session
from shared.styles import configure_page
from shared.layout import render_page_header
from shared.charts import render_chart
from components.sidebar_navigation import render_sidebar_navigation

from repositories.service_explorer_repository import (
    ServiceExplorerRepository,
)

configure_page(
    page_title="Service Explorer | Nexora",
    page_icon="📊",
)

init_session()

require_role(
    [
        "executive",
        "cio",
        "technical",
        "super_admin",
    ]
)

role = st.session_state.get("role", "Unknown")
render_sidebar_navigation(role)

render_page_header(
    "Service Explorer",
    "Cloud Service Cost Intelligence and Optimization"
)

# =====================================================
# KPI SECTION
# =====================================================

kpis = ServiceExplorerRepository.get_kpis()

col1, col2, col3, col4, col5 = st.columns(5)

with col1:
    st.metric(
        "Services",
        kpis["total_services"]
    )

with col2:
    st.metric(
        "Critical Services",
        kpis["critical_services"]
    )

with col3:
    st.metric(
        "Total Spend",
        f"${kpis['total_spend']:,.0f}"
    )

with col4:
    st.metric(
        "Optimization Candidates",
        kpis["optimization_candidates"]
    )

with col5:
    st.metric(
        "Active Anomalies",
        kpis["active_anomalies"]
    )

st.divider()

# =====================================================
# SERVICE CLASSIFICATION
# =====================================================

service_data = (
    ServiceExplorerRepository
    .get_service_classification()
)

if service_data:

    service_df = pd.DataFrame(service_data)

    st.subheader(
        "Service Cost Distribution"
    )

    top_services = (
        service_df
        .sort_values(
            "total_cost",
            ascending=False
        )
        .head(15)
    )

    fig = px.bar(
        top_services,
        x="service_name",
        y="total_cost",
        color="cloud",
        title="Top Services by Cost"
    )

    render_chart(
        "Top Services",
        fig
    )

    st.dataframe(
        top_services,
        use_container_width=True,
        hide_index=True,
    )

st.divider()

# =====================================================
# OPTIMIZATION OPPORTUNITIES
# =====================================================

optimization_data = (
    ServiceExplorerRepository
    .get_optimization_opportunities()
)

if optimization_data:

    optimization_df = pd.DataFrame(
        optimization_data
    )

    st.subheader(
        "Optimization Opportunities"
    )

    fig = px.bar(
        optimization_df.head(10),
        x="service_name",
        y="total_cost",
        color="cloud",
        title="Top Optimization Candidates"
    )

    render_chart(
        "Optimization Opportunities",
        fig
    )

    st.dataframe(
        optimization_df,
        use_container_width=True,
        hide_index=True,
    )

st.divider()

# =====================================================
# COST ANOMALIES
# =====================================================

anomaly_data = (
    ServiceExplorerRepository
    .get_cost_anomalies()
)

if anomaly_data:

    anomaly_df = pd.DataFrame(
        anomaly_data
    )

    st.subheader(
        "Cost Anomalies"
    )

    st.dataframe(
        anomaly_df,
        use_container_width=True,
        hide_index=True,
    )

st.divider()

# =====================================================
# AI RECOMMENDATIONS
# =====================================================

recommendation_data = (
    ServiceExplorerRepository
    .get_ai_recommendations()
)

if recommendation_data:

    recommendation_df = pd.DataFrame(
        recommendation_data
    )

    st.subheader(
        "AI Recommendations"
    )

    st.dataframe(
        recommendation_df,
        use_container_width=True,
        hide_index=True,
    )

else:

    st.info(
        "No AI recommendations available."
    )
