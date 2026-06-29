from __future__ import annotations

from typing import Any

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
from components.sidebar_navigation import PAGE_PATHS, ROLE_PAGES
from services.saas_intelligence_service import SaaSIntelligenceService
from shared.auth import require_role
from shared.session import init_session
from shared.styles import configure_page


def _money(value: Any) -> str:
    try:
        amount = float(value or 0)
    except (TypeError, ValueError):
        amount = 0.0

    if amount >= 1_000_000:
        return f"${amount / 1_000_000:.1f}M"
    if amount >= 1_000:
        value = amount / 1_000
        return f"${value:,.0f}K" if value.is_integer() else f"${value:,.1f}K"
    return f"${amount:,.0f}"


def _show_dataframe(df: pd.DataFrame, empty_message: str) -> None:
    if df.empty:
        st.info(empty_message)
        return
    st.dataframe(df, use_container_width=True, hide_index=True)


def _format_money_columns(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    formatted = df.copy()
    for column in columns:
        if column in formatted.columns:
            formatted[column] = formatted[column].apply(_money)
    return formatted


def _format_percent_columns(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    formatted = df.copy()
    for column in columns:
        if column in formatted.columns:
            formatted[column] = formatted[column].apply(lambda value: f"{float(value or 0):.1f}%")
    return formatted


def _status_for_count(value: int) -> str:
    return "critical" if value else "healthy"


def _status_for_value(value: float) -> str:
    return "warning" if value else "healthy"


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

kpis = SaaSIntelligenceService.get_kpis()
vendor_spend_df = SaaSIntelligenceService.vendor_spend_dataframe()
renewal_heatmap_df = SaaSIntelligenceService.renewal_heatmap_dataframe()
renewal_risks_df = SaaSIntelligenceService.renewal_risks_dataframe()
license_waste_df = SaaSIntelligenceService.license_waste_dataframe()
ai_governance_df = SaaSIntelligenceService.ai_license_governance_dataframe()
ai_risk_df = SaaSIntelligenceService.ai_risk_summary_dataframe()
ai_recommendations_df = SaaSIntelligenceService.ai_optimization_recommendations_dataframe()
inactive_users_df = SaaSIntelligenceService.inactive_users_dataframe()

total_saas_spend = kpis["total_saas_spend"]
total_subscription_spend = kpis["total_saas_spend"] + kpis["ai_spend"]
vendor_count = kpis["vendor_count"]
ai_vendors = kpis.get("ai_vendors", [])
ai_vendor_count = len(ai_vendors) if isinstance(ai_vendors, list) else int(ai_vendors or 0)
license_count = int(license_waste_df["Purchased"].sum()) if not license_waste_df.empty and "Purchased" in license_waste_df.columns else kpis["saas_platforms"]
inactive_users = kpis["inactive_users"]
license_waste = int(license_waste_df["Unused"].sum()) if not license_waste_df.empty and "Unused" in license_waste_df.columns else inactive_users
renewals_due = kpis["renewal_risks"]
duplicate_tools = len(ai_recommendations_df)
potential_savings = kpis["optimization_potential"]


def render_saas_content() -> None:
    render_section(
        "SaaS Portfolio Summary",
        "CIO view of SaaS spend, vendors, licenses, renewals, waste, and optimization opportunity.",
        divider=False,
    )
    summary_cols = st.columns(4)
    with summary_cols[0]:
        render_kpi_card(
            "Total SaaS Spend",
            _money(total_saas_spend),
            f"{_money(kpis['ai_spend'])} AI spend tracked separately",
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
            status=_status_for_count(inactive_users),
        )

    optimization_cols = st.columns(4)
    with optimization_cols[0]:
        render_risk_card(
            "License Waste",
            f"{license_waste:,}",
            "Unused licenses and inactive seats",
            icon="risk",
            status=_status_for_count(license_waste),
        )
    with optimization_cols[1]:
        render_risk_card(
            "Renewals Due",
            f"{renewals_due:,}",
            "Renewal events requiring near-term review",
            icon="calendar",
            status=_status_for_count(renewals_due),
        )
    with optimization_cols[2]:
        render_risk_card(
            "Duplicate Tools",
            f"{duplicate_tools:,}",
            "AI/SaaS consolidation recommendations",
            icon="governance",
            status=_status_for_count(duplicate_tools),
        )
    with optimization_cols[3]:
        render_health_card(
            "Potential Savings",
            _money(potential_savings),
            "Optimization potential from consolidation and license cleanup",
            icon="savings",
            status=_status_for_value(potential_savings),
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
            status=_status_for_count(inactive_users),
        )
    with waste_cols[1]:
        render_risk_card(
            "Unused Licenses",
            f"{license_waste:,}",
            "Purchased licenses not actively used",
            status=_status_for_count(license_waste),
        )
    with waste_cols[2]:
        render_metric_card(
            "Optimization Potential",
            _money(potential_savings),
            "Savings opportunity across SaaS and AI tools",
            icon="savings",
            status=_status_for_value(potential_savings),
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
        st.plotly_chart(fig, use_container_width=True)
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
        st.plotly_chart(fig, use_container_width=True)
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
            status=_status_for_count(duplicate_tools),
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

    render_section(
        "Executive SaaS Insight",
        "CIO narrative from SaaS spend, renewal, inactive license, and consolidation signals.",
    )
    render_insight_card(
        "SaaS Optimization Narrative",
        description=SaaSIntelligenceService.get_executive_narrative(),
        status="warning" if renewals_due or inactive_users or duplicate_tools else "healthy",
    )

    render_section(
        "Detailed Evidence / Drilldown",
        "Source tables for SaaS vendors, renewals, license waste, AI governance, risks, and inactive users.",
    )
    with st.expander("Detailed Evidence / Drilldown"):
        st.subheader("Vendor Spend")
        _show_dataframe(
            _format_money_columns(vendor_spend_df, ["Annual Spend"]),
            "No vendor spend data is available.",
        )

        st.subheader("Renewal Risks")
        _show_dataframe(
            _format_money_columns(renewal_risks_df, ["Annual Cost"]),
            "No SaaS renewals require immediate attention.",
        )

        st.subheader("License Waste")
        _show_dataframe(
            _format_percent_columns(license_waste_df, ["Waste %"]),
            "No license waste data is available.",
        )

        st.subheader("AI Governance Overview")
        _show_dataframe(
            _format_money_columns(ai_governance_df, ["Cost"]),
            "No AI license governance data is available.",
        )

        st.subheader("AI Risk Summary")
        _show_dataframe(
            ai_risk_df,
            "No AI risk data is available.",
        )

        st.subheader("AI Optimization Recommendations")
        _show_dataframe(
            _format_money_columns(
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


render_page(
    title="SaaS Intelligence",
    description="CIO view of SaaS spend, license waste, renewal risk, vendor concentration, and duplicate tools.",
    breadcrumbs=["Home", "CIO", "SaaS Intelligence"],
    content=render_saas_content,
    status="warning" if renewals_due or inactive_users or duplicate_tools else "healthy",
)
