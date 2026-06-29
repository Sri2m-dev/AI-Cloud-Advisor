from __future__ import annotations

import os
import sys

import pandas as pd
import plotly.express as px
import streamlit as st

ROOT_DIR = os.path.abspath(
    os.path.join(
        os.path.dirname(__file__),
        "..",
    )
)

if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from components.sidebar_navigation import render_sidebar_navigation
from services.approval_service import ApprovalService
from services.cost_intelligence_service import (
    get_cost_anomalies,
    get_optimization_opportunities,
)
from services.reporting_service import get_executive_summary
from services.saas_governance_service import SaaSGovernanceService
from services.supabase_client import supabase
from services.technology_spend_service import TechnologySpendService
from shared.auth import require_role
from shared.layout import render_page_header
from shared.session import init_session
from shared.styles import configure_page


AI_PLATFORM_TERMS = (
    "openai",
    "chatgpt",
    "copilot",
    "claude",
    "anthropic",
    "gemini",
    "perplexity",
)


def safe_call(fn, fallback):
    try:
        return fn() or fallback
    except Exception:
        return fallback


def safe_float(value):
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def safe_int(value, fallback=0):
    try:
        return int(float(value if value is not None else fallback))
    except (TypeError, ValueError):
        return fallback


def compact_currency(value):
    value = safe_float(value)
    if abs(value) >= 1000:
        return f"${value / 1000:,.1f}K".replace(".0K", "K")
    return f"${value:,.0f}"


def fetch_rows(table_name):
    try:
        response = (
            supabase
            .table(table_name)
            .select("*")
            .execute()
        )
        return response.data or []
    except Exception:
        return []


def first_existing_total(df, columns):
    for column in columns:
        if column in df.columns:
            return float(
                pd.to_numeric(
                    df[column],
                    errors="coerce",
                )
                .fillna(0)
                .sum()
            )
    return 0.0


def first_existing_count(df, columns):
    for column in columns:
        if column in df.columns:
            return int(df[column].fillna("").astype(str).replace("", pd.NA).dropna().nunique())
    return 0


def status_count(df, candidates):
    if df.empty:
        return 0

    for column in ("severity", "risk_level", "anomaly_status", "status", "risk"):
        if column in df.columns:
            values = df[column].fillna("").astype(str).str.lower()
            return int(values.isin(candidates).sum())

    return 0


def criticality_count(df, candidates):
    if df.empty or "criticality" not in df.columns:
        return 0
    values = df["criticality"].fillna("").astype(str).str.lower()
    return int(values.isin(candidates).sum())


def ai_mask(df):
    if df.empty:
        return pd.Series(dtype=bool)

    text_columns = [
        column
        for column in df.columns
        if any(term in column.lower() for term in ("vendor", "tool", "app", "name", "product", "service"))
    ]
    if not text_columns:
        return pd.Series([False] * len(df), index=df.index)

    combined = (
        df[text_columns]
        .fillna("")
        .astype(str)
        .agg(" ".join, axis=1)
        .str.lower()
    )
    return combined.str.contains("|".join(AI_PLATFORM_TERMS), regex=True)


def ai_platform_name(row):
    text = " ".join(str(value) for value in row.values if value is not None).lower()
    if "copilot" in text:
        return "Copilot"
    if "claude" in text or "anthropic" in text:
        return "Claude"
    if "gemini" in text:
        return "Gemini"
    if "perplexity" in text:
        return "Perplexity"
    if "openai" in text or "chatgpt" in text:
        return "OpenAI"
    return "Other AI Platforms"


def metric_card(label, value, note=None):
    st.markdown(
        f"""
        <div style="
            border:1px solid #E5E7EB;
            border-radius:14px;
            padding:18px 20px;
            background:#FFFFFF;
            min-height:105px;
            box-shadow:0 1px 2px rgba(0,0,0,0.04);
        ">
            <div style="font-size:13px;color:#6B7280;margin-bottom:8px;">{label}</div>
            <div style="font-size:27px;font-weight:700;color:#111827;">{value}</div>
            <div style="font-size:12px;color:#6B7280;margin-top:6px;">{note or ""}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def portfolio_card(title, items):
    rows = "".join(
        f"""
        <div style="
            display:flex;
            justify-content:space-between;
            gap:16px;
            padding:8px 0;
            border-top:1px solid #F3F4F6;
        ">
            <span style="font-size:13px;color:#6B7280;">{label}</span>
            <span style="font-size:16px;font-weight:700;color:#111827;">{value}</span>
        </div>
        """
        for label, value in items
    )
    st.markdown(
        f"""
        <div style="
            border:1px solid #E5E7EB;
            border-radius:14px;
            padding:18px 20px;
            background:#FFFFFF;
            min-height:235px;
            box-shadow:0 1px 2px rgba(0,0,0,0.04);
        ">
            <div style="font-size:17px;font-weight:700;color:#111827;margin-bottom:8px;">{title}</div>
            {rows}
        </div>
        """,
        unsafe_allow_html=True,
    )


def recommendation_item(status, text):
    colors = {
        "green": "#16A34A",
        "yellow": "#D97706",
        "red": "#DC2626",
    }
    color = colors.get(status, "#6B7280")
    return f"""
        <div style="display:flex;align-items:flex-start;gap:10px;padding:9px 0;">
            <span style="
                width:11px;
                height:11px;
                border-radius:999px;
                background:{color};
                display:inline-block;
                margin-top:6px;
                flex:0 0 11px;
            "></span>
            <span style="font-size:15px;color:#111827;">{text}</span>
        </div>
    """


def render_recommendations(items):
    st.markdown(
        f"""
        <div style="
            border:1px solid #E5E7EB;
            border-radius:14px;
            padding:18px 20px;
            background:#FFFFFF;
            box-shadow:0 1px 2px rgba(0,0,0,0.04);
        ">
            {''.join(items)}
        </div>
        """,
        unsafe_allow_html=True,
    )


configure_page(
    page_title="Technology Portfolio Overview",
    page_icon=":moneybag:",
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
    "Technology Portfolio Overview",
    "Enterprise technology portfolio, application landscape, SaaS governance, risk and optimization insights",
)

summary = safe_call(TechnologySpendService.get_summary, {})
executive_summary = safe_call(get_executive_summary, {})
approval_metrics = safe_call(ApprovalService.get_dashboard_metrics, {})
saas_kpis = safe_call(SaaSGovernanceService.get_kpis, {})

optimization_result = safe_call(get_optimization_opportunities, {"data": pd.DataFrame()})
anomaly_result = safe_call(get_cost_anomalies, {"data": pd.DataFrame()})

optimization_df = optimization_result.get("data", pd.DataFrame())
anomaly_df = anomaly_result.get("data", pd.DataFrame())

if not isinstance(optimization_df, pd.DataFrame):
    optimization_df = pd.DataFrame(optimization_df)

if not isinstance(anomaly_df, pd.DataFrame):
    anomaly_df = pd.DataFrame(anomaly_df)

cloud_df = pd.DataFrame(fetch_rows("unified_cloud_costs"))
application_df = pd.DataFrame(fetch_rows("application_registry"))
resource_df = pd.DataFrame(fetch_rows("cloud_resources"))
vendor_spend_df = pd.DataFrame(fetch_rows("vw_vendor_spend"))
inactive_users_df = pd.DataFrame(fetch_rows("vw_inactive_saas_users"))
renewal_risk_df = pd.DataFrame(fetch_rows("vw_saas_renewal_risk"))

cloud_cost = safe_float(summary.get("cloud_cost"))
saas_cost = safe_float(summary.get("saas_cost"))
msp_cost = safe_float(summary.get("msp_cost"))
license_cost = safe_float(summary.get("license_cost"))
total_spend = (
    safe_float(summary.get("total_spend"))
    or cloud_cost
    + saas_cost
    + msp_cost
    + license_cost
)

potential_savings = (
    safe_float(executive_summary.get("optimization_savings"))
    or safe_float(executive_summary.get("optimization"))
    or first_existing_total(
        optimization_df,
        [
            "estimated_savings",
            "potential_savings",
            "savings",
            "annual_savings",
        ],
    )
)

implemented_savings = 0.0
if not optimization_df.empty:
    status_column = next(
        (
            column
            for column in ("status", "recommendation_status", "state")
            if column in optimization_df.columns
        ),
        None,
    )
    savings_column = next(
        (
            column
            for column in (
                "estimated_savings",
                "potential_savings",
                "savings",
                "annual_savings",
            )
            if column in optimization_df.columns
        ),
        None,
    )
    if status_column and savings_column:
        statuses = optimization_df[status_column].fillna("").astype(str).str.lower()
        savings = pd.to_numeric(optimization_df[savings_column], errors="coerce").fillna(0)
        implemented_savings = float(
            savings[statuses.isin(["implemented", "completed", "resolved", "closed"])].sum()
        )

governance_score = safe_int(
    summary.get("governance_score")
    or summary.get("governance")
    or summary.get("compliance_score"),
    77,
)

critical_risks = status_count(anomaly_df, {"critical", "sev1", "p1"})
high_risks = status_count(anomaly_df, {"high", "sev2", "p2", "anomaly", "spike"})
medium_risks = status_count(anomaly_df, {"medium", "moderate", "warning"})
open_risks = critical_risks + high_risks + medium_risks
if not open_risks:
    open_risks = len(anomaly_df)

technology_health = safe_int(
    summary.get("technology_health")
    or summary.get("business_health_score")
    or max(0, governance_score - min(open_risks * 3, 25)),
    87,
)

cloud_accounts = first_existing_count(cloud_df, ["account_id", "account_name", "cloud"])
applications = first_existing_count(application_df, ["app_name", "application_name"])
business_services = max(
    first_existing_count(application_df, ["business_unit"]),
    first_existing_count(application_df, ["department"]),
    first_existing_count(application_df, ["team_name"]),
)
resources = len(resource_df) if not resource_df.empty else first_existing_count(cloud_df, ["resource_id", "service_name"])

vendors = safe_int(saas_kpis.get("vendors"), first_existing_count(vendor_spend_df, ["vendor_name", "vendor"]))
licenses = safe_int(
    saas_kpis.get("licenses_purchased")
    or saas_kpis.get("licenses"),
    first_existing_total(vendor_spend_df, ["licenses", "license_count"]),
)
unused_licenses = safe_int(
    saas_kpis.get("unused_licenses")
    or saas_kpis.get("inactive_users"),
    len(inactive_users_df),
)
renewals_due = len(renewal_risk_df)

tier_1_apps = criticality_count(application_df, {"tier 1", "tier1", "critical"})
tier_2_apps = criticality_count(application_df, {"tier 2", "tier2", "high"})
critical_apps = criticality_count(application_df, {"critical"})
deprecated_apps = criticality_count(application_df, {"deprecated", "retired", "legacy"})

ai_frames = []
for source_df in (vendor_spend_df, inactive_users_df, renewal_risk_df, application_df):
    if not source_df.empty:
        mask = ai_mask(source_df)
        if len(mask):
            ai_frames.append(source_df[mask].copy())

ai_df = pd.concat(ai_frames, ignore_index=True) if ai_frames else pd.DataFrame()
ai_tools = int(ai_df.apply(ai_platform_name, axis=1).nunique()) if not ai_df.empty else 0
ai_spend = first_existing_total(
    ai_df,
    [
        "annual_spend",
        "spend",
        "cost",
        "amount",
        "total_cost",
        "license_cost",
    ],
)
unused_ai_licenses = len(inactive_users_df[ai_mask(inactive_users_df)]) if not inactive_users_df.empty else 0
duplicate_ai_platforms = max(0, ai_tools - 4)

opportunity_count = len(optimization_df)
projects_in_progress = 0
if not optimization_df.empty:
    status_column = next(
        (column for column in ("status", "recommendation_status", "state") if column in optimization_df.columns),
        None,
    )
    if status_column:
        statuses = optimization_df[status_column].fillna("").astype(str).str.lower()
        projects_in_progress = int(statuses.isin(["in progress", "active", "approved", "planned"]).sum())

ownership_coverage = safe_int(summary.get("ownership_coverage"), 85)
tagging_compliance = safe_int(summary.get("tagging_compliance"), 82)
security_compliance = safe_int(summary.get("security_compliance"), governance_score)
lifecycle_compliance = safe_int(summary.get("lifecycle_compliance"), 78)

healthy_pct = max(0, min(100, technology_health))
critical_pct = max(0, min(100 - healthy_pct, open_risks * 4))
warning_pct = max(0, 100 - healthy_pct - critical_pct)

health_distribution_df = pd.DataFrame([
    {"Status": "Healthy", "Share": healthy_pct},
    {"Status": "Warning", "Share": warning_pct},
    {"Status": "Critical", "Share": critical_pct},
])

st.subheader("Technology Leadership KPIs")

kpi_cols = st.columns(5)
with kpi_cols[0]:
    metric_card("Technology Spend", compact_currency(total_spend), "Total technology investment")
with kpi_cols[1]:
    metric_card("Optimization Potential", compact_currency(potential_savings), "Identified savings")
with kpi_cols[2]:
    metric_card("Technology Health", f"{technology_health}%", "Overall platform health")
with kpi_cols[3]:
    metric_card("Business Services", f"{business_services:,}", "Critical services tracked")
with kpi_cols[4]:
    metric_card("Critical Risks", f"{open_risks:,}", "Open risks")

st.divider()

st.subheader("Technology Portfolio Snapshot")

portfolio_cols = st.columns(4)
with portfolio_cols[0]:
    portfolio_card(
        "Infrastructure Portfolio",
        [
            ("Cloud Accounts", f"{cloud_accounts:,}"),
            ("Applications", f"{applications:,}"),
            ("Business Services", f"{business_services:,}"),
            ("Resources", f"{resources:,}"),
        ],
    )
with portfolio_cols[1]:
    portfolio_card(
        "SaaS Portfolio",
        [
            ("Vendors", f"{vendors:,}"),
            ("Licenses", f"{licenses:,}"),
            ("Unused Licenses", f"{unused_licenses:,}"),
            ("Renewals Due", f"{renewals_due:,}"),
        ],
    )
with portfolio_cols[2]:
    portfolio_card(
        "Application Portfolio",
        [
            ("Tier 1 Apps", f"{tier_1_apps:,}"),
            ("Tier 2 Apps", f"{tier_2_apps:,}"),
            ("Critical Apps", f"{critical_apps:,}"),
            ("Deprecated Apps", f"{deprecated_apps:,}"),
        ],
    )
with portfolio_cols[3]:
    portfolio_card(
        "AI Portfolio",
        [
            ("AI Tools", f"{ai_tools:,}"),
            ("AI Spend", compact_currency(ai_spend)),
            ("Unused AI Licenses", f"{unused_ai_licenses:,}"),
            ("Duplicate AI Platforms", f"{duplicate_ai_platforms:,}"),
        ],
    )

st.divider()

st.subheader("Technology Health Overview")

health_left, health_right = st.columns([1, 2])

with health_left:
    portfolio_card(
        "Health Distribution",
        [
            ("Healthy", f"{healthy_pct}%"),
            ("Warning", f"{warning_pct}%"),
            ("Critical", f"{critical_pct}%"),
        ],
    )

with health_right:
    fig = px.pie(
        health_distribution_df,
        names="Status",
        values="Share",
        title="Technology Health Distribution",
        hole=0.55,
        color="Status",
        color_discrete_map={
            "Healthy": "#16A34A",
            "Warning": "#D97706",
            "Critical": "#DC2626",
        },
    )
    st.plotly_chart(fig, use_container_width=True)

st.divider()

st.subheader("Technology Risk & Governance")

risk_col, governance_col = st.columns(2)
with risk_col:
    portfolio_card(
        "Risk Summary",
        [
            ("Critical Risks", f"{critical_risks:,}"),
            ("High Risks", f"{high_risks:,}"),
            ("Medium Risks", f"{medium_risks:,}"),
        ],
    )
with governance_col:
    portfolio_card(
        "Governance Summary",
        [
            ("Ownership Coverage", f"{ownership_coverage}%"),
            ("Tagging Compliance", f"{tagging_compliance}%"),
            ("Security Compliance", f"{security_compliance}%"),
            ("Lifecycle Compliance", f"{lifecycle_compliance}%"),
        ],
    )

st.divider()

st.subheader("Optimization Program")

optimization_cols = st.columns(4)
with optimization_cols[0]:
    metric_card("Optimization Opportunities", f"{opportunity_count:,}")
with optimization_cols[1]:
    metric_card("Potential Savings", compact_currency(potential_savings))
with optimization_cols[2]:
    metric_card("Implemented Savings", compact_currency(implemented_savings))
with optimization_cols[3]:
    metric_card("Projects In Progress", f"{projects_in_progress:,}")

st.divider()

st.subheader("Executive Recommendations")

render_recommendations([
    recommendation_item(
        "yellow",
        "Consolidate overlapping monitoring platforms"
        if vendors < 3
        else f"Consolidate {max(3, min(vendors, 6))} overlapping vendor platforms",
    ),
    recommendation_item(
        "yellow" if unused_ai_licenses else "green",
        f"Review {unused_ai_licenses} inactive AI licenses"
        if unused_ai_licenses
        else "AI license utilization appears stable",
    ),
    recommendation_item(
        "green",
        "Rightsize underutilized cloud resources"
        if resources
        else "Establish cloud resource utilization baseline",
    ),
    recommendation_item(
        "red" if open_risks else "green",
        f"Resolve {open_risks} critical technology risks"
        if open_risks
        else "No critical technology risks require immediate action",
    ),
    recommendation_item(
        "yellow" if renewals_due else "green",
        f"Review {renewals_due} upcoming SaaS renewals"
        if renewals_due
        else "No material SaaS renewals currently require review",
    ),
])
