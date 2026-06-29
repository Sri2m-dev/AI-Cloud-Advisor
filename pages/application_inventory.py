from __future__ import annotations

from typing import Any

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
from components.sidebar_navigation import PAGE_PATHS, ROLE_PAGES
from services.application_portfolio_service import ApplicationPortfolioService
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
        return f"${amount / 1_000:.1f}K"
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


def _health_status(score: float) -> str:
    if score >= 90:
        return "healthy"
    if score >= 75:
        return "warning"
    return "critical"


def _first_text(values: list[Any], default: str = "-") -> str:
    for value in values:
        text = str(value or "").strip()
        if text and text.lower() not in {"nan", "none", "unassigned"}:
            return text
    return default


def _application_dependency_map(
    dependency_df: pd.DataFrame,
    portfolio_df: pd.DataFrame,
    cost_df: pd.DataFrame,
) -> pd.DataFrame:
    if dependency_df.empty:
        return pd.DataFrame(columns=["Application", "Business Service", "Technology", "Type", "Owner", "Spend"])

    owner_lookup = {}
    if not portfolio_df.empty and {"Application", "Owner"}.issubset(portfolio_df.columns):
        owner_lookup = {
            str(row["Application"]).lower(): row["Owner"]
            for _, row in portfolio_df.iterrows()
        }

    spend_lookup = {}
    if not cost_df.empty and {"App", "Total"}.issubset(cost_df.columns):
        spend_lookup = {
            str(row["App"]).lower(): row["Total"]
            for _, row in cost_df.iterrows()
        }

    rows = []
    for _, row in dependency_df.iterrows():
        target_type = str(row.get("Target Type") or "").lower()
        if target_type != "technology":
            continue

        application = _first_text([row.get("Source")], "Unknown Application")
        business_service = application if application != "Unknown Application" else _first_text(
            portfolio_df["Application"].tolist() if not portfolio_df.empty and "Application" in portfolio_df.columns else [],
            "Unknown Business Service",
        )
        owner = owner_lookup.get(application.lower(), "Unassigned")
        spend = spend_lookup.get(application.lower(), 0)

        rows.append(
            {
                "Application": application,
                "Business Service": business_service,
                "Technology": _first_text([row.get("Target")], "Unknown Technology"),
                "Type": _first_text([row.get("Dependency Type")], "Technology"),
                "Owner": owner,
                "Spend": spend,
            }
        )

    return pd.DataFrame(rows)


def _application_cost_ownership_map(
    portfolio_df: pd.DataFrame,
    cost_df: pd.DataFrame,
    unallocated_spend: float,
) -> pd.DataFrame:
    if portfolio_df.empty:
        return pd.DataFrame(
            columns=[
                "Application",
                "Business Owner",
                "Technical Owner",
                "Business Unit",
                "Department",
                "Allocated Spend",
                "Unallocated Spend",
                "Criticality",
                "Health",
            ]
        )

    spend_lookup = {}
    if not cost_df.empty and {"App", "Total"}.issubset(cost_df.columns):
        spend_lookup = {
            str(row["App"]).lower(): row["Total"]
            for _, row in cost_df.iterrows()
        }

    rows = []
    for _, row in portfolio_df.iterrows():
        application = _first_text([row.get("Application")], "Unknown Application")
        owner = _first_text([row.get("Owner")], "Unassigned")
        business_unit = _first_text([row.get("Business Unit")], "Unassigned")
        allocated = float(spend_lookup.get(application.lower(), 0) or 0)
        criticality = _first_text([row.get("Criticality")], "Standard")
        has_owner = owner != "Unassigned"
        has_spend = allocated > 0

        if has_owner and has_spend:
            health = "Healthy"
        elif has_owner or has_spend:
            health = "Needs Review"
        else:
            health = "Attention Required"

        rows.append(
            {
                "Application": application,
                "Business Owner": owner,
                "Technical Owner": "Unassigned",
                "Business Unit": business_unit,
                "Department": business_unit,
                "Allocated Spend": allocated,
                "Unallocated Spend": 0 if has_spend or len(portfolio_df) != 1 else unallocated_spend,
                "Criticality": criticality,
                "Health": health,
            }
        )

    return pd.DataFrame(rows)


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

summary = ApplicationPortfolioService.get_application_summary()
portfolio_df = ApplicationPortfolioService.application_portfolio_dataframe()
cost_df = ApplicationPortfolioService.cost_allocation_dataframe()
dependency_df = ApplicationPortfolioService.dependency_graph_dataframe()
dependency_summary_df = ApplicationPortfolioService.dependency_summary_dataframe()
unallocated_df = ApplicationPortfolioService.unallocated_spend_dataframe()
risk_df = ApplicationPortfolioService.risk_summary_dataframe()
application_map_df = _application_dependency_map(dependency_df, portfolio_df, cost_df)

total_applications = summary["applications"]
business_critical_apps = summary["critical_applications"]
application_spend = summary["allocated_spend"]
unmapped_spend = summary["unallocated_spend"]
total_spend_scope = application_spend + unmapped_spend
mapped_applications = int((cost_df["Total"] > 0).sum()) if not cost_df.empty and "Total" in cost_df.columns else 0
unmapped_applications = max(total_applications - mapped_applications, 0)
owner_gaps = (
    int(portfolio_df["Owner"].astype(str).str.lower().isin(["", "unassigned", "none", "nan"]).sum())
    if not portfolio_df.empty and "Owner" in portfolio_df.columns
    else 0
)
high_risk_applications = len(risk_df)
average_health_score = round(
    (
        (mapped_applications / total_applications * 45 if total_applications else 0)
        + ((total_applications - owner_gaps) / total_applications * 35 if total_applications else 0)
        + (20 if high_risk_applications == 0 else max(0, 20 - high_risk_applications * 5))
    ),
    1,
)
allocation_coverage = round((application_spend / total_spend_scope) * 100, 1) if total_spend_scope else 0
cost_ownership_df = _application_cost_ownership_map(portfolio_df, cost_df, unmapped_spend)


def render_application_content() -> None:
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
            status=_health_status(allocation_coverage),
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
            "Application Spend",
            _money(application_spend),
            f"{allocation_coverage}% allocation coverage",
            icon="cost",
            status=_health_status(allocation_coverage),
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
            status=_health_status(average_health_score),
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
            "Allocated Spend",
            _money(application_spend),
            "Spend mapped to registered applications",
            icon="cost",
            status="info",
        )
    with ownership_cols[1]:
        render_risk_card(
            "Unallocated Spend",
            _money(unmapped_spend),
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
            "Allocated Spend",
            _money(application_spend),
            "Spend mapped to registered applications",
            icon="cost",
            status=_health_status(allocation_coverage),
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
        _format_money_columns(cost_ownership_df, ["Allocated Spend", "Unallocated Spend"]),
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
            status=_health_status(allocation_coverage),
        )
    with allocation_cols[1]:
        render_risk_card(
            "Unallocated Spend",
            _money(unmapped_spend),
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
            status=_health_status(average_health_score),
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

    render_section(
        "Executive Application Insight",
        "CIO narrative generated from application registry, spend mapping, and dependency signals.",
    )
    render_insight_card(
        "Application Portfolio Narrative",
        description=ApplicationPortfolioService.get_executive_narrative(),
        status=_health_status(average_health_score),
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
            _format_money_columns(cost_df, ["Cloud", "SaaS", "MSP", "License", "Total"]),
            "No application cost allocation data is available.",
        )

        st.subheader("Dependency Summary")
        _show_dataframe(
            dependency_summary_df,
            "No dependency summary data is available.",
        )

        st.subheader("Technology Dependency Evidence")
        _show_dataframe(
            _format_money_columns(application_map_df, ["Spend"]),
            "No application dependency mapping data is available.",
        )

        st.subheader("Technical Mapping Visualization")
        graph = _dependency_graph(dependency_df)
        if graph:
            st.plotly_chart(graph, use_container_width=True)
        else:
            st.info("No application dependency graph data is available.")

        st.subheader("Allocation Gap Analysis")
        gap_table = unallocated_df.copy()
        if not gap_table.empty:
            gap_table = gap_table[["Spend Source", "Amount", "Status"]]
        _show_dataframe(
            _format_money_columns(gap_table, ["Amount"]),
            "No unallocated spend is currently identified.",
        )

        st.subheader("Risk Summary")
        _show_dataframe(
            risk_df,
            "No application portfolio risks are currently identified.",
        )


render_page(
    title="Applications",
    description="CIO view of application ownership, spend mapping, dependencies, criticality, and risk.",
    breadcrumbs=["Home", "CIO", "Applications"],
    content=render_application_content,
    status=_health_status(average_health_score),
)
