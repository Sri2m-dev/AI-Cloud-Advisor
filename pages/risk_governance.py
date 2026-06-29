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
from components.cards import (
    render_approval_card,
    render_insight_card,
    render_kpi_card,
    render_metric_card,
    render_risk_card,
)
from components.layout import render_page, render_section
from components.navigation import render_enterprise_sidebar
from components.sidebar_navigation import PAGE_PATHS, ROLE_PAGES
from components.tables import data_table

from services.approval_service import ApprovalService
from services.cost_intelligence_service import (
    get_cost_anomalies,
    get_optimization_opportunities,
    get_recommendations,
)


configure_page(
    page_title="Risk & Governance | Nexora",
    page_icon="⚠️",
)

init_session()

require_role([
    "executive",
    "cio",
    "technical",
    "finance",
    "super_admin",
])

role = st.session_state.get("role", "Unknown")
render_enterprise_sidebar(
    role,
    page_paths=PAGE_PATHS,
    role_pages=ROLE_PAGES,
    active_page=PAGE_PATHS["Risk & Governance"],
)

# --------------------------------------------------
# DATA LOAD
# --------------------------------------------------

anomaly_resp = get_cost_anomalies()
optimization_resp = get_optimization_opportunities()
recommendation_resp = get_recommendations()

anomaly_df = anomaly_resp.get("data", pd.DataFrame())
optimization_df = optimization_resp.get("data", pd.DataFrame())
recommendation_df = recommendation_resp.get("data", pd.DataFrame())

approval_metrics = ApprovalService.get_dashboard_metrics()
sla_metrics = ApprovalService.get_sla_metrics()
pending_approvals = ApprovalService.get_pending_approvals() or []

# --------------------------------------------------
# KPI CALCULATIONS
# --------------------------------------------------

active_risks = len(anomaly_df) if not anomaly_df.empty else 0

critical_risks = 0
risk_status_column = None

for column in ["anomaly_status", "status", "severity", "risk_level"]:
    if column in anomaly_df.columns:
        risk_status_column = column
        break

if risk_status_column:
    critical_risks = (
        anomaly_df[risk_status_column]
        .astype(str)
        .str.lower()
        .isin(["critical", "high", "anomaly", "spike"])
        .sum()
    )

optimization_items = len(optimization_df) if not optimization_df.empty else 0

potential_savings = 0
if not recommendation_df.empty and "estimated_savings" in recommendation_df.columns:
    potential_savings = pd.to_numeric(
        recommendation_df["estimated_savings"],
        errors="coerce",
    ).fillna(0).sum()

pending_count = approval_metrics.get("pending", len(pending_approvals))
sla_compliance = sla_metrics.get("sla_compliance", 0)

# Simple governance score until mature governance mart is finalized
governance_score = max(
    0,
    min(
        100,
        100
        - (critical_risks * 10)
        - (pending_count * 3)
        + min(10, sla_compliance / 10),
    ),
)

def render_governance_content():
    # --------------------------------------------------
    # EXECUTIVE SUMMARY
    # --------------------------------------------------

    render_section(
        "Executive Risk Summary",
        "Board-level view of governance posture, active risk, approval pressure, and savings exposure.",
        divider=False,
    )

    k1, k2, k3, k4, k5, k6 = st.columns(6)

    with k1:
        render_kpi_card(
            "Governance Score",
            f"{governance_score:.0f}%",
            icon="governance",
            status="healthy" if governance_score >= 75 else "warning",
        )
    with k2:
        render_metric_card("Active Risks", active_risks, icon="risk", status="warning" if active_risks else "healthy")
    with k3:
        render_risk_card("Critical Risks", int(critical_risks), status="critical" if critical_risks else "healthy")
    with k4:
        render_approval_card("Pending Approvals", pending_count, status="watch" if pending_count else "healthy")
    with k5:
        render_metric_card("Optimization Items", optimization_items, icon="ai", status="info")
    with k6:
        render_kpi_card("Potential Savings", f"${potential_savings:,.0f}", icon="cost", status="warning" if potential_savings else "healthy")

    render_insight_card(
        title="Executive Governance Summary",
        value=f"{governance_score:.0f}% Governance Score",
        description=(
            f"Enterprise governance score is currently {governance_score:.0f}%. "
            f"There are {active_risks} active risk records, including {int(critical_risks)} critical or high-priority risks. "
            f"The approval queue currently has {pending_count} pending items requiring governance attention. "
            f"The platform has identified {optimization_items} optimization-linked exposure items with potential savings of ${potential_savings:,.0f}."
        ),
        icon="governance",
        status="healthy" if governance_score >= 75 else "warning",
    )

    # --------------------------------------------------
    # RISK + GOVERNANCE VISUALS
    # --------------------------------------------------

    left, right = st.columns(2)

    with left:
        render_section(
            "Risk Posture",
            "Distribution of active risk records by status or severity.",
            divider=True,
        )

        if risk_status_column and not anomaly_df.empty:
            risk_summary = (
                anomaly_df[risk_status_column]
                .fillna("Unknown")
                .astype(str)
                .value_counts()
                .reset_index()
            )
            risk_summary.columns = ["Risk Status", "Count"]

            fig = px.bar(
                risk_summary,
                x="Risk Status",
                y="Count",
                title="Risk Distribution",
            )

            st.plotly_chart(fig, use_container_width=True)
        else:
            render_insight_card(
                title="No Risk Posture Data",
                description="No risk posture data is currently available.",
                status="healthy",
            )

    with right:
        render_section(
            "Decision Queue Health",
            "Approval queue status across pending, approved, rejected, and escalated decisions.",
            divider=True,
        )

        approval_summary = pd.DataFrame([
            {"Status": "Pending", "Count": approval_metrics.get("pending", 0)},
            {"Status": "Approved", "Count": approval_metrics.get("approved", 0)},
            {"Status": "Rejected", "Count": approval_metrics.get("rejected", 0)},
            {"Status": "Escalated", "Count": approval_metrics.get("escalated", 0)},
        ])

        fig = px.bar(
            approval_summary,
            x="Status",
            y="Count",
            title="Approval Queue Status",
        )

        st.plotly_chart(fig, use_container_width=True)

    # --------------------------------------------------
    # OPTIMIZATION EXPOSURE
    # --------------------------------------------------

    render_section(
        "Savings & Optimization Exposure",
        "Top governance-linked optimization exposures by service cost.",
        divider=True,
    )

    if not optimization_df.empty and {"service_name", "total_cost"}.issubset(optimization_df.columns):
        top_optimization_df = (
            optimization_df
            .copy()
            .assign(
                total_cost=pd.to_numeric(
                    optimization_df["total_cost"],
                    errors="coerce",
                ).fillna(0)
            )
            .sort_values("total_cost", ascending=False)
            .head(10)
        )

        fig = px.bar(
            top_optimization_df,
            x="service_name",
            y="total_cost",
            color="cloud" if "cloud" in top_optimization_df.columns else None,
            title="Top Savings & Optimization Exposures",
        )

        st.plotly_chart(fig, use_container_width=True)
    else:
        render_insight_card(
            title="No Savings Exposure",
            description="No savings and optimization exposure data is currently available.",
            status="healthy",
        )

    render_section(
        "Business Impact Areas",
        "Translation of risk and governance signals into business impact categories.",
        divider=True,
    )

    impact_cols = st.columns(5)
    with impact_cols[0]:
        render_risk_card(
            "Financial Exposure",
            f"${potential_savings:,.0f}",
            description="Optimization and spend exposure that may affect budget outcomes.",
            status="warning" if potential_savings else "healthy",
        )
    with impact_cols[1]:
        render_risk_card(
            "Operational Continuity",
            active_risks,
            description="Active risk records that may affect service or delivery reliability.",
            status="warning" if active_risks else "healthy",
        )
    with impact_cols[2]:
        render_metric_card(
            "Compliance Readiness",
            f"{governance_score:.0f}%",
            description="Governance score as a directional readiness signal.",
            icon="governance",
            status="healthy" if governance_score >= 75 else "warning",
        )
    with impact_cols[3]:
        render_approval_card(
            "Executive Decision Load",
            pending_count,
            description="Pending governance decisions awaiting approval.",
            status="watch" if pending_count else "healthy",
        )
    with impact_cols[4]:
        render_insight_card(
            "Optimization Opportunity",
            optimization_items,
            description="Optimization-linked exposure items requiring business prioritization.",
            icon="ai",
            status="info",
        )

    # --------------------------------------------------
    # DEFINITIONS
    # --------------------------------------------------

    render_section(
        "Definitions & Methodology",
        "Plain-language explanations for client and executive interpretation.",
        divider=True,
    )

    definition_rows = [
        (
            "What does Governance Score mean?",
            "A directional health score based on critical risk load, pending approval pressure, and SLA compliance signals.",
            "governance",
        ),
        (
            "What is an Active Risk?",
            "A current anomaly, exposure, or governance issue that may need review, mitigation, or monitoring.",
            "risk",
        ),
        (
            "What is a Critical Risk?",
            "An active risk classified as critical, high, anomaly, or spike based on the available risk status field.",
            "risk",
        ),
        (
            "What is Optimization Exposure?",
            "A cost or service area where governance review may unlock efficiency, waste reduction, or control improvement.",
            "ai",
        ),
        (
            "What is Potential Savings?",
            "The estimated savings attached to recommendations currently visible to the governance process.",
            "cost",
        ),
    ]
    definition_cols = st.columns(2)
    for index, (title, description, icon) in enumerate(definition_rows):
        with definition_cols[index % 2]:
            render_insight_card(
                title=title,
                description=description,
                icon=icon,
                status="info",
            )

    with st.expander("Detailed Evidence / Drilldown"):
        left, right = st.columns(2)

        with left:
            render_section(
                "Top Active Risks",
                "Highest-priority active risks currently visible to governance.",
                divider=False,
            )
            if not anomaly_df.empty:
                data_table(anomaly_df.head(10))
            else:
                render_risk_card(
                    title="No Active Risks",
                    value="Clear",
                    description="No active risks found.",
                    status="healthy",
                )

        with right:
            render_section(
                "Pending Governance Approvals",
                "Approval requests waiting for governance decisioning.",
                divider=False,
            )
            pending_df = pd.DataFrame(pending_approvals)
            if not pending_df.empty:
                visible_columns = [
                    column for column in [
                        "id",
                        "request_type",
                        "title",
                        "status",
                        "priority",
                        "created_at",
                    ]
                    if column in pending_df.columns
                ]
                st.dataframe(
                    pending_df[visible_columns],
                    use_container_width=True,
                    hide_index=True,
                )
            else:
                render_approval_card(
                    title="No Pending Governance Approvals",
                    value="Clear",
                    description="No pending governance approvals.",
                    status="healthy",
                )

        render_section(
            "Recommendations Requiring Governance Attention",
            "Recommendations that may require governance review or action.",
            divider=True,
        )

        if not recommendation_df.empty:
            visible_columns = [
                column for column in [
                    "service",
                    "description",
                    "estimated_savings",
                    "status",
                    "type",
                    "message",
                    "created_at",
                ]
                if column in recommendation_df.columns
            ]

            if visible_columns:
                st.dataframe(
                    recommendation_df[visible_columns].head(10),
                    use_container_width=True,
                    hide_index=True,
                )
            else:
                data_table(recommendation_df.head(10))
        else:
            render_insight_card(
                title="No Governance Recommendations",
                description="No governance recommendations available.",
                status="healthy",
            )


render_page(
    title="Risk & Governance",
    description="Governance exposure, risks, approvals, anomalies, and optimization control.",
    breadcrumbs=["Home", "Governance", "Risk & Governance"],
    content=render_governance_content,
)
