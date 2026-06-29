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
from components.sidebar_navigation import render_sidebar_navigation

from services.cost_intelligence_service import (
    get_optimization_opportunities,
    get_recommendations,
)
from services.reporting_service import get_executive_summary


def safe_float(value):
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def safe_df(response):
    if isinstance(response, dict):
        data = response.get("data", pd.DataFrame())
    else:
        data = response

    if isinstance(data, pd.DataFrame):
        return data

    return pd.DataFrame(data or [])


def count_status(df, values):
    if df.empty:
        return 0

    for column in ["status", "recommendation_status", "state"]:
        if column in df.columns:
            statuses = df[column].fillna("").astype(str).str.upper()
            return int(statuses.isin(values).sum())

    return 0


def sum_column(df, columns):
    if df.empty:
        return 0.0

    for column in columns:
        if column in df.columns:
            return float(
                pd.to_numeric(
                    df[column],
                    errors="coerce",
                ).fillna(0).sum()
            )

    return 0.0


configure_page(
    page_title="Optimization Center | Nexora",
    page_icon="💡",
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
    "Optimization Center",
    "CIO view of savings opportunities, approval pipeline, implementation progress, and realized value",
)

executive_summary = get_executive_summary() or {}

optimization_df = safe_df(get_optimization_opportunities())
recommendation_df = safe_df(get_recommendations())

opportunity_count = len(optimization_df)

potential_savings = (
    safe_float(executive_summary.get("optimization_savings"))
    or safe_float(executive_summary.get("optimization"))
    or sum_column(
        recommendation_df,
        ["estimated_savings", "potential_savings", "savings", "annual_savings"],
    )
    or sum_column(
        optimization_df,
        ["estimated_savings", "potential_savings", "savings", "annual_savings"],
    )
)

approved_count = count_status(
    recommendation_df,
    {"APPROVED", "APPROVED_BY_CIO", "APPROVED_BY_CEO"},
)

pending_count = count_status(
    recommendation_df,
    {"PENDING", "PENDING_APPROVAL", "NEW"},
)

implemented_count = count_status(
    recommendation_df,
    {"IMPLEMENTED", "COMPLETED", "CLOSED", "RESOLVED"},
)

rejected_count = count_status(
    recommendation_df,
    {"REJECTED", "DECLINED"},
)

savings_realized = safe_float(executive_summary.get("savings_realized"))

k1, k2, k3, k4, k5 = st.columns(5)

k1.metric("Optimization Opportunities", opportunity_count)
k2.metric("Potential Savings", f"${potential_savings:,.0f}")
k3.metric("Approved Savings Items", approved_count)
k4.metric("Implemented Items", implemented_count)
k5.metric("Savings Realized", f"${savings_realized:,.0f}")

st.divider()

left, right = st.columns(2)

with left:
    st.subheader("Optimization Pipeline")

    pipeline_df = pd.DataFrame([
        {"Stage": "Identified", "Count": opportunity_count},
        {"Stage": "Pending Approval", "Count": pending_count},
        {"Stage": "Approved", "Count": approved_count},
        {"Stage": "Implemented", "Count": implemented_count},
        {"Stage": "Rejected", "Count": rejected_count},
    ])

    fig = px.bar(
        pipeline_df,
        x="Stage",
        y="Count",
        title="Optimization Lifecycle",
        text="Count",
    )

    st.plotly_chart(fig, use_container_width=True)

with right:
    st.subheader("Savings Program")

    savings_df = pd.DataFrame([
        {"Category": "Potential", "Amount": potential_savings},
        {"Category": "Realized", "Amount": savings_realized},
    ])

    fig = px.bar(
        savings_df,
        x="Category",
        y="Amount",
        title="Savings Identified vs Realized",
        text="Amount",
    )

    st.plotly_chart(fig, use_container_width=True)

st.divider()

st.subheader("Top Optimization Focus Areas")

if not optimization_df.empty and {"service_name", "total_cost"}.issubset(optimization_df.columns):
    focus_df = (
        optimization_df
        .copy()
        .assign(
            total_cost=pd.to_numeric(
                optimization_df["total_cost"],
                errors="coerce",
            ).fillna(0)
        )
        .sort_values("total_cost", ascending=False)
        .head(8)
    )

    fig = px.bar(
        focus_df,
        x="service_name",
        y="total_cost",
        color="cloud" if "cloud" in focus_df.columns else None,
        title="Highest Value Optimization Focus Areas",
    )

    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("No optimization focus data available.")

st.divider()

st.subheader("CIO Optimization Narrative")

st.info(
    f"""
The platform has identified **{opportunity_count} optimization opportunities** with potential savings of **${potential_savings:,.0f}**.

There are currently **{pending_count} pending items**, **{approved_count} approved items**, and **{implemented_count} implemented items** in the optimization pipeline.

Savings realized currently stands at **${savings_realized:,.0f}**.

The CIO focus should remain on converting approved recommendations into implemented savings and reducing high-value cloud waste.
"""
)
