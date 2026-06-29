from services.supabase_client import supabase
import streamlit as st
import pandas as pd
import plotly.express as px
from shared.session import init_session
from shared.auth import require_role
from components.sidebar_navigation import render_sidebar_navigation


def fetch_rows(table_name, limit=None):
    try:
        query = (
            supabase
            .table(table_name)
            .select("*")
        )
        if limit:
            query = query.limit(limit)
        response = query.execute()
        return response.data or []
    except Exception:
        return []


def fetch_one(table_name):
    rows = fetch_rows(table_name, limit=1)
    return rows[0] if rows else {}


def spend_value(row, new_key, old_key):
    return float(
        row.get(
            new_key,
            row.get(old_key, 0)
        )
        or 0
    )


st.set_page_config(
    page_title="Nexora Executive Command Center",
    layout="wide"
)

st.title("📊 Nexora Executive Command Center")

init_session()

require_role([
    "executive",
    "super_admin",
    "cio",
])

role = st.session_state.get("role", "Unknown")
render_sidebar_navigation(role)

# =====================================================
# LOAD EXECUTIVE SUMMARY
# =====================================================

# Executive marts are enterprise-level snapshots in the current model;
# keep these reads unscoped until org-partitioned marts are introduced.
summary = fetch_one("mart_executive_summary")

# =====================================================
# LOAD ENTERPRISE SPEND BREAKDOWN
# =====================================================

# Enterprise spend breakdown is a global mart snapshot for this dashboard.
spend_breakdown = fetch_one("mart_enterprise_spend_v2")

cloud_cost = spend_value(spend_breakdown, "cloud_spend", "cloud_cost")
saas_cost = spend_value(spend_breakdown, "saas_spend", "saas_cost")
msp_cost = spend_value(spend_breakdown, "msp_spend", "msp_cost")
license_cost = spend_value(spend_breakdown, "license_spend", "license_cost")

# =====================================================
# LOAD CLOUD COST DATA
# =====================================================

# Nexora Executive Command Center intentionally uses the enterprise-wide cost snapshot.
df = pd.DataFrame(fetch_rows("unified_cloud_costs"))

# =====================================================
# CLEAN DATA
# =====================================================

if "cost" not in df.columns:
    df["cost"] = 0
else:
    df["cost"] = pd.to_numeric(
        df["cost"],
        errors="coerce"
    ).fillna(0)

if "usage_date" in df.columns:
    df["usage_date"] = pd.to_datetime(
        df["usage_date"],
        errors="coerce"
    )

# =====================================================
# EXECUTIVE KPIs
# =====================================================

total_spend = float(
    summary.get("total_spend", 0)
)

potential_savings = float(
    summary.get("optimization_savings", 0)
)

governance_score = int(
    summary.get("governance_score", 0)
)

anomaly_count = int(
    summary.get("anomaly_count", 0)
)

cloud_accounts = (
    df["account_id"].nunique()
    if "account_id" in df.columns
    else df["cloud"].nunique()
    if "cloud" in df.columns
    else 0
)

# =====================================================
# KPI ROW
# =====================================================

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric(
        "💰 Enterprise Spend",
        f"${total_spend:,.0f}"
    )

with col2:
    st.metric(
        "☁️ Cloud Accounts",
        cloud_accounts
    )

with col3:
    st.metric(
        "🎯 Optimization Savings",
        f"${potential_savings:,.0f}"
    )

with col4:
    st.metric(
        "🛡 Governance Score",
        f"{governance_score}%"
    )

st.divider()

# =====================================================
# ENTERPRISE SPEND BREAKDOWN
# =====================================================

st.subheader("💼 Enterprise Spend Breakdown")

b1, b2, b3, b4 = st.columns(4)

with b1:
    st.metric(
        "☁️ Cloud Cost",
        f"${cloud_cost:,.0f}"
    )

with b2:
    st.metric(
        "🧩 SaaS Cost",
        f"${saas_cost:,.0f}"
    )

with b3:
    st.metric(
        "🛠 MSP Cost",
        f"${msp_cost:,.0f}"
    )

with b4:
    st.metric(
        "📄 License Cost",
        f"${license_cost:,.0f}"
    )

st.divider()

# =====================================================
# CLOUD DISTRIBUTION
# =====================================================

if "cloud" in df.columns and not df.empty:
    cloud_df = (
        df.groupby("cloud")["cost"]
        .sum()
        .reset_index()
    )
else:
    cloud_df = pd.DataFrame(
        [{"cloud": "No data", "cost": 0}]
    )

largest_cloud = (
    cloud_df.sort_values(
        "cost",
        ascending=False
    )
    .iloc[0]
)

# =====================================================
# EXECUTIVE SUMMARY
# =====================================================

st.subheader("📌 Executive Summary")

st.info(
    f"""
    Enterprise spend is currently **${total_spend:,.0f}**.

    Cloud Cost: **${cloud_cost:,.0f}**

    SaaS Cost: **${saas_cost:,.0f}**

    Managed Services Cost: **${msp_cost:,.0f}**

    License Cost: **${license_cost:,.0f}**

    **{largest_cloud['cloud']}** represents the highest cloud expenditure.

    Estimated optimization opportunity is approximately
    **${potential_savings:,.0f}**.

    Current governance posture remains healthy with a score of
    **{governance_score}%**.

    Active anomalies detected:
    **{anomaly_count}**
    """
)

# =====================================================
# CHARTS
# =====================================================

col1, col2 = st.columns(2)

with col1:

    st.subheader("☁️ Spend by Cloud")

    fig = px.pie(
        cloud_df,
        names="cloud",
        values="cost",
        hole=0.4
    )

    st.plotly_chart(
        fig,
        use_container_width=True
    )

with col2:

    st.subheader("📈 Daily Cost Trend")

    if "usage_date" in df.columns and not df.empty:
        trend_df = (
            df.dropna(subset=["usage_date"])
            .groupby("usage_date")["cost"]
            .sum()
            .reset_index()
        )
    else:
        trend_df = pd.DataFrame()

    if not trend_df.empty:
        fig = px.line(
            trend_df,
            x="usage_date",
            y="cost",
            markers=True
        )

        st.plotly_chart(
            fig,
            use_container_width=True
        )
    else:
        st.info("No daily cost trend data available.")

# =====================================================
# SERVICE CATEGORY BREAKDOWN
# =====================================================

if "service_category" in df.columns:

    st.subheader("🏷 Spend by Service Category")

    category_df = (
        df.groupby("service_category")["cost"]
        .sum()
        .reset_index()
        .sort_values(
            "cost",
            ascending=False
        )
    )

    fig = px.bar(
        category_df,
        x="service_category",
        y="cost",
        text_auto=".2s"
    )

    st.plotly_chart(
        fig,
        use_container_width=True
    )

# =====================================================
# TOP SERVICES
# =====================================================

if "service_name" in df.columns:

    st.subheader("🔥 Top Cost Drivers")

    top_services = (
        df.groupby("service_name")["cost"]
        .sum()
        .reset_index()
        .sort_values(
            "cost",
            ascending=False
        )
        .head(10)
    )

    fig = px.bar(
        top_services,
        x="cost",
        y="service_name",
        orientation="h"
    )

    st.plotly_chart(
        fig,
        use_container_width=True
    )

# =====================================================
# GOVERNANCE HEALTH
# =====================================================

st.subheader("🛡 Governance Health")

governance_df = pd.DataFrame(
    {
        "Metric": [
            "Governance Score",
            "Optimization Coverage",
            "Anomaly Management"
        ],
        "Score": [
            governance_score,
            85,
            max(0, 100 - anomaly_count * 5)
        ]
    }
)

fig = px.bar(
    governance_df,
    x="Metric",
    y="Score",
    text="Score"
)

st.plotly_chart(
    fig,
    use_container_width=True
)

# =====================================================
# RAW DATA
# =====================================================

with st.expander("🔍 View Raw Cost Data"):

    st.dataframe(
        df,
        use_container_width=True
    )
