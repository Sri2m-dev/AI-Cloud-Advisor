from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from components.cards import (
    render_health_card,
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
from services.saas_intelligence_certification_service import SaaSIntelligenceCertificationService
from services.saas_intelligence_service import SaaSIntelligenceService
from shared.auth import require_role
from shared.session import init_session
from shared.streamlit_compat import dataframe, plotly_chart
from shared.styles import configure_page


def _show_dataframe(df: pd.DataFrame, empty_message: str) -> None:
    if df.empty:
        st.info(empty_message)
        return
    dataframe(df, hide_index=True)


configure_page(
    page_title="SaaS + AI Intelligence",
    page_icon="S",
)
init_session()
require_role([
    "executive",
    "cio",
    "super_admin",
])

role = st.session_state.get("role", "cio")
render_enterprise_sidebar(
    role,
    page_paths=PAGE_PATHS,
    role_pages=ROLE_PAGES,
    active_page=PAGE_PATHS["SaaS + AI Intelligence"],
)

dashboard = SaaSIntelligenceCertificationService.get_dashboard()
kpis = dashboard["kpis"]
metrics = dashboard["metrics"]
dataframes = dashboard["dataframes"]
reconciliation_cards = dashboard["reconciliation_cards"]
business_context = dashboard["business_context"]
evidence = dashboard["evidence"]

vendor_spend_df = dataframes["vendor_spend"]
renewal_heatmap_df = dataframes["renewal_heatmap"]
renewal_risks_df = dataframes["renewal_risks"]
license_waste_df = dataframes["license_waste"]
ai_governance_df = dataframes["ai_governance"]
ai_risk_df = dataframes["ai_risk"]
ai_recommendations_df = dataframes["ai_recommendations"]
inactive_users_df = dataframes["inactive_users"]

total_saas_spend = metrics["total_saas_spend"]
vendor_count = metrics["vendor_count"]
ai_vendor_count = metrics["ai_vendor_count"]
license_count = metrics["license_count"]
inactive_users = metrics["inactive_users"]
license_waste = metrics["license_waste"]
renewals_due = metrics["renewals_due"]
duplicate_tools = metrics["duplicate_tools"]
potential_savings = metrics["potential_savings"]


def render_certification_summary() -> None:
    render_executive_summary(
        {
            "title": "Executive Summary",
            "description": "Estate-level SaaS and AI portfolio summary for CIO certification, financial reconciliation, and business architecture context.",
            "narrative": dashboard.get("executive_summary") or "SaaS Intelligence certification summary is unavailable.",
            "metrics": [
                {
                    "label": "Total SaaS Spend",
                    "value": SaaSIntelligenceCertificationService.format_money(total_saas_spend),
                    "description": "Annual SaaS subscription spend",
                    "icon": "cost",
                    "status": "info",
                },
                {
                    "label": "AI Spend",
                    "value": SaaSIntelligenceCertificationService.format_money(metrics.get("ai_spend")),
                    "description": "AI tooling spend tracked separately",
                    "icon": "ai",
                    "status": "info",
                },
                {
                    "label": "License Spend",
                    "value": SaaSIntelligenceCertificationService.format_money(metrics.get("total_license_spend")),
                    "description": "License and subscription spend",
                    "icon": "technology",
                    "status": "info",
                },
                {
                    "label": "Optimization Potential",
                    "value": SaaSIntelligenceCertificationService.format_money(potential_savings),
                    "description": "Savings opportunity from cleanup and consolidation",
                    "icon": "savings",
                    "status": SaaSIntelligenceCertificationService.status_for_value(potential_savings),
                },
                {
                    "label": "Renewal Risks",
                    "value": f"{renewals_due:,}",
                    "description": "Renewal events requiring review",
                    "icon": "calendar",
                    "status": SaaSIntelligenceCertificationService.status_for_count(renewals_due),
                },
                {
                    "label": "Inactive Users",
                    "value": f"{inactive_users:,}",
                    "description": "Users eligible for license review",
                    "icon": "warning",
                    "status": SaaSIntelligenceCertificationService.status_for_count(inactive_users),
                },
                {
                    "label": "Vendor Portfolio Health",
                    "value": f"{metrics.get('vendor_portfolio_health', 0):.1f}%",
                    "description": "Vendor concentration and cleanup posture",
                    "icon": "health",
                    "status": "warning" if metrics.get("vendor_portfolio_health", 0) < 90 else "healthy",
                },
                {
                    "label": "AI Governance Summary",
                    "value": f"{metrics.get('ai_tools', 0):,} tools / {ai_vendor_count:,} vendors",
                    "description": "AI governance footprint",
                    "icon": "governance",
                    "status": "info",
                },
            ],
        }
    )
    render_reconciliation_panel(reconciliation_cards)
    render_business_context({**business_context, "technologies": business_context.get("saas_ai_platforms", 0)})


def render_certification_evidence() -> None:
    render_evidence_panel(evidence)


def render_saas_content() -> None:
    render_certification_summary()

    render_section(
        "SaaS Portfolio Summary",
        "CIO view of SaaS spend, vendors, licenses, renewals, waste, and optimization opportunity.",
        divider=False,
    )
    summary_cols = st.columns(4)
    with summary_cols[0]:
        render_kpi_card(
            "Total SaaS Spend",
            SaaSIntelligenceCertificationService.format_money(total_saas_spend),
            f"{SaaSIntelligenceCertificationService.format_money(kpis['ai_spend'])} AI spend tracked separately",
            icon="cost",
            status="info",
        )
    with summary_cols[1]:
        render_metric_card(
            "Vendors",
            f"{vendor_count:,}",
            f"Largest vendor: {kpis['largest_vendor']}",
            icon="enterprise",
            status="info",
        )
    with summary_cols[2]:
        render_metric_card(
            "Licenses",
            f"{license_count:,}",
            "Purchased SaaS/license seats in scope",
            icon="technology",
            status="info",
        )
    with summary_cols[3]:
        render_risk_card(
            "Inactive Users",
            f"{inactive_users:,}",
            "Users eligible for license review",
            icon="warning",
            status=SaaSIntelligenceCertificationService.status_for_count(inactive_users),
        )

    optimization_cols = st.columns(4)
    with optimization_cols[0]:
        render_risk_card(
            "License Waste",
            f"{license_waste:,}",
            "Unused licenses and inactive seats",
            icon="risk",
            status=SaaSIntelligenceCertificationService.status_for_count(license_waste),
        )
    with optimization_cols[1]:
        render_risk_card(
            "Renewals Due",
            f"{renewals_due:,}",
            "Renewal events requiring near-term review",
            icon="calendar",
            status=SaaSIntelligenceCertificationService.status_for_count(renewals_due),
        )
    with optimization_cols[2]:
        render_risk_card(
            "Duplicate Tools",
            f"{duplicate_tools:,}",
            "AI/SaaS consolidation recommendations",
            icon="governance",
            status=SaaSIntelligenceCertificationService.status_for_count(duplicate_tools),
        )
    with optimization_cols[3]:
        render_health_card(
            "Potential Savings",
            SaaSIntelligenceCertificationService.format_money(potential_savings),
            "Optimization potential from consolidation and license cleanup",
            icon="savings",
            status=SaaSIntelligenceCertificationService.status_for_value(potential_savings),
        )

    render_section(
        "License Waste Center",
        "Inactive users and unused licenses that can reduce subscription run-rate.",
    )
    waste_cols = st.columns(3)
    with waste_cols[0]:
        render_risk_card(
            "Inactive Users",
            f"{inactive_users:,}",
            "Users with inactive SaaS usage signals",
            status=SaaSIntelligenceCertificationService.status_for_count(inactive_users),
        )
    with waste_cols[1]:
        render_risk_card(
            "Unused Licenses",
            f"{license_waste:,}",
            "Purchased licenses not actively used",
            status=SaaSIntelligenceCertificationService.status_for_count(license_waste),
        )
    with waste_cols[2]:
        render_metric_card(
            "Optimization Potential",
            SaaSIntelligenceCertificationService.format_money(potential_savings),
            "Savings opportunity across SaaS and AI tools",
            icon="savings",
            status=SaaSIntelligenceCertificationService.status_for_value(potential_savings),
        )

    render_section(
        "Renewal Risk Center",
        "Upcoming renewals that need owner validation, usage review, and negotiation attention.",
    )
    if not renewal_heatmap_df.empty:
        fig = px.imshow(
            [renewal_heatmap_df["Renewals"].tolist()],
            x=renewal_heatmap_df["Window"].tolist(),
            y=["Renewals"],
            color_continuous_scale="Reds",
            text_auto=True,
            aspect="auto",
        )
        fig.update_layout(
            margin={"l": 10, "r": 10, "t": 10, "b": 10},
            height=210,
            coloraxis_showscale=False,
        )
        plotly_chart(fig)
    else:
        st.info("No SaaS renewal heatmap data is available.")

    render_section(
        "Vendor Spend Analysis",
        "Vendor concentration and annual SaaS spend distribution.",
    )
    if not vendor_spend_df.empty and {"Vendor", "Annual Spend"}.issubset(vendor_spend_df.columns):
        fig = px.bar(
            vendor_spend_df,
            x="Vendor",
            y="Annual Spend",
            color="Vendor",
            title=None,
        )
        fig.update_layout(
            showlegend=False,
            margin={"l": 10, "r": 10, "t": 10, "b": 10},
            height=320,
        )
        plotly_chart(fig)
    else:
        st.info("No vendor spend data is available.")

    render_section(
        "Duplicate Tool Review",
        "Consolidation opportunities where overlapping SaaS or AI capabilities may create avoidable cost.",
    )
    duplicate_cols = st.columns(3)
    with duplicate_cols[0]:
        render_risk_card(
            "Duplicate Tool Signals",
            f"{duplicate_tools:,}",
            "Recommendations indicating overlap or consolidation potential",
            status=SaaSIntelligenceCertificationService.status_for_count(duplicate_tools),
        )
    with duplicate_cols[1]:
        render_metric_card(
            "AI Tools",
            f"{kpis['ai_tools']:,}",
            "AI platforms in governance scope",
            icon="ai",
            status="info",
        )
    with duplicate_cols[2]:
        render_metric_card(
            "AI Vendors",
            f"{ai_vendor_count:,}",
            "AI vendor footprint",
            icon="enterprise",
            status="info",
        )

    render_ai_narrative(
        "Executive SaaS Insight",
        SaaSIntelligenceCertificationService.escape_markdown_currency(
            SaaSIntelligenceCertificationService.executive_narrative(metrics)
        ),
        description="CIO narrative from SaaS spend, renewal, inactive license, and consolidation signals.",
    )

    render_section(
        "Detailed Evidence / Drilldown",
        "Source tables for SaaS vendors, renewals, license waste, AI governance, risks, and inactive users.",
    )
    with st.expander("Detailed Evidence / Drilldown"):
        st.subheader("Vendor Spend")
        _show_dataframe(
            SaaSIntelligenceCertificationService.format_money_columns(vendor_spend_df, ["Annual Spend"]),
            "No vendor spend data is available.",
        )

        st.subheader("Renewal Risks")
        _show_dataframe(
            SaaSIntelligenceCertificationService.format_money_columns(renewal_risks_df, ["Annual Cost"]),
            "No SaaS renewals require immediate attention.",
        )

        st.subheader("License Waste")
        _show_dataframe(
            SaaSIntelligenceCertificationService.format_percent_columns(license_waste_df, ["Waste %"]),
            "No license waste data is available.",
        )

        st.subheader("AI Governance Overview")
        _show_dataframe(
            SaaSIntelligenceCertificationService.format_money_columns(ai_governance_df, ["Cost"]),
            "No AI license governance data is available.",
        )

        st.subheader("AI Risk Summary")
        _show_dataframe(
            ai_risk_df,
            "No AI risk data is available.",
        )

        st.subheader("AI Optimization Recommendations")
        _show_dataframe(
            SaaSIntelligenceCertificationService.format_money_columns(
                ai_recommendations_df.rename(
                    columns={
                        "title": "Recommendation",
                        "estimated_savings": "Potential Savings",
                        "priority": "Priority",
                    }
                )[["Recommendation", "Potential Savings", "Priority"]],
                ["Potential Savings"],
            )
            if not ai_recommendations_df.empty
            else ai_recommendations_df,
            "No AI optimization recommendations are available.",
        )

        st.subheader("Inactive Users")
        _show_dataframe(
            inactive_users_df,
            "No inactive SaaS users are currently available.",
        )

    render_certification_evidence()


render_page(
    title="SaaS Intelligence",
    description="CIO view of SaaS spend, license waste, renewal risk, vendor concentration, and duplicate tools.",
    breadcrumbs=["Home", "CIO", "SaaS Intelligence"],
    content=render_saas_content,
    status="warning" if renewals_due or inactive_users or duplicate_tools else "healthy",
)
