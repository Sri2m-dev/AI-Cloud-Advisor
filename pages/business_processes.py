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
from services.business_capability_service import BusinessCapabilityService
from services.business_process_service import BusinessProcessService
from services.business_service_service import BusinessServiceService
from services.business_unit_service import BusinessUnitService
from services.enterprise_financial_model import EnterpriseFinancialModel
from shared.auth import require_role
from shared.session import init_session
from shared.styles import configure_page


def _money(value: Any) -> str:
    try:
        amount = float(value or 0)
    except (TypeError, ValueError):
        amount = 0.0
    if abs(amount) >= 1_000_000:
        return f"${amount / 1_000_000:.1f}M"
    if abs(amount) >= 1_000:
        return f"${amount / 1_000:.1f}K"
    return f"${amount:,.0f}"


def _percent(value: Any) -> str:
    try:
        return f"{float(value or 0):.1f}%"
    except (TypeError, ValueError):
        return "0.0%"


def _status_from_score(score: Any) -> str:
    try:
        value = float(score or 0)
    except (TypeError, ValueError):
        value = 0.0
    if value >= 90:
        return "healthy"
    if value >= 70:
        return "warning"
    return "critical"


def _risk_status(score: Any) -> str:
    try:
        value = float(score or 0)
    except (TypeError, ValueError):
        value = 0.0
    if value >= 70:
        return "critical"
    if value >= 35:
        return "warning"
    return "healthy"


def _escape_money(text: str) -> str:
    return text.replace("$", r"\$")


def _list_text(values: list[Any] | None) -> str:
    clean = [str(value) for value in values or [] if str(value or "").strip()]
    return ", ".join(clean) if clean else "Unmapped"


def _show_dataframe(df: pd.DataFrame, empty_message: str) -> None:
    if df.empty:
        st.info(empty_message)
        return
    st.dataframe(df, use_container_width=True, hide_index=True)


def _financial_status_level(status: Any) -> str:
    text = str(status or "").lower()
    if "variance" in text or "unmapped" in text:
        return "critical"
    if "partial" in text:
        return "warning"
    return "healthy"


def _render_financial_reconciliation(summary: dict[str, Any]) -> None:
    render_section(
        "Data Reconciliation Status",
        "Canonical financial model status across process cost, forecast, optimization, and unallocated spend.",
    )
    cols = st.columns(3)
    status = summary.get("status", "Unmapped")
    with cols[0]:
        render_risk_card("Data Reconciliation Status", status, "Enterprise Financial Model", icon="governance", status=_financial_status_level(status))
    with cols[1]:
        render_metric_card("Allocation Coverage", _percent(summary.get("allocation_coverage")), "Canonical spend mapped to business processes", icon="graph", status=_financial_status_level(status))
    with cols[2]:
        render_metric_card("Unallocated Spend", _money(summary.get("unallocated_spend")), "Spend not yet mapped to a canonical business path", icon="cost", status="warning" if summary.get("unallocated_spend") else "healthy")


def _process_inventory_rows(processes: list[dict[str, Any]]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "Process": row.get("name"),
                "Business Service": row.get("business_service"),
                "Business Capability": row.get("business_capability"),
                "Business Unit": row.get("business_unit"),
                "Owner": row.get("owner"),
                "Criticality": row.get("criticality"),
                "SLA": row.get("sla"),
                "Status": row.get("status"),
            }
            for row in processes
        ]
    )


def _cost_rows(costs: list[dict[str, Any]]) -> pd.DataFrame:
    df = pd.DataFrame(costs)
    if df.empty:
        return df
    for column in ["Monthly Spend", "Annual Spend", "Forecast", "Optimization Opportunity"]:
        if column in df.columns:
            df[column] = df[column].apply(_money)
    return df


def _health_rows(health: list[dict[str, Any]]) -> pd.DataFrame:
    df = pd.DataFrame(health)
    if df.empty:
        return df
    for column in ["Health Score", "Dependency Score"]:
        if column in df.columns:
            df[column] = df[column].apply(_percent)
    return df


def _risk_rows(risks: list[dict[str, Any]]) -> pd.DataFrame:
    df = pd.DataFrame(risks)
    if df.empty:
        return df
    if "Risk Score" in df.columns:
        df["Risk Score"] = df["Risk Score"].apply(_percent)
    return df


def _recommendation_rows(recommendations: list[dict[str, Any]]) -> pd.DataFrame:
    df = pd.DataFrame(recommendations)
    if df.empty:
        return df
    if "Optimization Opportunity" in df.columns:
        df["Optimization Opportunity"] = df["Optimization Opportunity"].apply(_money)
    return df


def _evidence_rows(processes: list[dict[str, Any]]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "Process ID": row.get("id"),
                "Process": row.get("name"),
                "Business Unit": row.get("business_unit"),
                "Capability": row.get("business_capability"),
                "Business Service": row.get("business_service"),
                "Applications": _list_text(row.get("applications")),
                "Technologies": _list_text(row.get("technologies")),
                "Cloud Resources": row.get("cloud_resources"),
                "Source": row.get("source"),
                "Last Updated": row.get("last_updated"),
            }
            for row in processes
        ]
    )


def _executive_narrative(
    summary: dict[str, Any],
    risks: list[dict[str, Any]],
) -> str:
    elevated = [
        row for row in risks
        if "Elevated" in str(row.get("Dependency Risk")) or float(row.get("Risk Score") or 0) >= 35
    ]
    sentences = [
        (
            f"The enterprise currently operates {summary.get('business_processes', 0)} business process(es) "
            f"supporting {summary.get('business_services', 0)} business service(s) across "
            f"{summary.get('business_units', 0)} business unit(s)."
        ),
        (
            f"{len(elevated)} process(es) show elevated dependency or risk signals that may require executive review."
        ),
        (
            f"Mapped process monthly cost is {_money(summary.get('monthly_cost'))}, with "
            f"{_money(summary.get('optimization_opportunity'))} in optimization opportunity."
        ),
        (
            f"Automation initiatives include {summary.get('automation_opportunities', 0)} opportunity signal(s) "
            "that could improve delivery efficiency and operating resilience."
        ),
    ]
    return _escape_money(" ".join(sentences))


configure_page(
    page_title="Business Processes | Nexora",
    page_icon="BP",
)

init_session()
require_role(["executive", "cio", "finance", "super_admin", "technical"])

role = st.session_state.get("role", "cio")
render_enterprise_sidebar(
    role,
    page_paths=PAGE_PATHS,
    role_pages=ROLE_PAGES,
    active_page=PAGE_PATHS.get("Business Processes", "pages/business_processes.py"),
)

dashboard = BusinessProcessService.get_process_dashboard()
summary = dashboard["summary"]
processes = dashboard["business_processes"]
dependencies = dashboard["dependencies"]
costs = dashboard["costs"]
health = dashboard["health"]
risks = dashboard["risks"]
recommendations = dashboard["recommendations"]

unit_dashboard = BusinessUnitService.get_dashboard()
unit_summary = unit_dashboard["summary"]
business_units = unit_dashboard["business_units"]

capability_dashboard = BusinessCapabilityService.get_capability_dashboard()
capability_summary = capability_dashboard["summary"]
capabilities = capability_dashboard["capabilities"]

service_dashboard = BusinessServiceService.get_service_dashboard()
service_summary = service_dashboard["summary"]
business_services = service_dashboard["business_services"]

financial_summary = EnterpriseFinancialModel.get_enterprise_summary()


def render_business_processes_content() -> None:
    render_section(
        "Executive Process Summary",
        "Operational process layer connecting business services to applications, technologies, cloud resources, cost, risk, and automation signals.",
        divider=False,
    )

    kpi_cols = st.columns(4)
    with kpi_cols[0]:
        render_kpi_card(
            "Business Processes",
            f"{summary['business_processes']:,}",
            "Operational processes in scope",
            icon="workflow",
            status="info",
        )
    with kpi_cols[1]:
        render_metric_card(
            "Business Services",
            f"{summary['business_services']:,}",
            "Services supported by processes",
            icon="service",
            status="info",
        )
    with kpi_cols[2]:
        render_metric_card(
            "Applications",
            f"{summary['applications']:,}",
            "Applications supporting processes",
            icon="application",
            status="info",
        )
    with kpi_cols[3]:
        render_metric_card(
            "Technologies",
            f"{summary['technologies']:,}",
            "Technology platforms in process paths",
            icon="technology",
            status="info",
        )

    signal_cols = st.columns(4)
    with signal_cols[0]:
        render_metric_card(
            "Monthly Cost",
            _money(summary["monthly_cost"]),
            "Mapped process operating cost",
            icon="cost",
            status="healthy" if summary["monthly_cost"] else "warning",
        )
    with signal_cols[1]:
        render_health_card(
            "Health Score",
            _percent(summary["average_health"]),
            "Average process health",
            icon="health",
            status=_status_from_score(summary["average_health"]),
        )
    with signal_cols[2]:
        render_health_card(
            "Governance Score",
            _percent(summary["governance_score"]),
            "Owner, SLA, and mapping completeness",
            icon="governance",
            status=_status_from_score(summary["governance_score"]),
        )
    with signal_cols[3]:
        render_metric_card(
            "Automation Opportunities",
            f"{summary['automation_opportunities']:,}",
            "Process automation signals",
            icon="automation",
            status="info" if summary["automation_opportunities"] else "healthy",
        )

    _render_financial_reconciliation(financial_summary)

    render_section(
        "Executive Narrative",
        "Business interpretation of process coverage, operational risk, cost, and automation opportunity.",
    )
    render_insight_card(
        "Operational Process Signal",
        description=_executive_narrative(summary, risks),
        status=_status_from_score(summary["average_health"]),
    )

    render_section(
        "Process Explorer",
        "Business process portfolio by service, capability, business unit, owner, criticality, SLA, and status.",
    )
    _show_dataframe(
        _process_inventory_rows(processes),
        "No business processes are available yet.",
    )

    render_section(
        "End-to-End Process Flow",
        "Business Unit -> Capability -> Service -> Process -> Application -> Technology -> Cloud Resource traceability.",
    )
    dependency_df = pd.DataFrame(dependencies)
    _show_dataframe(
        dependency_df,
        "No process dependency paths are available yet.",
    )

    render_section(
        "Process Cost & Investment",
        "Monthly spend, annualized spend, forecast, and optimization opportunity by business process.",
    )
    cost_df = _cost_rows(costs)
    _show_dataframe(
        cost_df,
        "No process cost data is available yet.",
    )
    if costs:
        chart_df = pd.DataFrame(costs)
        fig = px.bar(
            chart_df,
            x="Business Process",
            y="Monthly Spend",
            color="Business Unit",
            title="Monthly Spend by Business Process",
        )
        st.plotly_chart(fig, use_container_width=True)

    render_section(
        "Process Health & Risk",
        "Health score, SLA, risk score, dependency score, compliance status, and AI recommendation posture.",
    )
    left, right = st.columns(2)
    with left:
        _show_dataframe(
            _health_rows(health),
            "No process health metrics are available yet.",
        )
    with right:
        _show_dataframe(
            _risk_rows(risks),
            "No process risk metrics are available yet.",
        )

    if processes:
        chart_df = pd.DataFrame(processes)
        fig = px.scatter(
            chart_df,
            x="risk_score",
            y="health_score",
            size="monthly_cost",
            color="criticality",
            hover_name="name",
            title="Process Health, Risk, and Cost",
            labels={
                "risk_score": "Risk Score",
                "health_score": "Health Score",
                "monthly_cost": "Monthly Cost",
                "criticality": "Criticality",
            },
            size_max=45,
        )
        st.plotly_chart(fig, use_container_width=True)

    render_section(
        "Detailed Evidence",
        "Standard evidence for source data, data coverage, relationship completeness, AI interpretation, and raw process records.",
    )
    missing_owners = sum(
        1
        for row in [*business_units, *capabilities, *business_services, *processes]
        if str(row.get("Owner") or row.get("owner") or "").strip().lower() in {"", "unknown", "unassigned"}
    )
    missing_cost = sum(
        1
        for row in [*capabilities, *business_services, *processes]
        if float(row.get("monthly_cost") or row.get("Allocated Spend") or 0) <= 0
    )
    missing_app_mapping = sum(1 for row in [*business_services, *processes] if not row.get("applications"))
    missing_tech_mapping = sum(1 for row in [*business_services, *processes] if not row.get("technologies"))
    source_df = pd.DataFrame(
        [
            {"Section": "Business Units", "Source": "business_units", "Status": "Derived through process ownership"},
            {"Section": "Capabilities", "Source": "business_capabilities", "Status": "Derived through process capability mapping"},
            {"Section": "Services", "Source": "business_services", "Status": "Derived through process service mapping"},
            {"Section": "Processes", "Source": "business_processes", "Status": "Live or Derived"},
            {"Section": "Applications", "Source": "application_registry", "Status": "Derived through process mappings"},
            {"Section": "Technologies", "Source": "technology_inventory", "Status": "Derived through process mappings"},
            {"Section": "Costs", "Source": "mart_application_spend", "Status": "Derived through process cost allocation"},
            {"Section": "Relationships", "Source": "technology_relationships", "Status": "Derived through process dependency paths"},
        ]
    )
    coverage_df = pd.DataFrame(
        [
            {"Indicator": "Mapping Coverage", "Value": _percent(summary.get("governance_score")), "Executive Meaning": "Owner, SLA, and process mapping completeness"},
            {"Indicator": "Missing Owners", "Value": f"{missing_owners:,}", "Executive Meaning": "Business process records without accountable ownership"},
            {"Indicator": "Missing Cost Allocation", "Value": f"{missing_cost:,}", "Executive Meaning": "Process records without mapped monthly cost"},
            {"Indicator": "Missing Technology Mapping", "Value": f"{missing_tech_mapping:,}", "Executive Meaning": "Services or processes without technology evidence"},
            {"Indicator": "Missing Application Mapping", "Value": f"{missing_app_mapping:,}", "Executive Meaning": "Services or processes without application evidence"},
        ]
    )
    relationship_df = pd.DataFrame(
        [
            {"Relationship": "Business Units", "Count": unit_summary.get("business_units", 0)},
            {"Relationship": "Capabilities", "Count": capability_summary.get("total_capabilities", 0)},
            {"Relationship": "Services", "Count": summary.get("business_services", service_summary.get("business_services", 0))},
            {"Relationship": "Processes", "Count": summary.get("business_processes", 0)},
            {"Relationship": "Applications", "Count": summary.get("applications", 0)},
            {"Relationship": "Technologies", "Count": summary.get("technologies", 0)},
            {"Relationship": "Relationships", "Count": len(dependencies)},
        ]
    )
    st.markdown("#### Source Data")
    _show_dataframe(source_df, "No source data evidence is available yet.")
    st.markdown("#### Data Coverage")
    _show_dataframe(coverage_df, "No data coverage evidence is available yet.")
    st.markdown("#### Relationship Summary")
    _show_dataframe(relationship_df, "No relationship summary evidence is available yet.")
    render_insight_card(
        "AI Interpretation",
        description=(
            f"Process evidence links {summary.get('business_processes', 0):,} process(es) into {len(dependencies):,} dependency path(s). "
            f"{missing_owners:,} owner gap(s), {missing_cost:,} cost allocation gap(s), "
            f"{missing_app_mapping:,} application mapping gap(s), and {missing_tech_mapping:,} technology mapping gap(s) remain."
        ).replace("$", r"\$"),
        status=_status_from_score(summary.get("governance_score")),
    )
    st.markdown("#### Raw Evidence")
    with st.expander("Business Units", expanded=False):
        _show_dataframe(pd.DataFrame(business_units), "No business unit evidence is available yet.")
    with st.expander("Capabilities", expanded=False):
        _show_dataframe(pd.DataFrame(capabilities), "No capability evidence is available yet.")
    with st.expander("Services", expanded=False):
        _show_dataframe(pd.DataFrame(business_services), "No service evidence is available yet.")
    with st.expander("Processes", expanded=True):
        _show_dataframe(_evidence_rows(processes), "No process inventory evidence is available yet.")
    with st.expander("Applications", expanded=False):
        _show_dataframe(dependency_df, "No application evidence is available yet.")
    with st.expander("Technologies", expanded=False):
        _show_dataframe(dependency_df, "No technology evidence is available yet.")
    with st.expander("Cost Allocation", expanded=False):
        _show_dataframe(cost_df, "No process cost allocation evidence is available yet.")
    with st.expander("Relationships", expanded=False):
        _show_dataframe(dependency_df, "No process relationship evidence is available yet.")
    with st.expander("Recommendations", expanded=False):
        _show_dataframe(_recommendation_rows(recommendations), "No process recommendation evidence is available yet.")


render_page(
    title="Business Processes",
    description="Operational business process layer connecting services, applications, technologies, cloud resources, cost, health, risk, governance, and automation signals.",
    breadcrumbs=["Home", "Enterprise Digital Twin", "Business Processes"],
    content=render_business_processes_content,
    status=_status_from_score(summary["average_health"]),
    footer_version="E7.1.8",
)
