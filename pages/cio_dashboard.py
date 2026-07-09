from __future__ import annotations

import os
import sys

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

from components.cards import (
    render_health_card,
    render_insight_card,
    render_kpi_card,
    render_metric_card,
    render_risk_card,
)
from components.layout import render_section
from components.navigation import render_enterprise_sidebar
from components.shared import (
    render_ai_narrative,
    render_business_context,
    render_evidence_panel,
    render_executive_summary,
    render_reconciliation_panel,
)
from components.sidebar_navigation import PAGE_PATHS, ROLE_PAGES
from services.cio_dashboard_certification_service import CioDashboardCertificationService
from services.cio_workspace_service import CIOWorkspaceService
from shared.auth import require_role
from shared.layout import render_page_header
from shared.session import init_session
from shared.streamlit_compat import plotly_chart
from shared.styles import configure_page


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
    return CioDashboardCertificationService.format_compact_currency(value)


configure_page(
    page_title="CIO Technology Command Center",
    page_icon="T",
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
render_enterprise_sidebar(
    role,
    page_paths=PAGE_PATHS,
    role_pages=ROLE_PAGES,
    active_page=PAGE_PATHS["Technology Portfolio Overview"],
)

workspace = CIOWorkspaceService.get_workspace()
dashboard = workspace["dashboard"]
metrics = dashboard["metrics"]
dataframes = dashboard["dataframes"]
reconciliation_cards = workspace["reconciliation_cards"]
business_context = workspace["business_context"]
evidence = dashboard["evidence"]

total_spend = metrics["total_spend"]
potential_savings = metrics["potential_savings"]
implemented_savings = metrics["implemented_savings"]
technology_health = metrics["technology_health"]
open_risks = metrics["open_risks"]
critical_risks = metrics["critical_risks"]
high_risks = metrics["high_risks"]
medium_risks = metrics["medium_risks"]
cloud_accounts = metrics["cloud_accounts"]
applications = metrics["applications"]
business_services = metrics["business_services"]
resources = metrics["resources"]
vendors = metrics["vendors"]
unused_licenses = metrics["unused_licenses"]
deprecated_apps = metrics["deprecated_apps"]
ai_tools = metrics["ai_tools"]
unused_ai_licenses = metrics["unused_ai_licenses"]
duplicate_ai_platforms = metrics["duplicate_ai_platforms"]
opportunity_count = metrics["opportunity_count"]
projects_in_progress = metrics["projects_in_progress"]
ownership_coverage = metrics["ownership_coverage"]
tagging_compliance = metrics["tagging_compliance"]
security_compliance = metrics["security_compliance"]
lifecycle_compliance = metrics["lifecycle_compliance"]
healthy_pct = metrics["healthy_pct"]
warning_pct = metrics["warning_pct"]
critical_pct = metrics["critical_pct"]
health_distribution_df = dataframes["health_distribution"]

def health_status(value):
    if safe_float(value) >= 85:
        return "healthy"
    if safe_float(value) >= 70:
        return "warning"
    return "critical"


def risk_status(value):
    return "critical" if safe_int(value) else "healthy"


def render_certification_summary():
    render_executive_summary(workspace["summary"])
    render_reconciliation_panel(reconciliation_cards)
    render_business_context(business_context)
    render_ai_narrative(
        "AI CIO Workspace Interpretation",
        workspace.get("ai_narrative") or "CIO workspace interpretation is unavailable.",
        description="AI-assisted interpretation of CIO workspace posture, financial reconciliation, and business architecture signals.",
    )


def render_evidence_section():
    render_evidence_panel(evidence)


def render_cio_workspace_content():
    render_certification_summary()

    render_section(
        "CIO Decision Summary",
        "Technology health, spend, risk, SaaS exposure, application landscape, and optimization priorities.",
    )

    kpi_cols = st.columns(5)
    with kpi_cols[0]:
        render_kpi_card(
            "Technology Spend",
            compact_currency(total_spend),
            "Total technology investment",
            icon="cost",
            status="info",
        )
    with kpi_cols[1]:
        render_metric_card(
            "Optimization Potential",
            compact_currency(potential_savings),
            "Identified savings",
            icon="savings",
            status="warning" if potential_savings else "healthy",
        )
    with kpi_cols[2]:
        render_health_card(
            "Technology Health",
            f"{technology_health}%",
            "Overall platform health",
            icon="health",
            status=health_status(technology_health),
        )
    with kpi_cols[3]:
        render_metric_card(
            "Business Services",
            f"{business_services:,}",
            "Critical services tracked",
            icon="enterprise",
            status="info",
        )
    with kpi_cols[4]:
        render_risk_card(
            "Critical Risks",
            f"{open_risks:,}",
            "Open technology risks",
            icon="risk",
            status=risk_status(open_risks),
        )

    render_section(
        "Technology Portfolio Snapshot",
        "Infrastructure, SaaS, application, and AI portfolio signals for CIO review.",
    )
    portfolio_cols = st.columns(4)
    with portfolio_cols[0]:
        render_metric_card("Cloud Accounts", f"{cloud_accounts:,}", "Connected cloud accounts", icon="cloud", status="info")
        render_metric_card("Resources", f"{resources:,}", "Cloud and technology resources", icon="technology", status="info")
    with portfolio_cols[1]:
        render_metric_card("Applications", f"{applications:,}", "Application records", icon="application", status="info")
        render_risk_card("Deprecated Apps", f"{deprecated_apps:,}", "Legacy or retired applications", icon="risk", status="warning" if deprecated_apps else "healthy")
    with portfolio_cols[2]:
        render_metric_card("SaaS Vendors", f"{vendors:,}", "Vendors in scope", icon="saas", status="info")
        render_risk_card("Unused Licenses", f"{unused_licenses:,}", "Inactive SaaS or license exposure", icon="savings", status="warning" if unused_licenses else "healthy")
    with portfolio_cols[3]:
        render_metric_card("AI Tools", f"{ai_tools:,}", "Detected AI platforms", icon="intelligence", status="info")
        render_risk_card("Duplicate AI Platforms", f"{duplicate_ai_platforms:,}", "Potential overlap in AI tooling", icon="governance", status="warning" if duplicate_ai_platforms else "healthy")

    render_section(
        "Technology Health Overview",
        "Portfolio health distribution and risk concentration across the technology estate.",
    )
    health_left, health_right = st.columns([1, 2])
    with health_left:
        render_health_card(
            "Healthy",
            f"{healthy_pct}%",
            "Portfolio in healthy posture",
            icon="success",
            status="healthy",
        )
        render_risk_card(
            "Warning / Critical",
            f"{warning_pct + critical_pct}%",
            "Portfolio requiring CIO attention",
            icon="alert",
            status="warning" if warning_pct + critical_pct else "healthy",
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
        plotly_chart(fig)

    render_section(
        "Risk & Governance",
        "Risk severity and governance controls requiring technology leadership attention.",
    )
    risk_cols = st.columns(3)
    with risk_cols[0]:
        render_risk_card("Critical Risks", f"{critical_risks:,}", "Immediate attention", icon="alert", status=risk_status(critical_risks))
    with risk_cols[1]:
        render_risk_card("High Risks", f"{high_risks:,}", "Active mitigation", icon="risk", status="warning" if high_risks else "healthy")
    with risk_cols[2]:
        render_risk_card("Medium Risks", f"{medium_risks:,}", "Monitor and govern", icon="governance", status="warning" if medium_risks else "healthy")

    governance_cols = st.columns(4)
    with governance_cols[0]:
        render_metric_card("Ownership Coverage", f"{ownership_coverage}%", "Owner mapping", icon="governance", status=health_status(ownership_coverage))
    with governance_cols[1]:
        render_metric_card("Tagging Compliance", f"{tagging_compliance}%", "Cost and asset tags", icon="governance", status=health_status(tagging_compliance))
    with governance_cols[2]:
        render_metric_card("Security Compliance", f"{security_compliance}%", "Security controls", icon="security", status=health_status(security_compliance))
    with governance_cols[3]:
        render_metric_card("Lifecycle Compliance", f"{lifecycle_compliance}%", "Lifecycle controls", icon="technology", status=health_status(lifecycle_compliance))

    render_section(
        "Optimization Program",
        "Savings pipeline and active optimization execution.",
    )
    optimization_cols = st.columns(4)
    with optimization_cols[0]:
        render_metric_card("Opportunities", f"{opportunity_count:,}", "Optimization records", icon="savings", status="info")
    with optimization_cols[1]:
        render_metric_card("Potential Savings", compact_currency(potential_savings), "Savings pipeline", icon="cost", status="warning" if potential_savings else "healthy")
    with optimization_cols[2]:
        render_metric_card("Implemented Savings", compact_currency(implemented_savings), "Completed savings", icon="success", status="healthy")
    with optimization_cols[3]:
        render_metric_card("Projects In Progress", f"{projects_in_progress:,}", "Approved or active work", icon="workflow", status="info")

    render_section(
        "CIO Attention Required",
        "Prioritized actions based on portfolio, AI, license, renewal, cloud, and risk signals.",
    )
    recommendation_cols = st.columns(2)
    with recommendation_cols[0]:
        render_insight_card(
            "Platform Rationalization",
            "Vendor consolidation",
            description=(
                "Consolidate overlapping monitoring platforms"
                if vendors < 3
                else f"Consolidate {max(3, min(vendors, 6))} overlapping vendor platforms"
            ),
            icon="enterprise",
            status="warning",
        )
        render_insight_card(
            "Cloud Optimization",
            "Rightsizing",
            description=(
                "Rightsize underutilized cloud resources"
                if resources
                else "Establish cloud resource utilization baseline"
            ),
            icon="cloud",
            status="info",
        )
    with recommendation_cols[1]:
        render_insight_card(
            "AI License Utilization",
            "License review",
            description=(
                f"Review {unused_ai_licenses} inactive AI licenses"
                if unused_ai_licenses
                else "AI license utilization appears stable"
            ),
            icon="intelligence",
            status="warning" if unused_ai_licenses else "healthy",
        )
        render_insight_card(
            "Technology Risk",
            "Risk remediation",
            description=(
                f"Resolve {open_risks} critical technology risks"
                if open_risks
                else "No critical technology risks require immediate action"
            ),
            icon="risk",
            status="critical" if open_risks else "healthy",
        )

    render_evidence_section()


render_page_header(
    "CIO Technology Command Center",
    "CIO workspace for enterprise technology health, spend, SaaS exposure, risk, and optimization decisions.",
)
render_cio_workspace_content()
