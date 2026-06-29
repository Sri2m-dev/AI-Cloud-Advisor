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

from shared.session import init_session
from shared.styles import configure_page
from shared.auth import require_role
from components.sidebar_navigation import render_sidebar_navigation
from shared.layout import render_page_header

from services.saas_governance_service import (
    SaaSGovernanceService
)
from services.saas_service import (
    get_duplicate_saas_tools,
    get_inactive_saas_users,
    get_renewal_forecasting,
    get_saas_license_utilization,
    get_vendor_cost_trends,
)


def safe_float(value):
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def safe_int(value):
    try:
        return int(float(value or 0))
    except (TypeError, ValueError):
        return 0


configure_page(
    page_title="SaaS Governance",
    page_icon="☁️",
)

init_session()

require_role([
    "executive",
    "cio",
    "finance",
    "technical",
    "super_admin",
])

role = st.session_state.get("role", "cio")
render_sidebar_navigation(role)

current_role = st.session_state.get("role", "").lower()
is_ceo_view = current_role == "executive"
org_id = st.session_state.get("organization_id")

render_page_header(
    "SaaS Governance",
    "SaaS Spend, Licensing and Vendor Optimization"
)

# --------------------------------------------------
# KPI Summary
# --------------------------------------------------

kpis = (
    SaaSGovernanceService
    .get_kpis()
)

utilization_data = get_saas_license_utilization(org_id)
utilization_rows = utilization_data.get("data", [])

renewal_data = get_renewal_forecasting(org_id)
renewal_rows = renewal_data.get("data", [])
renewal_df = pd.DataFrame(renewal_rows)

if not renewal_df.empty:
    for column in [
        "vendor",
        "application",
        "renewal_date",
        "annual_cost",
        "days_until_renewal",
    ]:
        if column not in renewal_df.columns:
            renewal_df[column] = None

    renewal_df = renewal_df.drop_duplicates(
        subset=[
            "vendor",
            "application",
            "renewal_date",
            "annual_cost",
        ]
    )

estimated_waste = sum(
    safe_float(item.get("estimated_waste"))
    for item in utilization_rows
)

renewal_vendors = len(
    {
        str(vendor).strip()
        for vendor in (
            renewal_df["vendor"]
            if not renewal_df.empty
            else []
        )
        if str(vendor).strip()
    }
)

c1, c2, c3, c4, c5, c6 = st.columns(6)

c1.metric(
    "SaaS Spend",
    f"${kpis['total_saas']:,.0f}"
)

c2.metric(
    "License Cost",
    f"${kpis['total_license']:,.0f}"
)

c3.metric(
    "Users",
    f"{kpis['total_users']:,}"
)

c4.metric(
    "SaaS Vendors",
    f"{kpis['vendors']}"
)

c5.metric(
    "Renewal Vendors",
    renewal_vendors
)

c6.metric(
    "License Waste",
    f"${estimated_waste:,.0f}"
)

st.divider()

# --------------------------------------------------
# Load Data
# --------------------------------------------------

# SaaS and license tables are currently enterprise-level snapshots.
saas_data = (
    SaaSGovernanceService
    .get_saas_spend()
)

license_data = (
    SaaSGovernanceService
    .get_license_cost()
)

saas_df = pd.DataFrame(saas_data)
license_df = pd.DataFrame(license_data)

duplicate_tools_data = get_duplicate_saas_tools(org_id)
duplicate_tool_rows = duplicate_tools_data.get("data", [])

vendor_trends_data = get_vendor_cost_trends(org_id)
vendor_trend_rows = vendor_trends_data.get("data", [])

inactive_users_data = get_inactive_saas_users(org_id)
inactive_user_rows = inactive_users_data.get("data", [])

# --------------------------------------------------
# Charts
# --------------------------------------------------

col1, col2 = st.columns(2)

with col1:

    st.subheader(
        "SaaS Spend Allocation"
    )

    if not saas_df.empty:

        fig = px.pie(
            saas_df,
            names="vendor_name",
            values="cost",
            title="SaaS Spend by Vendor"
        )

        st.plotly_chart(
            fig,
            use_container_width=True
        )

with col2:

    st.subheader(
        "License Utilization"
    )

    st.metric(
        "Utilization",
        f"{kpis['utilization']}%"
    )

    if not license_df.empty:

        used = (
            license_df["licenses_used"]
            .sum()
        )

        purchased = (
            license_df["licenses_purchased"]
            .sum()
        )

        unused = max(
            purchased - used,
            0
        )

        util_df = pd.DataFrame(
            {
                "Category": [
                    "Used",
                    "Unused"
                ],
                "Value": [
                    used,
                    unused
                ]
            }
        )

        fig = px.pie(
            util_df,
            names="Category",
            values="Value",
            hole=0.5,
            title="License Utilization"
        )

        st.plotly_chart(
            fig,
            use_container_width=True
        )

st.divider()

# --------------------------------------------------
# Renewal Risk Summary
# --------------------------------------------------

st.subheader(
    "Renewal Risk Summary"
)

if not renewal_df.empty:
    renewal_days = pd.to_numeric(
        renewal_df["days_until_renewal"],
        errors="coerce"
    )
else:
    renewal_days = pd.Series(dtype="float64")

critical = len(
    renewal_df[
        renewal_days <= 30
    ]
)

warning = len(
    renewal_df[
        (renewal_days > 30)
        & (renewal_days <= 60)
    ]
)

upcoming = len(
    renewal_df[
        (renewal_days > 60)
        & (renewal_days <= 90)
    ]
)

renewal_risk_df = renewal_df[
    renewal_days <= 90
] if not renewal_df.empty else pd.DataFrame()

annual_cost_at_risk = (
    pd.to_numeric(
        renewal_risk_df.get("annual_cost", pd.Series(dtype="float64")),
        errors="coerce"
    )
    .fillna(0)
    .sum()
)

r1, r2, r3, r4 = st.columns(4)

r1.metric(
    "Critical (0-30 Days)",
    critical
)

r2.metric(
    "Warning (31-60 Days)",
    warning
)

r3.metric(
    "Upcoming (61-90 Days)",
    upcoming
)

r4.metric(
    "Annual Cost at Risk",
    f"${annual_cost_at_risk:,.0f}"
)

if is_ceo_view and not renewal_df.empty:

    st.subheader("Renewals Requiring Executive Attention")

    executive_renewal_df = renewal_df[
        renewal_days <= 90
    ].copy()

    if not executive_renewal_df.empty:
        executive_renewal_df["days_until_renewal"] = pd.to_numeric(
            executive_renewal_df["days_until_renewal"],
            errors="coerce"
        ).fillna(99999)

        executive_renewal_df["Status"] = executive_renewal_df["days_until_renewal"].apply(
            lambda x: (
                "🔴 Critical"
                if x < 0 or x <= 30
                else "🟠 Warning"
                if x <= 60
                else "🟡 Upcoming"
                if x <= 90
                else "🟢 Healthy"
            )
        )

        executive_renewal_df = executive_renewal_df.rename(
            columns={
                "renewal_date": "Renewal Date",
                "days_until_renewal": "Days Remaining / Overdue",
                "annual_cost": "Annual Cost",
                "vendor": "Vendor",
                "application": "Application",
                "risk": "Risk",
            }
        )

        st.dataframe(
            executive_renewal_df[
                [
                    "Vendor",
                    "Application",
                    "Renewal Date",
                    "Days Remaining / Overdue",
                    "Annual Cost",
                    "Risk",
                    "Status",
                ]
            ],
            use_container_width=True,
            hide_index=True
        )
    else:
        st.success("No renewals require executive attention in the next 90 days.")

st.divider()

# --------------------------------------------------
# Duplicate Tool Detection
# --------------------------------------------------

st.subheader(
    "Duplicate Tool Detection"
)

duplicate_categories = len(duplicate_tool_rows)
potential_consolidation_areas = sum(
    safe_int(row.get("tool_count"))
    for row in duplicate_tool_rows
)

d1, d2 = st.columns(2)

d1.metric(
    "Duplicate Tool Categories",
    duplicate_categories
)

d2.metric(
    "Potential Consolidation Areas",
    potential_consolidation_areas
)

if duplicate_tool_rows:
    duplicate_df = pd.DataFrame(duplicate_tool_rows)
    visible_columns = [
        column for column in [
            "category",
            "tools",
        ]
        if column in duplicate_df.columns
    ]

    st.dataframe(
        duplicate_df[visible_columns],
        use_container_width=True,
        hide_index=True
    )

st.divider()

if not is_ceo_view:

    # --------------------------------------------------
    # Vendor Spend Trend
    # --------------------------------------------------

    st.subheader(
        "Top 5 Vendors by Spend Trend"
    )

    vendor_trend_df = pd.DataFrame(vendor_trend_rows)

    if (
        not vendor_trend_df.empty
        and "vendor" in vendor_trend_df.columns
        and "period" in vendor_trend_df.columns
        and "cost" in vendor_trend_df.columns
    ):
        vendor_trend_df["cost"] = pd.to_numeric(
            vendor_trend_df["cost"],
            errors="coerce"
        ).fillna(0)

        vendor_totals = (
            vendor_trend_df
            .groupby("vendor")["cost"]
            .sum()
            .sort_values(ascending=False)
            .head(5)
        )

        top_vendor_trend_df = vendor_trend_df[
            vendor_trend_df["vendor"].isin(vendor_totals.index)
        ]

        fig = px.line(
            top_vendor_trend_df,
            x="period",
            y="cost",
            color="vendor",
            markers=True,
            title="Top 5 Vendor Spend Trend"
        )

        st.plotly_chart(
            fig,
            use_container_width=True
        )
    else:
        st.info("No vendor trend data available.")

    st.divider()

    # --------------------------------------------------
    # Inactive License Summary
    # --------------------------------------------------

    st.subheader(
        "Inactive License Summary"
    )

    inactive_license_count = len(inactive_user_rows)
    inactive_license_savings = sum(
        safe_float(row.get("monthly_license_cost"))
        for row in inactive_user_rows
    )

    i1, i2 = st.columns(2)

    i1.metric(
        "Inactive Licenses",
        inactive_license_count
    )

    i2.metric(
        "Potential Savings",
        f"${inactive_license_savings:,.0f}"
    )

    st.divider()

    # --------------------------------------------------
    # Vendor Spend
    # --------------------------------------------------

    st.subheader(
        "Top SaaS Vendors"
    )

    if not saas_df.empty:

        vendor_spend = (
            saas_df
            .groupby("vendor_name")["cost"]
            .sum()
            .reset_index()
            .sort_values(
                "cost",
                ascending=False
            )
        )

        fig = px.bar(
            vendor_spend,
            x="vendor_name",
            y="cost",
            title="Vendor Spend"
        )

        st.plotly_chart(
            fig,
            use_container_width=True
        )

    # --------------------------------------------------
    # Licensed Software
    # --------------------------------------------------

    st.subheader(
        "Top Licensed Software"
    )

    if not license_df.empty:

        fig = px.bar(
            license_df,
            x="software_name",
            y="cost",
            title="License Cost by Software"
        )

        st.plotly_chart(
            fig,
            use_container_width=True
        )

    st.divider()

if is_ceo_view:

    st.divider()

    st.subheader("Executive Insight")

    st.info(
        f"""
        SaaS portfolio consists of {kpis['vendors']} active vendors.

        License utilization remains at {kpis['utilization']}%.

        Current license optimization opportunities total approximately ${estimated_waste:,.0f}.

        Contracts representing ${annual_cost_at_risk:,.0f} are approaching renewal within the next 90 days.

        Duplicate tool analysis indicates {duplicate_categories} consolidation opportunities requiring review.
        """
    )

# --------------------------------------------------
# Detail Tables
# --------------------------------------------------

if not is_ceo_view:

    st.subheader(
        "SaaS Spend Detail"
    )

    if not saas_df.empty:

        st.dataframe(
            saas_df,
            use_container_width=True,
            hide_index=True
        )

    st.subheader(
        "License Detail"
    )

    if not license_df.empty:

        st.dataframe(
            license_df,
            use_container_width=True,
            hide_index=True
        )
