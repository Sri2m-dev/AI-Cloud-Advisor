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


def _status_from_score(score: float) -> str:
    if score >= 90:
        return "healthy"
    if score >= 70:
        return "warning"
    return "critical"


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
        "Canonical financial model status across business-unit allocation, mapped cost, and unallocated spend.",
    )
    cols = st.columns(3)
    status = summary.get("status", "Unmapped")
    with cols[0]:
        render_risk_card("Data Reconciliation Status", status, "Enterprise Financial Model", icon="governance", status=_financial_status_level(status))
    with cols[1]:
        render_metric_card("Allocation Coverage", _percent(summary.get("allocation_coverage")), "Canonical spend mapped to business units", icon="graph", status=_financial_status_level(status))
    with cols[2]:
        render_metric_card("Unallocated Spend", _money(summary.get("unallocated_spend")), "Spend not yet mapped to a canonical business path", icon="cost", status="warning" if summary.get("unallocated_spend") else "healthy")


def _format_business_units(rows: list[dict[str, Any]]) -> pd.DataFrame:
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    output = df.rename(
        columns={
            "Allocated Spend": "Mapped Monthly Spend",
            "Applications": "Applications",
            "Business Services": "Business Services",
        }
    )
    if "Mapped Monthly Spend" in output.columns:
        output["Mapped Monthly Spend"] = output["Mapped Monthly Spend"].apply(_money)
    columns = [
        "Business Unit",
        "Owner",
        "Executive Owner",
        "CIO",
        "Applications",
        "Business Services",
        "Mapped Monthly Spend",
        "Status",
        "Source",
    ]
    return output[[column for column in columns if column in output.columns]]


def _capability_rows_by_unit(
    capabilities_by_unit: dict[str, list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    rows = []
    for unit, capabilities in capabilities_by_unit.items():
        rows.append(
            {
                "Business Unit": unit,
                "Capabilities": len(capabilities),
                "Applications": sum(int(row.get("applications") or 0) for row in capabilities),
                "Business Services": sum(int(row.get("business_services") or 0) for row in capabilities),
                "Monthly Cost": sum(float(row.get("monthly_cost") or 0) for row in capabilities),
                "Average Health": (
                    sum(float(row.get("health_score") or 0) for row in capabilities) / max(len(capabilities), 1)
                ),
                "Mapping Coverage": (
                    sum(float(row.get("mapping_coverage") or 0) for row in capabilities) / max(len(capabilities), 1)
                ),
            }
        )
    return sorted(rows, key=lambda row: row["Monthly Cost"], reverse=True)


def _service_rows_by_unit(
    services_by_unit: dict[str, list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    rows = []
    for unit, services in services_by_unit.items():
        rows.append(
            {
                "Business Unit": unit,
                "Business Services": len(services),
                "Applications": sum(len(row.get("applications") or []) for row in services),
                "Technologies": sum(len(row.get("technologies") or []) for row in services),
                "Monthly Cost": sum(float(row.get("monthly_cost") or 0) for row in services),
                "Potential Savings": sum(float(row.get("potential_savings") or 0) for row in services),
                "Average Health": (
                    sum(float(row.get("health_score") or 0) for row in services) / max(len(services), 1)
                ),
                "Average Risk": (
                    sum(float(row.get("risk_score") or 0) for row in services) / max(len(services), 1)
                ),
            }
        )
    return sorted(rows, key=lambda row: row["Monthly Cost"], reverse=True)


def _format_money_columns(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    if df.empty:
        return df
    formatted = df.copy()
    for column in columns:
        if column in formatted.columns:
            formatted[column] = formatted[column].apply(_money)
    for column in ["Average Health", "Mapping Coverage", "Average Risk"]:
        if column in formatted.columns:
            formatted[column] = formatted[column].apply(_percent)
    return formatted


def _executive_narrative(
    unit_summary: dict[str, Any],
    capability_summary: dict[str, Any],
    service_summary: dict[str, Any],
) -> str:
    sentences = [
        (
            f"The enterprise model currently connects {unit_summary.get('business_units', 0)} business unit(s), "
            f"{capability_summary.get('total_capabilities', 0)} business capability/capabilities, and "
            f"{service_summary.get('business_services', 0)} business service(s)."
        ),
        (
            f"Business service mapping links {service_summary.get('applications', 0)} application(s) "
            f"to {service_summary.get('technologies', 0)} technology platform(s)."
        ),
        (
            f"Mapped monthly business service cost is {_money(service_summary.get('monthly_cost'))}, "
            f"with {_money(service_summary.get('potential_savings'))} in potential savings signals."
        ),
        (
            f"Business unit mapping coverage is {_percent(unit_summary.get('mapping_coverage'))}, "
            f"while average service health is {_percent(service_summary.get('average_health'))}."
        ),
    ]
    return " ".join(sentences).replace("$", r"\$")


configure_page(
    page_title="Business Units | Nexora",
    page_icon="BU",
)

init_session()
require_role(["executive", "cio", "finance", "super_admin"])

role = st.session_state.get("role", "cio")
render_enterprise_sidebar(
    role,
    page_paths=PAGE_PATHS,
    role_pages=ROLE_PAGES,
    active_page=PAGE_PATHS.get("Business Units", "pages/business_units.py"),
)

unit_dashboard = BusinessUnitService.get_dashboard()
unit_summary = unit_dashboard["summary"]
business_units = unit_dashboard["business_units"]

capability_summary = BusinessCapabilityService.get_capability_summary()
capabilities_by_unit = BusinessCapabilityService.get_capabilities_by_business_unit()
capability_by_unit_rows = _capability_rows_by_unit(capabilities_by_unit)

service_dashboard = BusinessServiceService.get_service_dashboard()
service_summary = service_dashboard["summary"]
services_by_unit = service_dashboard["services_by_business_unit"]
service_by_unit_rows = _service_rows_by_unit(services_by_unit)
relationship_paths = service_dashboard["relationship_paths"]

process_dashboard = BusinessProcessService.get_process_dashboard()
process_summary = process_dashboard["summary"]
processes = process_dashboard["business_processes"]

financial_summary = EnterpriseFinancialModel.get_enterprise_summary()


def render_business_units_content() -> None:
    render_section(
        "Enterprise Business Unit Summary",
        "Business-unit view of enterprise capabilities, services, applications, technology exposure, cost, and optimization signals.",
        divider=False,
    )

    kpi_cols = st.columns(5)
    with kpi_cols[0]:
        render_kpi_card(
            "Business Units",
            f"{unit_summary['business_units']:,}",
            "Enterprise operating units in scope",
            icon="enterprise",
            status="info",
        )
    with kpi_cols[1]:
        render_metric_card(
            "Capabilities",
            f"{capability_summary['total_capabilities']:,}",
            "Business capabilities mapped to units",
            icon="governance",
            status="info",
        )
    with kpi_cols[2]:
        render_metric_card(
            "Business Services",
            f"{service_summary['business_services']:,}",
            "Services connecting business to technology",
            icon="service",
            status="info",
        )
    with kpi_cols[3]:
        render_metric_card(
            "Mapped Monthly Cost",
            _money(service_summary["monthly_cost"]),
            "Cost attributed through service mappings",
            icon="cost",
            status="healthy" if service_summary["monthly_cost"] else "warning",
        )
    with kpi_cols[4]:
        render_health_card(
            "Service Health",
            _percent(service_summary["average_health"]),
            "Average health across mapped business services",
            icon="health",
            status=_status_from_score(float(service_summary["average_health"] or 0)),
        )

    signal_cols = st.columns(4)
    with signal_cols[0]:
        render_health_card(
            "Mapping Coverage",
            _percent(unit_summary["mapping_coverage"]),
            "Business units with application or service mappings",
            icon="graph",
            status=_status_from_score(float(unit_summary["mapping_coverage"] or 0)),
        )
    with signal_cols[1]:
        render_metric_card(
            "Applications",
            f"{service_summary['applications']:,}",
            "Applications connected to business services",
            icon="application",
            status="info",
        )
    with signal_cols[2]:
        render_metric_card(
            "Technologies",
            f"{service_summary['technologies']:,}",
            "Technology platforms connected to services",
            icon="technology",
            status="info",
        )
    with signal_cols[3]:
        render_risk_card(
            "Owner Gaps",
            f"{unit_summary['executive_owner_gaps']:,}",
            "Business units missing executive owner assignment",
            icon="risk",
            status="warning" if unit_summary["executive_owner_gaps"] else "healthy",
        )

    _render_financial_reconciliation(financial_summary)

    render_section(
        "Executive Business Narrative",
        "How the new enterprise business layer is connecting business ownership, service delivery, and technology cost.",
    )
    render_insight_card(
        "Enterprise Business Model Signal",
        description=_executive_narrative(unit_summary, capability_summary, service_summary),
        status=_status_from_score(float(service_summary["average_health"] or 0)),
    )

    render_section(
        "Business Unit Portfolio",
        "Owner, application, service, and mapped monthly spend view by business unit.",
    )
    _show_dataframe(
        _format_business_units(business_units),
        "No business unit data is available yet.",
    )

    render_section(
        "Business Capability Coverage",
        "Business capabilities grouped by business unit with service, application, cost, and mapping health.",
    )
    capability_df = _format_money_columns(
        pd.DataFrame(capability_by_unit_rows),
        ["Monthly Cost"],
    )
    _show_dataframe(
        capability_df,
        "No business capability coverage is available yet.",
    )
    if capability_by_unit_rows:
        chart_df = pd.DataFrame(capability_by_unit_rows)
        fig = px.bar(
            chart_df,
            x="Business Unit",
            y="Capabilities",
            color="Monthly Cost",
            title="Capabilities by Business Unit",
            color_continuous_scale="Blues",
        )
        st.plotly_chart(fig, use_container_width=True)

    render_section(
        "Business Service Rollup",
        "Business service mapping from unit and capability into applications, technologies, cost, savings, health, and risk.",
    )
    service_df = _format_money_columns(
        pd.DataFrame(service_by_unit_rows),
        ["Monthly Cost", "Potential Savings"],
    )
    _show_dataframe(
        service_df,
        "No business service rollup is available yet.",
    )

    render_section(
        "Enterprise Service Path",
        "Current Business Unit -> Capability -> Service -> Application -> Technology paths.",
    )
    path_df = pd.DataFrame(relationship_paths)
    _show_dataframe(
        path_df,
        "No enterprise service paths are available yet.",
    )

    render_section(
        "Detailed Evidence",
        "Standard evidence for source data, data coverage, relationship completeness, AI interpretation, and raw business unit records.",
    )
    flattened_capabilities = [
        {**capability, "business_unit": unit}
        for unit, capabilities in capabilities_by_unit.items()
        for capability in capabilities
    ]
    flattened_services = [
        service
        for services in services_by_unit.values()
        for service in services
    ]
    missing_owners = sum(
        1
        for row in [*business_units, *flattened_capabilities, *flattened_services, *processes]
        if str(row.get("Owner") or row.get("owner") or "").strip().lower() in {"", "unknown", "unassigned"}
    )
    missing_cost = sum(
        1
        for row in [*flattened_capabilities, *flattened_services, *processes]
        if float(row.get("monthly_cost") or row.get("Allocated Spend") or 0) <= 0
    )
    missing_app_mapping = sum(1 for row in [*flattened_services, *processes] if not row.get("applications"))
    missing_tech_mapping = sum(1 for row in [*flattened_services, *processes] if not row.get("technologies"))
    source_df = pd.DataFrame(
        [
            {"Section": "Business Units", "Source": "business_units", "Status": "Live or Derived"},
            {"Section": "Capabilities", "Source": "business_capabilities", "Status": "Live or Derived"},
            {"Section": "Services", "Source": "business_services", "Status": "Live or Derived"},
            {"Section": "Processes", "Source": "business_processes", "Status": "Derived for coverage context"},
            {"Section": "Applications", "Source": "application_registry", "Status": "Derived through service/process mappings"},
            {"Section": "Technologies", "Source": "technology_inventory", "Status": "Derived through service/process mappings"},
            {"Section": "Costs", "Source": "mart_application_spend", "Status": "Derived through service cost allocation"},
            {"Section": "Relationships", "Source": "technology_relationships", "Status": "Derived through service paths"},
        ]
    )
    coverage_df = pd.DataFrame(
        [
            {"Indicator": "Mapping Coverage", "Value": _percent(unit_summary.get("mapping_coverage")), "Executive Meaning": "Business units with application or service mappings"},
            {"Indicator": "Missing Owners", "Value": f"{missing_owners:,}", "Executive Meaning": "Business records without accountable ownership"},
            {"Indicator": "Missing Cost Allocation", "Value": f"{missing_cost:,}", "Executive Meaning": "Mapped records without monthly cost evidence"},
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
            {"Relationship": "Applications", "Count": service_summary.get("applications", 0)},
            {"Relationship": "Technologies", "Count": service_summary.get("technologies", 0)},
            {"Relationship": "Relationships", "Count": len(relationship_paths)},
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
            f"Business unit coverage is {_percent(unit_summary.get('mapping_coverage'))} with {len(relationship_paths):,} mapped relationship path(s). "
            f"{missing_owners:,} owner gap(s), {missing_cost:,} cost allocation gap(s), "
            f"{missing_app_mapping:,} application mapping gap(s), and {missing_tech_mapping:,} technology mapping gap(s) remain."
        ).replace("$", r"\$"),
        status=_status_from_score(float(unit_summary.get("mapping_coverage") or 0)),
    )
    st.markdown("#### Raw Evidence")
    with st.expander("Business Units", expanded=False):
        _show_dataframe(_format_business_units(business_units), "No business unit evidence is available yet.")
    with st.expander("Capabilities", expanded=False):
        _show_dataframe(pd.DataFrame(flattened_capabilities), "No capability evidence is available yet.")
    with st.expander("Services", expanded=False):
        _show_dataframe(pd.DataFrame(flattened_services), "No service evidence is available yet.")
    with st.expander("Processes", expanded=False):
        _show_dataframe(pd.DataFrame(processes), "No process evidence is available yet.")
    with st.expander("Applications", expanded=False):
        _show_dataframe(path_df, "No application evidence is available yet.")
    with st.expander("Technologies", expanded=False):
        _show_dataframe(path_df, "No technology evidence is available yet.")
    with st.expander("Cost Allocation", expanded=False):
        _show_dataframe(service_df, "No cost allocation evidence is available yet.")
    with st.expander("Relationships", expanded=False):
        _show_dataframe(path_df, "No relationship evidence is available yet.")
    with st.expander("Recommendations", expanded=False):
        _show_dataframe(
            pd.DataFrame(
                [
                    {"Recommendation": "Assign missing owners", "Count": missing_owners},
                    {"Recommendation": "Complete service cost allocation", "Count": missing_cost},
                    {"Recommendation": "Complete application mappings", "Count": missing_app_mapping},
                    {"Recommendation": "Complete technology mappings", "Count": missing_tech_mapping},
                ]
            ),
            "No recommendation evidence is available yet.",
        )


render_page(
    title="Business Units",
    description="Executive view of the enterprise business model foundation across units, capabilities, services, applications, and technologies.",
    breadcrumbs=["Home", "Enterprise Digital Twin", "Business Units"],
    content=render_business_units_content,
    status=_status_from_score(float(service_summary["average_health"] or 0)),
    footer_version="E7.1.4",
)
