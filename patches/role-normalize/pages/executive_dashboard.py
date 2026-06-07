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
from shared.charts import render_chart
from shared.components import kpi_cards
from shared.layout import render_page_header, render_section
from shared.session import init_session
from shared.styles import configure_page
from shared.tables import recommendation_table
from services.dashboard_metrics import (
    DETAIL_COLUMNS,
    get_executive_dashboard_metrics,
)

configure_page(
    page_title="Executive Dashboard | AI Cloud Advisor",
    page_icon=":bar_chart:",
)

init_session()

authenticated = bool(
    st.session_state.get("authenticated")
)

if not authenticated:
    st.warning("Please login first.")
    st.switch_page("pages/login.py")

require_role([
    "executive",
    "technical",
    "super_admin",
])

with st.sidebar:

    st.markdown("### AI Cloud Advisor")
    st.caption("Enterprise Cloud Governance")

    st.divider()

    user = st.session_state.get(
        "user",
        "Unknown"
    )

    role = st.session_state.get(
        "role",
        "Unknown"
    )

    organization = st.session_state.get(
        "organization_name",
        "Demo Enterprise"
    )

    st.markdown(
        f"""
        **User**  
        {user}

        **Role**  
        {role}

        **Organization**  
        {organization}
        """
    )

    st.divider()

    if role == "super_admin":
        st.success(
            "Platform Administrator"
        )

    elif role == "executive":
        st.info(
            "Executive Access"
        )

    if st.button("Logout"):
        st.session_state.clear()
        st.switch_page("pages/logout.py")

organization_id = st.session_state.get(
    "organization_id"
)

if not organization_id:
    st.error(
        "Organization not assigned."
    )
    st.stop()

dashboard = get_executive_dashboard_metrics(
    organization_id
)

gov_score = dashboard["governance_score"]

total_spend = dashboard["total_spend"]
pending_recs = dashboard["pending_recommendations"]

completed_savings = dashboard["completed_savings"]
savings_opportunity = dashboard["savings_opportunity"]

overall_score = float(
    gov_score.get("overall_score", 0)
)

render_page_header(
    "AI Cloud Advisor",
    "Enterprise Cloud Governance and FinOps Executive Overview",
)

role = st.session_state.get(
    "role",
    "Unknown"
)

if role == "super_admin":
    st.success(
        "Viewing dashboard as Platform Administrator"
    )

# ======================================================
# KPI CARDS
# ======================================================

kpi_cards(
    [
        {
            "label": "Total Spend",
            "value": f"${total_spend:,.0f}",
        },
        {
            "label": "Governance Score",
            "value": f"{overall_score:.2f}%",
        },
        {
            "label": "Pending Recommendations",
            "value": f"{pending_recs:,}",
        },
        {
            "label": "Savings Opportunity",
            "value": f"${savings_opportunity:,.0f}",
        },
    ]
)

# ======================================================
# Spend by Cloud
# ======================================================

spend_by_cloud = dashboard["spend_by_cloud"]

if spend_by_cloud and not pd.DataFrame(
    spend_by_cloud
).empty:

    df_cloud = pd.DataFrame(
        spend_by_cloud
    )

    fig_cloud = px.pie(
        df_cloud,
        names="cloud",
        values="spend",
        hole=0.5,
    )

    fig_cloud.update_traces(
        textinfo="percent",
        textposition="inside",
    )

    render_chart(
        "Spend by Cloud",
        fig_cloud,
    )

else:
    render_section("Spend by Cloud")
    st.info("No cloud spend data available.")

# ======================================================
# Daily Spend Trend
# ======================================================

daily_trend = dashboard["daily_spend_trend"]

if daily_trend and not pd.DataFrame(
    daily_trend
).empty:

    df_trend = pd.DataFrame(
        daily_trend
    )

    fig_trend = px.line(
        df_trend,
        x="date",
        y="spend",
        markers=True,
    )

    render_chart(
        "Daily Spend Trend",
        fig_trend,
    )

else:
    render_section("Daily Spend Trend")
    st.info("No daily trend data available.")

# ======================================================
# Top Services
# ======================================================

top_services = dashboard["top_services"]

if top_services and not pd.DataFrame(
    top_services
).empty:

    df_services = (
        pd.DataFrame(top_services)
        .sort_values(
            "spend",
            ascending=False,
        )
        .head(10)
    )

    fig_services = px.bar(
        df_services,
        x="service",
        y="spend",
    )

    fig_services.update_xaxes(
        tickangle=-45
    )

    render_chart(
        "Top Services",
        fig_services,
    )

else:
    render_section("Top Services")
    st.info("No services data available.")

# ======================================================
# Recommendation Breakdown
# ======================================================

rec_breakdown = dashboard[
    "recommendation_breakdown"
]

if rec_breakdown and not pd.DataFrame(
    rec_breakdown
).empty:

    fig_rec = px.pie(
        pd.DataFrame(
            rec_breakdown
        ),
        names="type",
        values="count",
        hole=0.6,
    )

    render_chart(
        "Recommendation Breakdown",
        fig_rec,
    )

else:
    render_section(
        "Recommendation Breakdown"
    )
    st.info(
        "No recommendation breakdown available."
    )

# ======================================================
# GOVERNANCE OVERVIEW
# ======================================================

render_section("Governance Overview")

governance_metrics = dashboard.get(
    "governance_metrics",
    {},
)

with st.container(border=True):

    col1, col2, col3, col4, col5 = st.columns(5)

    compliance = governance_metrics.get(
        "compliance",
        0,
    )

    optimization = governance_metrics.get(
        "optimization",
        0,
    )

    sla = governance_metrics.get(
        "sla",
        0,
    )

    idle = governance_metrics.get(
        "idle_resources",
        0,
    )

    security = governance_metrics.get(
        "security",
        0,
    )

    col1.metric(
        "Compliance",
        f"{float(compliance):.0f}%"
        if isinstance(
            compliance,
            (int, float),
        )
        else str(compliance),
    )

    col2.metric(
        "Optimization",
        f"{float(optimization):.0f}%"
        if isinstance(
            optimization,
            (int, float),
        )
        else str(optimization),
    )

    col3.metric(
        "SLA",
        f"{float(sla):.0f}%"
        if isinstance(
            sla,
            (int, float),
        )
        else str(sla),
    )

    col4.metric(
        "Idle Resources",
        f"{float(idle):.0f}%"
        if isinstance(
            idle,
            (int, float),
        )
        else str(idle),
    )

    col5.metric(
        "Security",
        f"{float(security):.0f}%"
        if isinstance(
            security,
            (int, float),
        )
        else str(security),
    )

# ======================================================
# EXECUTIVE SUMMARY
# ======================================================

render_section(
    "Executive Summary"
)

with st.container(border=True):

    st.markdown(
        f"""
Enterprise cloud spend is currently **${total_spend:,.0f}**, with **{pending_recs:,}** recommendations pending review.

Governance score stands at **{overall_score:.2f}%**, reflecting current compliance and optimization coverage.

Realized savings to date are **${completed_savings:,.0f}**.

Potential savings opportunity currently identified is **${savings_opportunity:,.0f}**.
"""
    )

# ======================================================
# TOP RECOMMENDATIONS
# ======================================================

render_section(
    "Top Recommendations"
)

top_recs = dashboard[
    "top_recommendations"
]

if (
    top_recs is not None
    and not top_recs.empty
):

    recommendation_table(
        top_recs,
        columns=[
            "service",
            "description",
            "estimated_savings",
            "status",
            "priority",
        ],
        rename_columns={
            "service": "Service",
            "description": "Description",
            "estimated_savings": "Estimated Savings ($)",
            "status": "Status",
            "priority": "Priority",
        },
    )

else:
    st.info(
        "No recommendations available."
    )
