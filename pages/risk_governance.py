from __future__ import annotations

import os
import sys

import pandas as pd
import plotly.express as px
import streamlit as st

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from components.cards import (
    render_approval_card,
    render_insight_card,
    render_kpi_card,
    render_metric_card,
    render_risk_card,
)
from components.layout import render_page, render_section
from components.navigation import render_enterprise_sidebar
from components.shared import (
    render_ai_narrative,
    render_business_context,
    render_evidence_panel,
    render_executive_summary,
    render_reconciliation_panel,
)
from components.sidebar_navigation import PAGE_PATHS, ROLE_PAGES
from components.tables import data_table
from services.demo_tenant_service import demo_mode_enabled, is_demo_tenant, load_demo_tenant
from services.risk_governance_certification_service import RiskGovernanceCertificationService
from shared.auth import require_role
from shared.evidence_context import resolve_active_evidence_context
from shared.session import init_session
from shared.streamlit_compat import dataframe, plotly_chart
from shared.styles import configure_page

configure_page(
    page_title="Risk & Governance | Nexora",
    page_icon="âš ï¸",
)

init_session()

require_role(
    [
        "executive",
        "cio",
        "technical",
        "finance",
        "super_admin",
    ]
)

role = st.session_state.get("role", "Unknown")
render_enterprise_sidebar(
    role,
    page_paths=PAGE_PATHS,
    role_pages=ROLE_PAGES,
    active_page=PAGE_PATHS["Risk & Governance"],
)

evidence_context = resolve_active_evidence_context(st.session_state)
if evidence_context.is_prospect:
    st.title("Risk & Governance")
    st.caption("TEMPORARY PROSPECT ANALYSIS · PROSPECT EVIDENCE ONLY")
    st.info("Risk is not assessed from current uploaded evidence.")
    st.write(
        "No governed risk, control, concentration, service-health, or financial-impact "
        "conclusion is supported by this prospect analysis."
    )
    st.stop()


def render_demo_risk_governance(payload: dict) -> None:
    """Render the isolated demo posture from the same decisions used by the CEO view."""
    metrics = payload["metrics"]
    decisions = payload["decisions"]
    journeys = {item["decision_id"]: item for item in payload["journeys"]}
    risk_decisions = [item for item in decisions if item["type"] == "executive_technology_risk"]
    known_impact = sum(item.get("financial_impact") or 0 for item in decisions)

    st.title("Risk & Governance")
    st.caption("Executive risk, decision accountability, and evidence posture.")
    st.warning(
        "SYNTHETIC DEMONSTRATION DATA — isolated from customer and production records."
    )
    st.subheader("Leadership risk posture")
    cols = st.columns(4)
    cols[0].metric("Material technology risks", len(risk_decisions))
    cols[1].metric("Decisions requiring action", len(decisions))
    cols[2].metric("Known decision impact", f"${known_impact / 1_000_000:.1f}M")
    cols[3].metric("Technology health", f"{metrics['technology_health']}%")

    st.subheader("Decision requiring mitigation")
    for decision in risk_decisions:
        journey = journeys[decision["id"]]
        with st.container(border=True):
            st.caption(f"{decision['id']} · {decision['status'].replace('_', ' ').title()}")
            st.markdown(f"### {decision['title']}")
            st.write(f"**Business service:** {decision['business_service']}")
            st.write(f"**Why it matters:** {journey['impact']}")
            st.write("**Financial impact:** UNKNOWN — not yet certified")
            st.write(f"**Recommended decision:** {journey['recommendation']}")
            st.info(f"Accountable next step — {journey['next_step']}")
            confidence, evidence = st.columns(2)
            confidence.metric("Confidence", f"{decision['confidence']}%")
            evidence.metric("Evidence coverage", f"{decision['evidence_coverage']}%")
            with st.expander("Show evidence and dependency context"):
                st.write(journey["evidence"])
                st.write(" → ".join(item["entity"] for item in journey["twin_path"]))

    st.subheader("Financial reconciliation")
    st.info(
        "Allocation and unallocated spend are NOT ASSESSED for this risk decision. "
        "No zero-value or healthy financial conclusion is asserted without certified evidence."
    )
    st.caption(f"Source: {payload['source']} · As of {payload['as_of']}")


organization_id = str(
    st.session_state.get("organization_id") or st.session_state.get("org_id") or ""
)
if demo_mode_enabled() and is_demo_tenant(organization_id):
    render_demo_risk_governance(load_demo_tenant(organization_id))
    st.stop()

dashboard = RiskGovernanceCertificationService.get_dashboard()
metrics = dashboard["metrics"]
dataframes = dashboard["dataframes"]
approval_metrics = dashboard["approval_metrics"]
sla_metrics = dashboard["sla_metrics"]
pending_approvals = RiskGovernanceCertificationService.get_live_approval_queue()
reconciliation_cards = dashboard["reconciliation_cards"]
business_context = dashboard["business_context"]
evidence = dashboard["evidence"]

anomaly_df = dataframes["anomaly"]
optimization_df = dataframes["optimization"]
recommendation_df = dataframes["recommendation"]

active_risks = metrics["active_risks"]
critical_risks = metrics["critical_risks"]
risk_status_column = metrics["risk_status_column"]
optimization_items = metrics["optimization_items"]
potential_savings = metrics["potential_savings"]
pending_count = metrics["pending_count"]
sla_compliance = metrics["sla_compliance"]
governance_score = metrics["governance_score"]


def render_certification_summary() -> None:
    render_executive_summary(
        {
            "title": "Executive Summary",
            "description": "Estate-level risk and governance summary for CIO certification, financial reconciliation, and business architecture context.",
            "narrative": dashboard.get("executive_summary")
            or "Risk & Governance certification summary is unavailable.",
            "metrics": [
                {
                    "label": "Governance Confidence",
                    "value": f"{governance_score:.0f}%",
                    "description": "Directional governance posture",
                    "icon": "governance",
                    "status": "healthy" if governance_score >= 75 else "warning",
                },
                {
                    "label": "Active Risk Signals",
                    "value": f"{active_risks:,}",
                    "description": "Current risk signals visible to governance",
                    "icon": "risk",
                    "status": "warning" if active_risks else "healthy",
                },
                {
                    "label": "Critical Risks",
                    "value": f"{int(critical_risks):,}",
                    "description": "High-priority risks requiring attention",
                    "icon": "alert",
                    "status": "critical" if critical_risks else "healthy",
                },
                {
                    "label": "Executive Action Required",
                    "value": f"{int(metrics.get('executive_action_required') or 0):,}",
                    "description": "Combined approval and risk action load",
                    "icon": "approval",
                    "status": "warning" if metrics.get("executive_action_required") else "healthy",
                },
                {
                    "label": "Optimization Opportunities",
                    "value": f"{optimization_items:,}",
                    "description": "Governance-linked optimization signals",
                    "icon": "ai",
                    "status": "info",
                },
                {
                    "label": "Savings Exposure",
                    "value": RiskGovernanceCertificationService.format_money(potential_savings),
                    "description": "Potential financial exposure under governance review",
                    "icon": "cost",
                    "status": "warning" if potential_savings else "healthy",
                },
                {
                    "label": "Approval Queue",
                    "value": f"{pending_count:,}",
                    "description": "Pending governance decisions",
                    "icon": "approval",
                    "status": "warning" if pending_count else "healthy",
                },
                {
                    "label": "SLA Compliance",
                    "value": f"{sla_compliance:.0f}%",
                    "description": "Approval service-level compliance",
                    "icon": "health",
                    "status": "healthy" if sla_compliance >= 90 else "warning",
                },
            ],
        }
    )
    render_reconciliation_panel(reconciliation_cards)
    render_business_context(business_context)


def render_certification_evidence() -> None:
    render_evidence_panel(evidence)


def _show_dataframe(df: pd.DataFrame, empty_message: str) -> None:
    if df.empty:
        st.info(empty_message)
        return
    dataframe(df, hide_index=True)


def render_governance_content():
    if not dashboard["data_available"]:
        st.warning("Risk data source has not been configured for this tenant.")
        render_insight_card(
            "Risk Intelligence",
            "Unavailable",
            description=(
                "Risk posture cannot currently be assessed. Configure a certified "
                "governance data source before using this page for decisions."
            ),
            icon="governance",
            status="warning",
        )
        return
    render_certification_summary()

    # --------------------------------------------------
    # EXECUTIVE SUMMARY
    # --------------------------------------------------

    render_section(
        "Executive Governance Summary",
        "Board-level view of governance confidence, active risk exposure, approval pressure, and financial opportunity.",
        divider=False,
    )

    k1, k2, k3, k4, k5, k6 = st.columns(6)

    with k1:
        render_kpi_card(
            "Governance Confidence",
            f"{governance_score:.0f}%",
            icon="governance",
            status="healthy" if governance_score >= 75 else "warning",
        )
    with k2:
        render_metric_card(
            "Active Risk Signals",
            active_risks,
            icon="risk",
            status="warning" if active_risks else "healthy",
        )
    with k3:
        render_risk_card(
            "High-Priority Risks",
            int(critical_risks),
            status="critical" if critical_risks else "healthy",
        )
    with k4:
        render_approval_card(
            "Decision Queue", pending_count, status="watch" if pending_count else "healthy"
        )
    with k5:
        render_metric_card("Optimization Signals", optimization_items, icon="ai", status="info")
    with k6:
        render_kpi_card(
            "Savings Exposure",
            RiskGovernanceCertificationService.format_money(potential_savings),
            icon="cost",
            status="warning" if potential_savings else "healthy",
        )

    render_ai_narrative(
        "Executive Governance Summary",
        (
            f"Governance confidence is currently {governance_score:.0f}%, based on high-priority risk load, "
            f"approval queue pressure, and SLA compliance signals. "
            f"There are {active_risks} active risk signals, including {int(critical_risks)} high-priority items. "
            f"The decision queue has {pending_count} pending approval items, and {optimization_items} optimization "
            f"signals indicate potential financial exposure of {RiskGovernanceCertificationService.format_money(potential_savings)}."
        ),
        description="AI-assisted interpretation of governance confidence, risk exposure, approval pressure, and savings exposure.",
    )

    # --------------------------------------------------
    # RISK + GOVERNANCE VISUALS
    # --------------------------------------------------

    left, right = st.columns(2)

    with left:
        render_section(
            "Risk Signal Posture",
            "Distribution of active risk signals by status, severity, or risk level.",
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
            risk_summary.columns = ["Risk Signal Status", "Count"]

            fig = px.bar(
                risk_summary,
                x="Risk Signal Status",
                y="Count",
                title="Risk Signal Distribution",
            )

            plotly_chart(fig)
        else:
            render_insight_card(
                title="No Active Risk Signals",
                description="No active risk signal data is currently available for governance review.",
                status="healthy",
            )

    with right:
        render_section(
            "Decision Queue Health",
            "Governance decision status across pending, approved, rejected, and escalated approvals.",
            divider=True,
        )

        approval_summary = RiskGovernanceCertificationService.approval_summary(approval_metrics)

        fig = px.bar(
            approval_summary,
            x="Status",
            y="Count",
            title="Approval Queue Status",
        )

        plotly_chart(fig)

    # --------------------------------------------------
    # OPTIMIZATION EXPOSURE
    # --------------------------------------------------

    render_section(
        "Savings & Optimization Exposure",
        "Top governance-linked optimization signals by service cost and financial exposure.",
        divider=True,
    )

    if not optimization_df.empty and {"service_name", "total_cost"}.issubset(
        optimization_df.columns
    ):
        top_optimization_df = (
            optimization_df.copy()
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

        plotly_chart(fig)
    else:
        render_insight_card(
            title="No Savings Exposure",
            description="No governance-linked savings or optimization exposure data is currently available.",
            status="healthy",
        )

    render_section(
        "Business Impact Areas",
        "How governance, risk, approval, and optimization signals translate into business impact.",
        divider=True,
    )

    impact_cols = st.columns(5)
    with impact_cols[0]:
        render_risk_card(
            "Financial Exposure",
            RiskGovernanceCertificationService.format_money(potential_savings),
            description="Optimization and spend exposure that may affect budget outcomes or savings commitments.",
            status="warning" if potential_savings else "healthy",
        )
    with impact_cols[1]:
        render_risk_card(
            "Operational Continuity",
            active_risks,
            description="Active risk signals that may affect service continuity or delivery reliability.",
            status="warning" if active_risks else "healthy",
        )
    with impact_cols[2]:
        render_metric_card(
            "Compliance Readiness",
            f"{governance_score:.0f}%",
            description="Governance confidence as a directional compliance readiness signal.",
            icon="governance",
            status="healthy" if governance_score >= 75 else "warning",
        )
    with impact_cols[3]:
        render_approval_card(
            "Executive Decision Load",
            pending_count,
            description="Pending approvals requiring executive or governance action.",
            status="watch" if pending_count else "healthy",
        )
    with impact_cols[4]:
        render_insight_card(
            "Optimization Opportunity",
            optimization_items,
            description="Optimization signals requiring business prioritization or ownership.",
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
            "What does Governance Confidence mean?",
            "A directional governance confidence score based on high-priority risk load, pending approval pressure, and SLA compliance signals.",
            "governance",
        ),
        (
            "What is an Active Risk Signal?",
            "A current anomaly, exposure, or governance issue that may need review, mitigation, or monitoring.",
            "risk",
        ),
        (
            "What is a High-Priority Risk?",
            "An active risk signal classified as critical, high, anomaly, or spike based on the available risk status field.",
            "risk",
        ),
        (
            "What is Optimization Exposure?",
            "A cost or service area where governance review may unlock efficiency, waste reduction, or control improvement.",
            "ai",
        ),
        (
            "What is Savings Exposure?",
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
                "Top Active Risk Signals",
                "Highest-priority active risk signals currently visible to governance.",
                divider=False,
            )
            if not anomaly_df.empty:
                data_table(anomaly_df.head(10))
            else:
                render_risk_card(
                    title="No Active Risk Signals",
                    value="Clear",
                    description="No active governance risk signals found.",
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
                    column
                    for column in [
                        "id",
                        "request_type",
                        "title",
                        "status",
                        "priority",
                        "created_at",
                    ]
                    if column in pending_df.columns
                ]
                dataframe(pending_df[visible_columns], hide_index=True)
            else:
                render_approval_card(
                    title="No Pending Governance Approvals",
                    value="Clear",
                    description="No pending governance approvals are waiting for decision.",
                    status="healthy",
                )

        render_section(
            "Recommendations Requiring Governance Attention",
            "Recommendations that may require governance review or action.",
            divider=True,
        )

        if not recommendation_df.empty:
            visible_columns = [
                column
                for column in [
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
                dataframe(recommendation_df[visible_columns].head(10), hide_index=True)
            else:
                data_table(recommendation_df.head(10))
        else:
            render_insight_card(
                title="No Governance Recommendations",
                description="No governance recommendations are currently available.",
                status="healthy",
            )

    render_certification_evidence()


render_page(
    title="Risk & Governance",
    description="Executive view of governance confidence, risk signals, approval pressure, business impact, and optimization exposure.",
    breadcrumbs=["Home", "Governance", "Risk & Governance"],
    content=render_governance_content,
)
