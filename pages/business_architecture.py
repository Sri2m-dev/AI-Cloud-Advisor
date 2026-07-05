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
        "Canonical financial model status across business, application, technology, cost, risk, and automation mappings.",
    )
    cols = st.columns(3)
    status = summary.get("status", "Unmapped")
    with cols[0]:
        render_risk_card("Data Reconciliation Status", status, "Enterprise Financial Model", icon="governance", status=_financial_status_level(status))
    with cols[1]:
        render_metric_card("Allocation Coverage", _percent(summary.get("allocation_coverage")), "Canonical spend mapped to the business architecture", icon="graph", status=_financial_status_level(status))
    with cols[2]:
        render_metric_card("Unallocated Spend", _money(summary.get("unallocated_spend")), "Spend not yet mapped to a canonical business path", icon="cost", status="warning" if summary.get("unallocated_spend") else "healthy")


def _maturity_score(
    unit_summary: dict[str, Any],
    capability_summary: dict[str, Any],
    service_summary: dict[str, Any],
    process_summary: dict[str, Any],
) -> float:
    dimensions = [
        100 if unit_summary.get("business_units") else 0,
        float(capability_summary.get("mapping_coverage") or 0),
        100 if service_summary.get("business_services") else 0,
        100 if process_summary.get("business_processes") else 0,
        float(service_summary.get("average_health") or 0),
        max(100 - float(process_summary.get("average_risk") or 0), 0),
        min(float(process_summary.get("automation_opportunities") or 0) * 20, 100),
    ]
    return round(sum(dimensions) / len(dimensions), 1) if dimensions else 0.0


def _architecture_rollup(
    unit_summary: dict[str, Any],
    capability_summary: dict[str, Any],
    service_summary: dict[str, Any],
    process_summary: dict[str, Any],
    maturity: float,
) -> pd.DataFrame:
    rows = [
        {"Layer": "Business Units", "Count": unit_summary.get("business_units", 0), "Coverage": unit_summary.get("mapping_coverage", 0), "Signal": "Operating model"},
        {"Layer": "Capabilities", "Count": capability_summary.get("total_capabilities", 0), "Coverage": capability_summary.get("mapping_coverage", 0), "Signal": "Business architecture"},
        {"Layer": "Services", "Count": service_summary.get("business_services", 0), "Coverage": service_summary.get("average_health", 0), "Signal": "Business service model"},
        {"Layer": "Processes", "Count": process_summary.get("business_processes", 0), "Coverage": process_summary.get("governance_score", 0), "Signal": "Operational layer"},
        {"Layer": "Applications", "Count": process_summary.get("applications", 0), "Coverage": process_summary.get("average_health", 0), "Signal": "Application support"},
        {"Layer": "Technologies", "Count": process_summary.get("technologies", 0), "Coverage": service_summary.get("average_health", 0), "Signal": "Technology support"},
        {"Layer": "Maturity", "Count": maturity, "Coverage": maturity, "Signal": "Business-to-technology traceability"},
    ]
    return pd.DataFrame(rows)


def _traceability_rows(
    capabilities: list[dict[str, Any]],
    services: list[dict[str, Any]],
    processes: list[dict[str, Any]],
) -> pd.DataFrame:
    rows = []
    for capability in capabilities:
        capability_name = capability.get("name")
        linked_services = [
            service for service in services
            if service.get("business_capability") == capability_name
        ] or [{"name": "Unmapped Service", "applications": [], "technologies": []}]
        for service in linked_services:
            linked_processes = [
                process for process in processes
                if process.get("business_capability") == capability_name
                and (
                    process.get("business_service") == service.get("name")
                    or service.get("name") == "Unmapped Service"
                )
            ] or [{"name": "Unmapped Process", "applications": service.get("applications", []), "technologies": service.get("technologies", [])}]
            for process in linked_processes:
                rows.append(
                    {
                        "Business Unit": capability.get("business_unit"),
                        "Capability": capability_name,
                        "Service": service.get("name"),
                        "Process": process.get("name"),
                        "Applications": len(process.get("applications") or []),
                        "Technologies": len(process.get("technologies") or []),
                        "Monthly Cost": _money(process.get("monthly_cost") or service.get("monthly_cost") or capability.get("monthly_cost")),
                        "Health": _percent(process.get("health_score") or capability.get("health_score")),
                        "Risk": _percent(process.get("risk_score") or capability.get("risk_score")),
                    }
                )
    return pd.DataFrame(rows)


def _executive_narrative(
    unit_summary: dict[str, Any],
    capability_summary: dict[str, Any],
    service_summary: dict[str, Any],
    process_summary: dict[str, Any],
    maturity: float,
) -> str:
    sentences = [
        (
            f"The business architecture layer connects {unit_summary.get('business_units', 0)} business unit(s), "
            f"{capability_summary.get('total_capabilities', 0)} capability/capabilities, "
            f"{service_summary.get('business_services', 0)} service(s), and "
            f"{process_summary.get('business_processes', 0)} operational process(es)."
        ),
        (
            f"Mapped monthly cost is {_money(process_summary.get('monthly_cost') or service_summary.get('monthly_cost'))}, "
            f"with {_money(process_summary.get('optimization_opportunity') or service_summary.get('potential_savings'))} in optimization opportunity."
        ),
        (
            f"Average process health is {_percent(process_summary.get('average_health'))}, "
            f"average risk is {_percent(process_summary.get('average_risk'))}, and "
            f"{process_summary.get('automation_opportunities', 0)} automation opportunity signal(s) are available."
        ),
        (
            f"Enterprise business-to-technology maturity is {_percent(maturity)}, reflecting traceability from business ownership into processes, applications, and technology platforms."
        ),
    ]
    return _escape_money(" ".join(sentences))


configure_page(
    page_title="Business Architecture | Nexora",
    page_icon="BA",
)

init_session()
require_role(["executive", "cio", "finance", "super_admin"])

role = st.session_state.get("role", "cio")
render_enterprise_sidebar(
    role,
    page_paths=PAGE_PATHS,
    role_pages=ROLE_PAGES,
    active_page=PAGE_PATHS.get("Business Architecture", "pages/business_architecture.py"),
)

unit_dashboard = BusinessUnitService.get_dashboard()
unit_summary = unit_dashboard["summary"]

capability_dashboard = BusinessCapabilityService.get_capability_dashboard()
capability_summary = capability_dashboard["summary"]
capabilities = capability_dashboard["capabilities"]

service_dashboard = BusinessServiceService.get_service_dashboard()
service_summary = service_dashboard["summary"]
services = service_dashboard["business_services"]

process_dashboard = BusinessProcessService.get_process_dashboard()
process_summary = process_dashboard["summary"]
processes = process_dashboard["business_processes"]

financial_summary = EnterpriseFinancialModel.get_enterprise_summary()

maturity = _maturity_score(unit_summary, capability_summary, service_summary, process_summary)
architecture_rollup = _architecture_rollup(unit_summary, capability_summary, service_summary, process_summary, maturity)
traceability = _traceability_rows(capabilities, services, processes)


def render_business_architecture_content() -> None:
    render_section(
        "Business Architecture Executive Summary",
        "Executive view of business-to-technology traceability across units, capabilities, services, processes, applications, technology, cost, risk, and automation.",
        divider=False,
    )

    kpi_cols = st.columns(4)
    with kpi_cols[0]:
        render_kpi_card("Business Units", f"{unit_summary['business_units']:,}", "Operating units in scope", icon="enterprise", status="info")
    with kpi_cols[1]:
        render_metric_card("Capabilities", f"{capability_summary['total_capabilities']:,}", "Business capabilities mapped", icon="governance", status="info")
    with kpi_cols[2]:
        render_metric_card("Services", f"{service_summary['business_services']:,}", "Business services connected", icon="service", status="info")
    with kpi_cols[3]:
        render_metric_card("Processes", f"{process_summary['business_processes']:,}", "Operational processes connected", icon="workflow", status="info")

    signal_cols = st.columns(4)
    with signal_cols[0]:
        render_metric_card("Applications", f"{process_summary['applications']:,}", "Applications supporting processes", icon="application", status="info")
    with signal_cols[1]:
        render_metric_card("Technologies", f"{process_summary['technologies']:,}", "Technology platforms supporting operations", icon="technology", status="info")
    with signal_cols[2]:
        render_metric_card("Mapped Cost", _money(process_summary["monthly_cost"] or service_summary["monthly_cost"]), "Monthly business architecture cost", icon="cost", status="healthy")
    with signal_cols[3]:
        render_health_card("Maturity", _percent(maturity), "Business-to-technology maturity", icon="health", status=_status_from_score(maturity))

    posture_cols = st.columns(3)
    with posture_cols[0]:
        render_health_card("Health", _percent(process_summary["average_health"]), "Average process health", icon="health", status=_status_from_score(process_summary["average_health"]))
    with posture_cols[1]:
        render_risk_card("Risk", _percent(process_summary["average_risk"]), "Average process risk", icon="risk", status=_risk_status(process_summary["average_risk"]))
    with posture_cols[2]:
        render_metric_card("Automation", f"{process_summary['automation_opportunities']:,}", "Automation opportunity signals", icon="automation", status="info" if process_summary["automation_opportunities"] else "healthy")

    _render_financial_reconciliation(financial_summary)

    render_section(
        "Executive Narrative",
        "Concise business architecture interpretation for CIO and executive review.",
    )
    render_insight_card(
        "Business Architecture Signal",
        description=_executive_narrative(unit_summary, capability_summary, service_summary, process_summary, maturity),
        status=_status_from_score(maturity),
    )

    render_section(
        "Enterprise Architecture Rollup",
        "Layer-by-layer maturity and coverage across the business architecture model.",
    )
    display_rollup = architecture_rollup.copy()
    display_rollup["Coverage"] = display_rollup["Coverage"].apply(_percent)
    _show_dataframe(display_rollup, "No business architecture rollup is available yet.")
    fig = px.bar(
        architecture_rollup,
        x="Layer",
        y="Coverage",
        color="Signal",
        title="Business Architecture Coverage by Layer",
    )
    st.plotly_chart(fig, use_container_width=True)

    render_section(
        "Business-to-Technology Traceability",
        "Business Unit -> Capability -> Service -> Process -> Application -> Technology traceability.",
    )
    _show_dataframe(traceability, "No traceability paths are available yet.")

    render_section(
        "Cost, Health, Risk, and Automation",
        "Executive rollup of financial, operating, and automation posture.",
    )
    metrics_df = pd.DataFrame(
        [
            {"Metric": "Monthly Cost", "Value": _money(process_summary["monthly_cost"] or service_summary["monthly_cost"]), "Domain": "Cost"},
            {"Metric": "Annual Cost", "Value": _money(process_summary["annual_cost"]), "Domain": "Cost"},
            {"Metric": "Optimization", "Value": _money(process_summary["optimization_opportunity"]), "Domain": "Cost"},
            {"Metric": "Health", "Value": _percent(process_summary["average_health"]), "Domain": "Operations"},
            {"Metric": "Risk", "Value": _percent(process_summary["average_risk"]), "Domain": "Risk"},
            {"Metric": "Automation", "Value": f"{process_summary['automation_opportunities']:,}", "Domain": "Automation"},
            {"Metric": "Maturity", "Value": _percent(maturity), "Domain": "Architecture"},
        ]
    )
    _show_dataframe(metrics_df, "No executive architecture metrics are available yet.")

    render_section(
        "Detailed Evidence",
        "Standard evidence for source data, data coverage, relationship completeness, AI interpretation, and raw architecture records.",
    )
    process_df = pd.DataFrame(processes)
    business_units_df = pd.DataFrame(unit_dashboard.get("business_units", []))
    source_df = pd.DataFrame(
        [
            {"Section": "Business Units", "Source": "business_units", "Status": "Live or Derived"},
            {"Section": "Capabilities", "Source": "business_capabilities", "Status": "Live or Derived"},
            {"Section": "Services", "Source": "business_services", "Status": "Live or Derived"},
            {"Section": "Processes", "Source": "business_processes", "Status": "Live or Derived"},
            {"Section": "Applications", "Source": "application_registry", "Status": "Derived through service/process mappings"},
            {"Section": "Technologies", "Source": "technology_inventory", "Status": "Derived through service/process mappings"},
            {"Section": "Costs", "Source": "mart_application_spend", "Status": "Derived through cost allocation"},
            {"Section": "Relationships", "Source": "technology_relationships", "Status": "Derived through traceability paths"},
        ]
    )
    missing_owners = sum(
        1
        for row in [*capabilities, *services, *processes]
        if str(row.get("owner") or "").strip().lower() in {"", "unknown", "unassigned"}
    )
    missing_cost = sum(
        1
        for row in [*capabilities, *services, *processes]
        if float(row.get("monthly_cost") or 0) <= 0
    )
    missing_app_mapping = sum(1 for row in [*services, *processes] if not row.get("applications"))
    missing_tech_mapping = sum(1 for row in [*services, *processes] if not row.get("technologies"))
    coverage_df = pd.DataFrame(
        [
            {"Indicator": "Mapping Coverage", "Value": _percent(maturity), "Executive Meaning": "Overall business-to-technology evidence maturity"},
            {"Indicator": "Missing Owners", "Value": f"{missing_owners:,}", "Executive Meaning": "Records without accountable ownership"},
            {"Indicator": "Missing Cost Allocation", "Value": f"{missing_cost:,}", "Executive Meaning": "Records without mapped monthly cost"},
            {"Indicator": "Missing Technology Mapping", "Value": f"{missing_tech_mapping:,}", "Executive Meaning": "Services or processes without technology evidence"},
            {"Indicator": "Missing Application Mapping", "Value": f"{missing_app_mapping:,}", "Executive Meaning": "Services or processes without application evidence"},
        ]
    )
    relationship_df = pd.DataFrame(
        [
            {"Relationship": "Business Units", "Count": unit_summary.get("business_units", 0)},
            {"Relationship": "Capabilities", "Count": capability_summary.get("total_capabilities", 0)},
            {"Relationship": "Services", "Count": service_summary.get("business_services", 0)},
            {"Relationship": "Processes", "Count": process_summary.get("business_processes", 0)},
            {"Relationship": "Applications", "Count": process_summary.get("applications", service_summary.get("applications", 0))},
            {"Relationship": "Technologies", "Count": process_summary.get("technologies", service_summary.get("technologies", 0))},
            {"Relationship": "Relationships", "Count": len(traceability)},
        ]
    )
    st.markdown("#### Source Data")
    _show_dataframe(source_df, "No source data evidence is available yet.")
    st.markdown("#### Data Coverage")
    _show_dataframe(coverage_df, "No data coverage evidence is available yet.")
    st.markdown("#### Relationship Summary")
    _show_dataframe(relationship_df, "No relationship summary evidence is available yet.")
    traceability_app_columns = ["Business Unit", "Capability", "Service", "Process", "Applications"]
    traceability_tech_columns = ["Business Unit", "Capability", "Service", "Process", "Technologies"]
    traceability_app_df = (
        traceability[traceability_app_columns]
        if all(column in traceability.columns for column in traceability_app_columns)
        else pd.DataFrame()
    )
    traceability_tech_df = (
        traceability[traceability_tech_columns]
        if all(column in traceability.columns for column in traceability_tech_columns)
        else pd.DataFrame()
    )
    render_insight_card(
        "AI Interpretation",
        description=(
            f"Business architecture evidence links {len(traceability):,} traceability path(s). "
            f"{missing_owners:,} ownership gap(s), {missing_cost:,} cost allocation gap(s), "
            f"{missing_app_mapping:,} application mapping gap(s), and {missing_tech_mapping:,} technology mapping gap(s) remain for review."
        ),
        status=_status_from_score(maturity),
    )
    st.markdown("#### Raw Evidence")
    with st.expander("Business Units", expanded=False):
        _show_dataframe(business_units_df, "No business unit evidence is available yet.")
    with st.expander("Capabilities", expanded=False):
        _show_dataframe(pd.DataFrame(capabilities), "No capability evidence is available yet.")
    with st.expander("Services", expanded=False):
        _show_dataframe(pd.DataFrame(services), "No service evidence is available yet.")
    with st.expander("Processes", expanded=True):
        _show_dataframe(process_df, "No process evidence is available yet.")
    with st.expander("Applications", expanded=False):
        _show_dataframe(traceability_app_df, "No application evidence is available yet.")
    with st.expander("Technologies", expanded=False):
        _show_dataframe(traceability_tech_df, "No technology evidence is available yet.")
    with st.expander("Cost Allocation", expanded=False):
        _show_dataframe(metrics_df, "No cost allocation evidence is available yet.")
    with st.expander("Relationships", expanded=False):
        _show_dataframe(traceability, "No relationship evidence is available yet.")
    with st.expander("Recommendations", expanded=False):
        _show_dataframe(
            pd.DataFrame(
                [
                    {"Recommendation": "Close ownership gaps", "Count": missing_owners},
                    {"Recommendation": "Complete cost allocation", "Count": missing_cost},
                    {"Recommendation": "Complete application mapping", "Count": missing_app_mapping},
                    {"Recommendation": "Complete technology mapping", "Count": missing_tech_mapping},
                ]
            ),
            "No recommendation evidence is available yet.",
        )


render_page(
    title="Business Architecture",
    description="Executive summary of enterprise business architecture maturity and business-to-technology traceability.",
    breadcrumbs=["Home", "Enterprise Digital Twin", "Business Architecture"],
    content=render_business_architecture_content,
    status=_status_from_score(maturity),
    footer_version="E7.1.10",
)
