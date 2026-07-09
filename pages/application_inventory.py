from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
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
from services.application_inventory_certification_service import ApplicationInventoryCertificationService
from services.application_portfolio_service import ApplicationPortfolioService
from shared.auth import require_role
from shared.session import init_session
from shared.streamlit_compat import dataframe, plotly_chart
from shared.styles import configure_page


def _show_dataframe(df: pd.DataFrame, empty_message: str) -> None:
    if df.empty:
        st.info(empty_message)
        return
    dataframe(df, hide_index=True)


def _dependency_graph(edges: pd.DataFrame) -> go.Figure | None:
    if edges.empty:
        return None

    graph_df = edges.copy()
    labels = pd.unique(graph_df[["Source", "Target"]].values.ravel("K")).tolist()
    label_index = {label: index for index, label in enumerate(labels)}
    palette = ["#1f2937", "#2563eb", "#16a34a", "#7c3aed", "#0f766e", "#b45309"]

    figure = go.Figure(
        data=[
            go.Sankey(
                arrangement="snap",
                node={
                    "label": labels,
                    "pad": 18,
                    "thickness": 18,
                    "color": [palette[index % len(palette)] for index in range(len(labels))],
                },
                link={
                    "source": graph_df["Source"].map(label_index).tolist(),
                    "target": graph_df["Target"].map(label_index).tolist(),
                    "value": [1] * len(graph_df),
                    "color": ["rgba(37, 99, 235, 0.22)"] * len(graph_df),
                },
            )
        ]
    )
    figure.update_layout(
        margin={"l": 10, "r": 10, "t": 10, "b": 10},
        height=330,
        font={"size": 12},
    )
    return figure


configure_page(page_title="Application Portfolio", page_icon="A")
init_session()
require_role(["executive", "cio", "super_admin"])

role = st.session_state.get("role", "cio")
render_enterprise_sidebar(
    role,
    page_paths=PAGE_PATHS,
    role_pages=ROLE_PAGES,
    active_page=PAGE_PATHS["Application Portfolio"],
)

dashboard = ApplicationInventoryCertificationService.get_dashboard()
summary = dashboard["summary"]
metrics = dashboard["metrics"]
dataframes = dashboard["dataframes"]
reconciliation_cards = dashboard["reconciliation_cards"]
business_context = dashboard["business_context"]
evidence = dashboard["evidence"]

portfolio_df = dataframes["portfolio"]
cost_df = dataframes["cost"]
dependency_df = dataframes["dependency"]
dependency_summary_df = dataframes["dependency_summary"]
unallocated_df = dataframes["unallocated"]
risk_df = dataframes["risk"]
application_map_df = dataframes["application_map"]
cost_ownership_df = dataframes["cost_ownership"]

total_applications = metrics["total_applications"]
business_critical_apps = metrics["business_critical_apps"]
application_spend = metrics["application_spend"]
unmapped_spend = metrics["unmapped_spend"]
mapped_applications = metrics["mapped_applications"]
unmapped_applications = metrics["unmapped_applications"]
owner_gaps = metrics["owner_gaps"]
high_risk_applications = metrics["high_risk_applications"]
average_health_score = metrics["average_health_score"]
allocation_coverage = metrics["allocation_coverage"]


def render_certification_summary() -> None:
    render_executive_summary(
        {
            "title": "Executive Summary",
            "description": "Estate-level application portfolio summary for CIO certification, financial reconciliation, and business architecture context.",
            "narrative": dashboard.get("executive_summary") or "Application Inventory certification summary is unavailable.",
            "metrics": [
                {
                    "label": "Applications",
                    "value": f"{total_applications:,}",
                    "description": "Active registered applications",
                    "icon": "technology",
                    "status": "info",
                },
                {
                    "label": "Critical Applications",
                    "value": f"{business_critical_apps:,}",
                    "description": "Business-critical portfolio scope",
                    "icon": "risk",
                    "status": "critical" if business_critical_apps else "healthy",
                },
                {
                    "label": "Portfolio Health",
                    "value": f"{average_health_score}%",
                    "description": "Composite mapping, ownership, and risk score",
                    "icon": "health",
                    "status": ApplicationInventoryCertificationService.health_status(average_health_score),
                },
                {
                    "label": "Technology Dependencies",
                    "value": f"{summary['technology_dependencies']:,.0f}",
                    "description": "Technology relationships supporting applications",
                    "icon": "graph",
                    "status": "info" if summary["technology_dependencies"] else "warning",
                },
                {
                    "label": "Allocated Spend",
                    "value": ApplicationInventoryCertificationService.format_money(application_spend),
                    "description": "Spend mapped to registered applications",
                    "icon": "cost",
                    "status": "info",
                },
                {
                    "label": "Unmapped Spend",
                    "value": ApplicationInventoryCertificationService.format_money(unmapped_spend),
                    "description": "Technology spend awaiting application mapping",
                    "icon": "warning",
                    "status": "critical" if unmapped_spend else "healthy",
                },
                {
                    "label": "Risk Signals",
                    "value": f"{high_risk_applications:,}",
                    "description": "Application portfolio risks identified",
                    "icon": "risk",
                    "status": "critical" if high_risk_applications else "healthy",
                },
                {
                    "label": "Owner Gaps",
                    "value": f"{owner_gaps:,}",
                    "description": "Applications needing business ownership",
                    "icon": "governance",
                    "status": "critical" if owner_gaps else "healthy",
                },
            ],
        }
    )
    render_reconciliation_panel(
        {
            **reconciliation_cards,
            "variance_status": reconciliation_cards.get("status", "Unknown"),
        }
    )
    render_business_context(business_context)


def render_certification_evidence() -> None:
    render_evidence_panel(evidence)


def render_application_content() -> None:
    render_certification_summary()

    render_section(
        "Application Portfolio Summary",
        "Business view of critical applications, ownership, spend mapping, and operational risk.",
        divider=False,
    )
    summary_cols = st.columns(4)
    with summary_cols[0]:
        render_kpi_card(
            "Total Applications",
            f"{total_applications:,}",
            "Active registered applications",
            icon="technology",
            status="info",
        )
    with summary_cols[1]:
        render_risk_card(
            "Business Critical Apps",
            f"{business_critical_apps:,}",
            "Applications marked critical or high criticality",
            icon="risk",
            status="critical" if business_critical_apps else "info",
        )
    with summary_cols[2]:
        render_health_card(
            "Mapped Applications",
            f"{mapped_applications:,}",
            "Applications with allocated spend",
            icon="success",
            status=ApplicationInventoryCertificationService.health_status(allocation_coverage),
        )
    with summary_cols[3]:
        render_risk_card(
            "Unmapped Applications",
            f"{unmapped_applications:,}",
            "Applications without allocated spend mapping",
            icon="warning",
            status="critical" if unmapped_applications else "healthy",
        )

    spend_cols = st.columns(4)
    with spend_cols[0]:
        render_metric_card(
            "Allocated Application Spend",
            ApplicationInventoryCertificationService.format_money(application_spend),
            f"{allocation_coverage}% allocation coverage",
            icon="cost",
            status=ApplicationInventoryCertificationService.health_status(allocation_coverage),
        )
    with spend_cols[1]:
        render_risk_card(
            "Owner Gaps",
            f"{owner_gaps:,}",
            "Applications needing business owner assignment",
            icon="governance",
            status="critical" if owner_gaps else "healthy",
        )
    with spend_cols[2]:
        render_risk_card(
            "High-Risk Applications",
            f"{high_risk_applications:,}",
            "Application portfolio risks identified",
            icon="risk",
            status="critical" if high_risk_applications else "healthy",
        )
    with spend_cols[3]:
        render_health_card(
            "Average Health Score",
            f"{average_health_score}%",
            "Composite mapping, ownership, and risk score",
            icon="health",
            status=ApplicationInventoryCertificationService.health_status(average_health_score),
        )

    render_section(
        "Business Critical Applications",
        "Which applications carry business criticality and need CIO attention?",
    )
    critical_cols = st.columns(3)
    with critical_cols[0]:
        render_risk_card(
            "Critical Applications",
            f"{business_critical_apps:,}",
            "Critical or high criticality applications",
            status="critical" if business_critical_apps else "info",
        )
    with critical_cols[1]:
        render_metric_card(
            "Technology Dependencies",
            f"{summary['technology_dependencies']:,.0f}",
            "Technology dependencies supporting application delivery",
            icon="graph",
            status="info" if summary["technology_dependencies"] else "warning",
        )
    with critical_cols[2]:
        render_metric_card(
            "Portfolio Risks",
            f"{high_risk_applications:,}",
            "Risk rows generated from criticality, spend gaps, and dependency concentration",
            icon="risk",
            status="critical" if high_risk_applications else "healthy",
        )

    render_section(
        "Application Spend & Ownership",
        "Who owns applications, how much do they cost, and where is spend unmapped?",
    )
    ownership_cols = st.columns(3)
    with ownership_cols[0]:
        render_metric_card(
            "Allocated Application Spend",
            ApplicationInventoryCertificationService.format_money(application_spend),
            "Spend mapped to registered applications",
            icon="cost",
            status="info",
        )
    with ownership_cols[1]:
        render_risk_card(
            "Unmapped Technology Spend",
            ApplicationInventoryCertificationService.format_money(unmapped_spend),
            "Technology spend not mapped to applications",
            icon="warning",
            status="critical" if unmapped_spend else "healthy",
        )
    with ownership_cols[2]:
        render_health_card(
            "Owner Coverage",
            f"{round(((total_applications - owner_gaps) / total_applications) * 100, 1) if total_applications else 0}%",
            "Applications with named ownership",
            icon="governance",
            status="critical" if owner_gaps else "healthy",
        )

    render_insight_card(
        "Application Spend Attribution",
        description=(
            "Only spend with a mapped application relationship is counted as allocated application spend. "
            "Unmapped technology spend remains visible separately so CIOs can see how much cloud, SaaS, MSP, "
            "license, or AI spend still needs application ownership mapping."
        ),
        status="warning" if unmapped_spend else "info",
    )

    render_section(
        "Application Cost & Ownership",
        "Which applications exist, who owns them, how much they cost, and which need CIO attention.",
    )
    ownership_map_cols = st.columns(3)
    with ownership_map_cols[0]:
        render_metric_card(
            "Applications With Owners",
            f"{max(total_applications - owner_gaps, 0):,}",
            "Applications with assigned business ownership",
            icon="technology",
            status="healthy" if not owner_gaps else "warning",
        )
    with ownership_map_cols[1]:
        render_metric_card(
            "Allocated Application Spend",
            ApplicationInventoryCertificationService.format_money(application_spend),
            "Spend mapped to registered applications",
            icon="cost",
            status=ApplicationInventoryCertificationService.health_status(allocation_coverage),
        )
    with ownership_map_cols[2]:
        render_risk_card(
            "Needs CIO Attention",
            f"{owner_gaps + unmapped_applications + high_risk_applications:,}",
            "Owner, spend, or risk gaps requiring review",
            icon="risk",
            status="critical" if owner_gaps or unmapped_applications or high_risk_applications else "healthy",
        )

    render_insight_card(
        "Cost & Ownership Context",
        description=(
            "This view separates application accountability from dependency analysis: it shows which "
            "applications exist, who owns them, how much cost is allocated, and which records need cleanup."
        ),
        status="info",
    )
    _show_dataframe(
        ApplicationInventoryCertificationService.format_money_columns(cost_ownership_df, ["Allocated Spend", "Unallocated Spend"]),
        "No application cost and ownership data is available.",
    )

    render_section(
        "Spend Allocation Quality",
        "Cost mapping completeness and unmapped financial exposure by application portfolio.",
    )
    allocation_cols = st.columns(3)
    with allocation_cols[0]:
        render_health_card(
            "Allocation Coverage",
            f"{allocation_coverage}%",
            "Share of application spend mapped to registered apps",
            status=ApplicationInventoryCertificationService.health_status(allocation_coverage),
        )
    with allocation_cols[1]:
        render_risk_card(
            "Unmapped Technology Spend",
            ApplicationInventoryCertificationService.format_money(unmapped_spend),
            "Portfolio spend not mapped to applications",
            status="critical" if unmapped_spend else "healthy",
        )
    with allocation_cols[2]:
        render_risk_card(
            "Unmapped Applications",
            f"{unmapped_applications:,}",
            "Applications without allocated spend",
            status="critical" if unmapped_applications else "healthy",
        )

    render_section(
        "Application Risk & Health",
        "Operational and financial risk signals across the application portfolio.",
    )
    risk_cols = st.columns(3)
    with risk_cols[0]:
        render_health_card(
            "Average Health Score",
            f"{average_health_score}%",
            "Portfolio health based on mapping, ownership, and risks",
            status=ApplicationInventoryCertificationService.health_status(average_health_score),
        )
    with risk_cols[1]:
        render_risk_card(
            "Unmapped Applications",
            f"{unmapped_applications:,}",
            "Applications needing spend mapping cleanup",
            status="critical" if unmapped_applications else "healthy",
        )
    with risk_cols[2]:
        render_risk_card(
            "Risk Items",
            f"{high_risk_applications:,}",
            "Active portfolio risk summary items",
            status="critical" if high_risk_applications else "healthy",
        )

    render_ai_narrative(
        "Executive Application Insight",
        ApplicationPortfolioService.get_executive_narrative(),
        description="CIO narrative generated from application registry, spend mapping, and dependency signals.",
    )

    render_section(
        "Detailed Evidence / Drilldown",
        "Source tables for application registry, cost allocation, dependencies, mapping gaps, and risk.",
    )
    with st.expander("Detailed Evidence / Drilldown"):
        st.subheader("Application Portfolio")
        _show_dataframe(
            portfolio_df,
            "No application portfolio data is available.",
        )

        st.subheader("Cost Allocation Summary")
        _show_dataframe(
            ApplicationInventoryCertificationService.format_money_columns(cost_df, ["Cloud", "SaaS", "MSP", "License", "Total"]),
            "No application cost allocation data is available.",
        )

        st.subheader("Dependency Summary")
        _show_dataframe(
            dependency_summary_df,
            "No dependency summary data is available.",
        )

        st.subheader("Technology Dependency Evidence")
        _show_dataframe(
            ApplicationInventoryCertificationService.format_money_columns(application_map_df, ["Spend"]),
            "No application dependency mapping data is available.",
        )

        st.subheader("Technical Mapping Visualization")
        graph = _dependency_graph(dependency_df)
        if graph:
            plotly_chart(graph)
        else:
            st.info("No application dependency graph data is available.")

        st.subheader("Allocation Gap Analysis")
        gap_table = unallocated_df.copy()
        if not gap_table.empty:
            gap_table = gap_table[["Spend Source", "Amount", "Status"]]
        _show_dataframe(
            ApplicationInventoryCertificationService.format_money_columns(gap_table, ["Amount"]),
            "No unallocated spend is currently identified.",
        )

        st.subheader("Risk Summary")
        _show_dataframe(
            risk_df,
            "No application portfolio risks are currently identified.",
        )

    render_certification_evidence()


render_page(
    title="Applications",
    description="CIO view of application ownership, spend mapping, dependencies, criticality, and risk.",
    breadcrumbs=["Home", "CIO", "Applications"],
    content=render_application_content,
    status=ApplicationInventoryCertificationService.health_status(average_health_score),
)
