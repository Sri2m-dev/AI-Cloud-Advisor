from __future__ import annotations

import os
import sys

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

import pandas as pd
import plotly.express as px
import streamlit as st

from shared.session import init_session
from shared.styles import configure_page
from components.sidebar_navigation import render_sidebar_navigation

configure_page(
    page_title="Leadership Dashboard | Nexora",
    page_icon="📈",
)

init_session()

from shared.auth import require_role

require_role([
    "executive",
    "super_admin",
])

role = st.session_state.get("role", "Unknown")
render_sidebar_navigation(role)

from components.layout import render_page_header, render_section
from components.tables import data_table
from services.leadership_metrics import get_leadership_dashboard_metrics

dashboard = get_leadership_dashboard_metrics()

kpis = dashboard["kpis"]

render_page_header(
    "Leadership Dashboard",
    "Enterprise Financial, Governance and Optimization Overview",
)

# =====================================================
# KPI ROW
# =====================================================

c1, c2, c3, c4, c5 = st.columns(5)

c1.metric(
    "Enterprise Spend",
    f"${kpis['total_spend']:,.0f}"
)

c2.metric(
    "Savings Opportunity",
    f"${kpis['savings_identified']:,.0f}"
)

c3.metric(
    "Governance Score",
    f"{kpis['governance_score']:.0f}%"
)

c4.metric(
    "Security Score",
    f"{kpis['security_score']:.0f}%"
)

c5.metric(
    "Customer Health",
    f"{kpis['customer_health_score']:.0f}"
)

st.divider()

# =====================================================
# ENTERPRISE SPEND BREAKDOWN
# =====================================================

render_section("Enterprise Spend Breakdown")

spend_breakdown = pd.DataFrame(
    [
        {
            "Category": "Cloud",
            "Cost": kpis["cloud_cost"],
        },
        {
            "Category": "SaaS",
            "Cost": kpis["saas_cost"],
        },
        {
            "Category": "MSP",
            "Cost": kpis["msp_cost"],
        },
        {
            "Category": "Licensing",
            "Cost": kpis["license_cost"],
        },
    ]
)

fig = px.pie(
    spend_breakdown,
    names="Category",
    values="Cost",
    hole=0.5,
)

st.plotly_chart(
    fig,
    use_container_width=True,
)

# =====================================================
# SAVINGS
# =====================================================

render_section("Savings Program")

savings_df = pd.DataFrame(
    [
        {
            "Status": "Identified",
            "Value": dashboard["savings"]["identified"],
        },
        {
            "Status": "Realized",
            "Value": dashboard["savings"]["realized"],
        },
        {
            "Status": "Pending",
            "Value": dashboard["savings"]["pending"],
        },
    ]
)

fig = px.bar(
    savings_df,
    x="Status",
    y="Value",
)

st.plotly_chart(
    fig,
    use_container_width=True,
)

st.info(
    f"Realization Rate: "
    f"{dashboard['savings']['realization_rate']:.1f}%"
)

# =====================================================
# APPROVALS
# =====================================================

render_section("Approval Governance")

st.metric(
    "Pending Approvals",
    kpis["pending_approvals"]
)

approvals = pd.DataFrame(
    dashboard["approvals"]
)

if not approvals.empty:
    data_table(approvals)

# =====================================================
# COST ANOMALIES
# =====================================================

render_section("Cost Anomalies")

anomalies = pd.DataFrame(
    dashboard["anomalies"]
)

if not anomalies.empty:
    data_table(anomalies)

# =====================================================
# OPTIMIZATION
# =====================================================

render_section("Optimization Opportunities")

optimization = pd.DataFrame(
    dashboard["optimization_opportunities"]
)

if not optimization.empty:

    chart = px.bar(
        optimization.head(10),
        x="service_name",
        y="total_cost",
        color="cloud",
        title="Top Optimization Targets",
    )

    st.plotly_chart(
        chart,
        use_container_width=True,
    )

    data_table(
        optimization
    )

# =====================================================
# RECOMMENDATIONS
# =====================================================

render_section("AI Recommendations")

recommendations = pd.DataFrame(
    dashboard["recommendations"]
)

if not recommendations.empty:
    data_table(
        recommendations
    )

# =====================================================
# EXECUTIVE SUMMARY
# =====================================================

render_section("Executive Summary")

st.success(
    f"""
Enterprise spend is currently ${kpis['total_spend']:,.0f}.

Cloud Spend: ${kpis['cloud_cost']:,.0f}

SaaS Spend: ${kpis['saas_cost']:,.0f}

MSP Spend: ${kpis['msp_cost']:,.0f}

License Spend: ${kpis['license_cost']:,.0f}

Optimization Opportunity: ${kpis['savings_identified']:,.0f}

Governance Score: {kpis['governance_score']:.0f}%

Security Score: {kpis['security_score']:.0f}%

Customer Health: {kpis['customer_health_label']}
"""
)
