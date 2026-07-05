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


def _count(value: Any) -> int:
    try:
        return int(float(value or 0))
    except (TypeError, ValueError):
        return 0


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
        "Canonical financial model status across capability investment, mapped cost, and unallocated spend.",
    )
    cols = st.columns(3)
    status = summary.get("status", "Unmapped")
    with cols[0]:
        render_risk_card("Data Reconciliation Status", status, "Enterprise Financial Model", icon="governance", status=_financial_status_level(status))
    with cols[1]:
        render_metric_card("Allocation Coverage", _percent(summary.get("allocation_coverage")), "Canonical spend mapped to capabilities", icon="graph", status=_financial_status_level(status))
    with cols[2]:
        render_metric_card("Unallocated Spend", _money(summary.get("unallocated_spend")), "Spend not yet mapped to a canonical business path", icon="cost", status="warning" if summary.get("unallocated_spend") else "healthy")


def _capability_portfolio_rows(
    capabilities: list[dict[str, Any]],
    services: list[dict[str, Any]],
) -> pd.DataFrame:
    rows = []
    for capability in capabilities:
        capability_name = capability.get("name")
        linked_services = [
            service for service in services
            if service.get("business_capability") == capability_name
        ]
        technologies = {
            tech
            for service in linked_services
            for tech in service.get("technologies", [])
        }
        rows.append(
            {
                "Capability": capability_name,
                "Business Unit": capability.get("business_unit"),
                "Business Owner": capability.get("owner"),
                "Criticality": capability.get("criticality"),
                "Applications": _count(capability.get("applications")),
                "Business Services": _count(capability.get("business_services")),
                "Technologies": len(technologies),
                "Monthly Cost": _money(capability.get("monthly_cost")),
                "Health": _percent(capability.get("health_score")),
                "Risk": _percent(capability.get("risk_score")),
                "Governance": _percent(capability.get("mapping_coverage")),
                "Status": capability.get("status"),
            }
        )
    return pd.DataFrame(rows)


def _mapping_rows(
    capabilities: list[dict[str, Any]],
    services: list[dict[str, Any]],
) -> pd.DataFrame:
    rows = []
    for capability in capabilities:
        capability_name = capability.get("name")
        linked_services = [
            service for service in services
            if service.get("business_capability") == capability_name
        ]
        if not linked_services:
            rows.append(
                {
                    "Capability": capability_name,
                    "Business Service": "Unmapped",
                    "Application": "Unmapped",
                    "Technology": "Unmapped",
                    "Business Unit": capability.get("business_unit"),
                    "Monthly Cost": _money(capability.get("monthly_cost")),
                }
            )
            continue

        for service in linked_services:
            applications = service.get("applications") or ["Unmapped Application"]
            technologies = service.get("technologies") or ["Unmapped Technology"]
            for application in applications:
                for technology in technologies:
                    rows.append(
                        {
                            "Capability": capability_name,
                            "Business Service": service.get("name"),
                            "Application": application,
                            "Technology": technology,
                            "Business Unit": capability.get("business_unit"),
                            "Monthly Cost": _money(service.get("monthly_cost")),
                        }
                    )
    return pd.DataFrame(rows)


def _spend_rows(capabilities: list[dict[str, Any]]) -> pd.DataFrame:
    rows = []
    for capability in capabilities:
        monthly = float(capability.get("monthly_cost") or 0)
        optimization = monthly * 0.08
        rows.append(
            {
                "Capability": capability.get("name"),
                "Business Unit": capability.get("business_unit"),
                "Monthly Spend": monthly,
                "Annual Spend": monthly * 12,
                "Forecast": monthly * 1.08,
                "Optimization Opportunity": optimization,
            }
        )
    return pd.DataFrame(rows)


def _risk_rows(health_rows: list[dict[str, Any]]) -> pd.DataFrame:
    rows = []
    for row in health_rows:
        monthly = float(row.get("Monthly Spend") or 0)
        risk_score = float(row.get("Risk Score") or 0)
        rows.append(
            {
                "Capability": row.get("Business Capability"),
                "Business Unit": row.get("Business Unit"),
                "Health": _percent(row.get("Health Score")),
                "Risk": _percent(risk_score),
                "Technical Debt": "Elevated" if risk_score >= 35 else "Managed",
                "Dependency Risk": "Elevated" if _count(row.get("Business Services")) == 0 else "Mapped",
                "Renewal Exposure": _money(monthly * 2),
                "Criticality": row.get("Criticality"),
            }
        )
    return pd.DataFrame(rows)


def _evidence_inventory(capabilities: list[dict[str, Any]]) -> pd.DataFrame:
    rows = []
    for capability in capabilities:
        rows.append(
            {
                "Capability ID": capability.get("id"),
                "Capability": capability.get("name"),
                "Business Unit ID": capability.get("business_unit_id"),
                "Business Unit": capability.get("business_unit"),
                "Owner": capability.get("owner"),
                "Criticality": capability.get("criticality"),
                "Applications": capability.get("applications"),
                "Business Services": capability.get("business_services"),
                "Monthly Cost": _money(capability.get("monthly_cost")),
                "Source": capability.get("source"),
                "Status": capability.get("status"),
            }
        )
    return pd.DataFrame(rows)


def _recommendation_rows(
    capabilities: list[dict[str, Any]],
    service_summary: dict[str, Any],
) -> pd.DataFrame:
    rows = []
    for capability in capabilities:
        health = float(capability.get("health_score") or 0)
        risk = float(capability.get("risk_score") or 0)
        monthly = float(capability.get("monthly_cost") or 0)
        rows.append(
            {
                "Capability": capability.get("name"),
                "Recommendation": (
                    "Review owner and mapping completeness"
                    if capability.get("owner") in {"Unassigned", "Unknown", ""}
                    else "Monitor capability operating posture"
                ),
                "Priority": "High" if risk >= 35 or health < 70 else "Normal",
                "Optimization Signal": _money(monthly * 0.08),
                "Automation Context": (
                    "Available"
                    if _count(service_summary.get("automation_candidates")) else "Monitor"
                ),
            }
        )
    return pd.DataFrame(rows)


def _executive_narrative(
    summary: dict[str, Any],
    service_summary: dict[str, Any],
    capabilities: list[dict[str, Any]],
) -> str:
    highest_spend = sorted(
        capabilities,
        key=lambda row: float(row.get("monthly_cost") or 0),
        reverse=True,
    )[:2]
    spend_names = ", ".join(row.get("name", "Unmapped") for row in highest_spend) or "No mapped capabilities"
    attention = [
        row for row in capabilities
        if float(row.get("risk_score") or 0) >= 35 or float(row.get("health_score") or 0) < 70
    ]
    annual_cost = float(summary.get("total_capability_spend") or 0) * 12
    savings = float(summary.get("optimization_opportunity") or 0) * 12
    sentences = [
        (
            f"The enterprise currently manages {summary.get('total_capabilities', 0)} business capability/capabilities "
            f"across {summary.get('business_units', 0)} business unit(s)."
        ),
        (
            f"{spend_names} represent the highest mapped technology investment, with annual capability spend of "
            f"{_money(annual_cost)}."
        ),
        (
            f"{len(attention)} capability/capabilities require executive attention based on health, mapping, or risk signals."
        ),
        (
            f"Optimization initiatives could reduce annual operating cost by approximately {_money(savings)}, "
            f"supported by {service_summary.get('recommendations', 0)} service-level recommendation signal(s)."
        ),
    ]
    return _escape_money(" ".join(sentences))


configure_page(
    page_title="Business Capabilities | Nexora",
    page_icon="BC",
)

init_session()
require_role(["executive", "cio", "finance", "super_admin"])

role = st.session_state.get("role", "cio")
render_enterprise_sidebar(
    role,
    page_paths=PAGE_PATHS,
    role_pages=ROLE_PAGES,
    active_page=PAGE_PATHS.get("Business Capabilities", "pages/business_capabilities.py"),
)

capability_dashboard = BusinessCapabilityService.get_capability_dashboard()
capability_summary = capability_dashboard["summary"]
capabilities = capability_dashboard["capabilities"]
health_rows = capability_dashboard["health"]
spend_rows = _spend_rows(capabilities)

service_dashboard = BusinessServiceService.get_service_dashboard()
service_summary = service_dashboard["summary"]
business_services = service_dashboard["business_services"]

unit_summary = BusinessUnitService.get_summary()

process_dashboard = BusinessProcessService.get_process_dashboard()
process_summary = process_dashboard["summary"]
processes = process_dashboard["business_processes"]

financial_summary = EnterpriseFinancialModel.get_enterprise_summary()


def render_business_capabilities_content() -> None:
    render_section(
        "Executive Summary",
        "Capability-level view of business architecture, service coverage, applications, technology, investment, health, and governance.",
        divider=False,
    )

    technologies = {
        tech
        for service in business_services
        for tech in service.get("technologies", [])
    }
    annual_spend = float(capability_summary.get("total_capability_spend") or 0) * 12

    kpi_cols = st.columns(4)
    with kpi_cols[0]:
        render_kpi_card(
            "Business Capabilities",
            f"{capability_summary['total_capabilities']:,}",
            "Capabilities represented in the enterprise model",
            icon="enterprise",
            status="info",
        )
    with kpi_cols[1]:
        render_metric_card(
            "Business Units Covered",
            f"{capability_summary['business_units']:,}",
            "Operating units with mapped capabilities",
            icon="governance",
            status="info",
        )
    with kpi_cols[2]:
        render_metric_card(
            "Business Services Covered",
            f"{capability_summary['business_services']:,}",
            "Services linked to business capabilities",
            icon="service",
            status="info",
        )
    with kpi_cols[3]:
        render_metric_card(
            "Applications",
            f"{capability_summary['applications']:,}",
            "Applications supporting capabilities",
            icon="application",
            status="info",
        )

    signal_cols = st.columns(4)
    with signal_cols[0]:
        render_metric_card(
            "Technology Platforms",
            f"{len(technologies):,}",
            "Technology platforms supporting services",
            icon="technology",
            status="info",
        )
    with signal_cols[1]:
        render_metric_card(
            "Annual Spend",
            _money(annual_spend),
            "Annualized mapped capability spend",
            icon="cost",
            status="healthy" if annual_spend else "warning",
        )
    with signal_cols[2]:
        render_health_card(
            "Health Score",
            _percent(capability_summary["average_health"]),
            "Average capability health",
            icon="health",
            status=_status_from_score(capability_summary["average_health"]),
        )
    with signal_cols[3]:
        render_health_card(
            "Governance Score",
            _percent(capability_summary["governance_score"]),
            "Health and mapping coverage blend",
            icon="governance",
            status=_status_from_score(capability_summary["governance_score"]),
        )

    _render_financial_reconciliation(financial_summary)

    render_section(
        "Executive Narrative",
        "Business interpretation of capability coverage, investment, risk, and optimization potential.",
    )
    render_insight_card(
        "Capability Portfolio Signal",
        description=_executive_narrative(capability_summary, service_summary, capabilities),
        status=_status_from_score(capability_summary["average_health"]),
    )

    render_section(
        "Capability Explorer",
        "Portfolio table with capability ownership, business unit coverage, applications, services, technology exposure, cost, health, and risk.",
    )
    portfolio_df = _capability_portfolio_rows(capabilities, business_services)
    _show_dataframe(
        portfolio_df,
        "No business capabilities are available yet.",
    )

    render_section(
        "Capability -> Service Mapping",
        "Traceability from capability into business service, application, and technology.",
    )
    mapping_df = _mapping_rows(capabilities, business_services)
    _show_dataframe(
        mapping_df,
        "No capability-to-service mappings are available yet.",
    )

    render_section(
        "Spend & Investment",
        "Monthly spend, annualized investment, forecast movement, and optimization opportunity by capability.",
    )
    spend_display = spend_rows.copy()
    if not spend_display.empty:
        for column in ["Monthly Spend", "Annual Spend", "Forecast", "Optimization Opportunity"]:
            spend_display[column] = spend_display[column].apply(_money)
    _show_dataframe(
        spend_display,
        "No capability spend data is available yet.",
    )
    if not spend_rows.empty:
        fig = px.bar(
            spend_rows,
            x="Capability",
            y="Monthly Spend",
            color="Business Unit",
            title="Monthly Spend by Capability",
        )
        st.plotly_chart(fig, use_container_width=True)

    render_section(
        "Health & Risk",
        "Capability-level health, risk, technical debt, dependency risk, and renewal exposure.",
    )
    risk_df = _risk_rows(health_rows)
    _show_dataframe(
        risk_df,
        "No capability health or risk data is available yet.",
    )
    if health_rows:
        chart_df = pd.DataFrame(health_rows)
        fig = px.scatter(
            chart_df,
            x="Risk Score",
            y="Health Score",
            size="Monthly Spend",
            color="Criticality",
            hover_name="Business Capability",
            title="Capability Health, Risk, and Investment",
            size_max=45,
        )
        st.plotly_chart(fig, use_container_width=True)

    render_section(
        "Detailed Evidence",
        "Standard evidence for source data, data coverage, relationship completeness, AI interpretation, and raw capability records.",
    )
    missing_owners = sum(
        1
        for row in [*capabilities, *business_services, *processes]
        if str(row.get("owner") or "").strip().lower() in {"", "unknown", "unassigned"}
    )
    missing_cost = sum(
        1
        for row in [*capabilities, *business_services, *processes]
        if float(row.get("monthly_cost") or 0) <= 0
    )
    missing_app_mapping = sum(1 for row in [*business_services, *processes] if not row.get("applications"))
    missing_tech_mapping = sum(1 for row in [*business_services, *processes] if not row.get("technologies"))
    source_df = pd.DataFrame(
        [
            {"Section": "Business Units", "Source": "business_units", "Status": "Derived through capability ownership"},
            {"Section": "Capabilities", "Source": "business_capabilities", "Status": "Live or Derived"},
            {"Section": "Services", "Source": "business_services", "Status": "Live or Derived"},
            {"Section": "Processes", "Source": "business_processes", "Status": "Derived for coverage context"},
            {"Section": "Applications", "Source": "application_registry", "Status": "Derived through service/process mappings"},
            {"Section": "Technologies", "Source": "technology_inventory", "Status": "Derived through service/process mappings"},
            {"Section": "Costs", "Source": "mart_application_spend", "Status": "Derived through capability cost allocation"},
            {"Section": "Relationships", "Source": "technology_relationships", "Status": "Derived through capability mappings"},
        ]
    )
    coverage_df = pd.DataFrame(
        [
            {"Indicator": "Mapping Coverage", "Value": _percent(capability_summary.get("mapping_coverage")), "Executive Meaning": "Capability coverage across applications and services"},
            {"Indicator": "Missing Owners", "Value": f"{missing_owners:,}", "Executive Meaning": "Business architecture records without accountable ownership"},
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
            {"Relationship": "Applications", "Count": capability_summary.get("applications", 0)},
            {"Relationship": "Technologies", "Count": len(technologies)},
            {"Relationship": "Relationships", "Count": len(mapping_df)},
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
            f"Capability evidence covers {capability_summary.get('total_capabilities', 0):,} capability record(s) and {len(mapping_df):,} service/application/technology mapping row(s). "
            f"{missing_owners:,} owner gap(s), {missing_cost:,} cost allocation gap(s), "
            f"{missing_app_mapping:,} application mapping gap(s), and {missing_tech_mapping:,} technology mapping gap(s) remain."
        ).replace("$", r"\$"),
        status=_status_from_score(capability_summary.get("governance_score")),
    )
    st.markdown("#### Raw Evidence")
    with st.expander("Business Units", expanded=False):
        _show_dataframe(pd.DataFrame([unit_summary]), "No business unit evidence is available yet.")
    with st.expander("Capabilities", expanded=True):
        _show_dataframe(_evidence_inventory(capabilities), "No capability inventory evidence is available yet.")
    with st.expander("Services", expanded=False):
        _show_dataframe(pd.DataFrame(business_services), "No service evidence is available yet.")
    with st.expander("Processes", expanded=False):
        _show_dataframe(pd.DataFrame(processes), "No process evidence is available yet.")
    with st.expander("Applications", expanded=False):
        _show_dataframe(mapping_df, "No application evidence is available yet.")
    with st.expander("Technologies", expanded=False):
        _show_dataframe(mapping_df, "No technology evidence is available yet.")
    with st.expander("Cost Allocation", expanded=False):
        _show_dataframe(spend_display, "No cost allocation evidence is available yet.")
    with st.expander("Relationships", expanded=False):
        _show_dataframe(mapping_df, "No relationship evidence is available yet.")
    with st.expander("Recommendations", expanded=False):
        _show_dataframe(_recommendation_rows(capabilities, service_summary), "No capability recommendation evidence is available yet.")


render_page(
    title="Business Capabilities",
    description="Capability-centered enterprise architecture view connecting business units, services, applications, technology, cost, health, risk, and governance.",
    breadcrumbs=["Home", "Enterprise Digital Twin", "Business Capabilities"],
    content=render_business_capabilities_content,
    status=_status_from_score(capability_summary["average_health"]),
    footer_version="E7.1.7",
)
