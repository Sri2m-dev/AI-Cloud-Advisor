from __future__ import annotations

import os
import sys

import pandas as pd
import plotly.express as px
import streamlit as st

ROOT_DIR = os.path.abspath(
    os.path.join(
        os.path.dirname(__file__),
        ".."
    )
)

if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from shared.auth import require_role
from shared.session import init_session
from shared.styles import configure_page
from shared.layout import render_page_header
from shared.charts import render_chart
from components.sidebar_navigation import render_sidebar_navigation

from services.technology_spend_service import (
    TechnologySpendService
)

configure_page(
    page_title="Technology Spend",
    page_icon="💰",
)

init_session()

require_role([
    "executive",
    "cio",
    "finance",
    "technical",
    "super_admin",
])

role = st.session_state.get("role", "Unknown")
render_sidebar_navigation(role)

render_page_header(
    "Technology Spend",
    "Cloud, SaaS, MSP and License Cost Management"
)

# --------------------------------------------------
# KPI Summary
# --------------------------------------------------

kpis = TechnologySpendService.get_kpis()

col1, col2, col3, col4, col5 = st.columns(5)

col1.metric("Cloud Cost", f"${kpis['cloud_cost']:,.0f}")
col2.metric("SaaS Cost", f"${kpis['saas_cost']:,.0f}")
col3.metric("MSP Cost", f"${kpis['msp_cost']:,.0f}")
col4.metric("License Cost", f"${kpis['license_cost']:,.0f}")
col5.metric("Total Spend", f"${kpis['total_spend']:,.0f}")

st.divider()

# --------------------------------------------------
# Spend Allocation Charts
# --------------------------------------------------

allocation_df = pd.DataFrame([
    {
        "Category": "Cloud",
        "Cost": kpis["cloud_cost"]
    },
    {
        "Category": "SaaS",
        "Cost": kpis["saas_cost"]
    },
    {
        "Category": "MSP",
        "Cost": kpis["msp_cost"]
    },
    {
        "Category": "License",
        "Cost": kpis["license_cost"]
    }
])

col1, col2 = st.columns(2)

with col1:

    pie_fig = px.pie(
        allocation_df,
        names="Category",
        values="Cost",
        title="Technology Spend Allocation"
    )

    render_chart(
        "Spend Allocation",
        pie_fig
    )

with col2:

    bar_fig = px.bar(
        allocation_df,
        x="Category",
        y="Cost",
        title="Cost Comparison"
    )

    render_chart(
        "Cost Comparison",
        bar_fig
    )

st.divider()

# --------------------------------------------------
# Enterprise Spend Breakdown
# --------------------------------------------------

st.subheader(
    "Enterprise Spend Breakdown"
)

breakdown = (
    TechnologySpendService
    .get_spend_breakdown()
)

if breakdown:

    st.dataframe(
        pd.DataFrame(breakdown),
        use_container_width=True,
        hide_index=True
    )

st.divider()

# --------------------------------------------------
# Managed Services
# --------------------------------------------------

st.subheader(
    "Managed Services Cost"
)

msp = (
    TechnologySpendService
    .get_managed_services()
)

if msp:

    msp_df = pd.DataFrame(msp)

    st.dataframe(
        msp_df,
        use_container_width=True,
        hide_index=True
    )

    provider_summary = (
        msp_df
        .groupby("provider")["cost"]
        .sum()
        .reset_index()
        .sort_values(
            "cost",
            ascending=False
        )
    )

    provider_fig = px.bar(
        provider_summary,
        x="provider",
        y="cost",
        title="MSP Provider Spend"
    )

    render_chart(
        "Top MSP Providers",
        provider_fig
    )

st.divider()

# --------------------------------------------------
# SaaS Cost
# --------------------------------------------------

st.subheader(
    "SaaS Cost"
)

saas = (
    TechnologySpendService
    .get_saas_spend()
)

if saas:

    saas_df = pd.DataFrame(saas)

    st.dataframe(
        saas_df,
        use_container_width=True,
        hide_index=True
    )

    vendor_summary = (
        saas_df
        .groupby("vendor_name")["cost"]
        .sum()
        .reset_index()
        .sort_values(
            "cost",
            ascending=False
        )
    )

    vendor_fig = px.bar(
        vendor_summary,
        x="vendor_name",
        y="cost",
        title="SaaS Vendor Spend"
    )

    render_chart(
        "Top SaaS Vendors",
        vendor_fig
    )
