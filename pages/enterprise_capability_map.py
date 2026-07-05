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
        "Canonical financial model status across capability-map cost, risk, automation, and unallocated spend.",
    )
    cols = st.columns(3)
    status = summary.get("status", "Unmapped")
    with cols[0]:
        render_risk_card("Data Reconciliation Status", status, "Enterprise Financial Model", icon="governance", status=_financial_status_level(status))
    with cols[1]:
        render_metric_card("Allocation Coverage", _percent(summary.get("allocation_coverage")), "Canonical spend mapped to the capability map", icon="graph", status=_financial_status_level(status))
    with cols[2]:
        render_metric_card("Unallocated Spend", _money(summary.get("unallocated_spend")), "Spend not yet mapped to a canonical business path", icon="cost", status="warning" if summary.get("unallocated_spend") else "healthy")


def _capability_rollups(
    capabilities: list[dict[str, Any]],
    services: list[dict[str, Any]],
    processes: list[dict[str, Any]],
) -> pd.DataFrame:
    rows = []
    for capability in capabilities:
        name = capability.get("name")
        linked_services = [row for row in services if row.get("business_capability") == name]
        linked_processes = [row for row in processes if row.get("business_capability") == name]
        technologies = {
            tech
            for service in linked_services
            for tech in service.get("technologies", [])
        } | {
            tech
            for process in linked_processes
            for tech in process.get("technologies", [])
        }
        monthly_cost = float(capability.get("monthly_cost") or 0)
        process_cost = sum(float(row.get("monthly_cost") or 0) for row in linked_processes)
        rows.append(
            {
                "Business Unit": capability.get("business_unit"),
                "Capability": name,
                "Owner": capability.get("owner"),
                "Criticality": capability.get("criticality"),
                "Business Services": len(linked_services) or int(capability.get("business_services") or 0),
                "Business Processes": len(linked_processes),
                "Applications": int(capability.get("applications") or 0),
                "Technologies": len(technologies),
                "Monthly Cost": monthly_cost or process_cost,
                "Annual Cost": (monthly_cost or process_cost) * 12,
                "Health Score": float(capability.get("health_score") or 0),
                "Risk Score": float(capability.get("risk_score") or 0),
                "Governance Score": float(capability.get("mapping_coverage") or 0),
                "Automation": sum(int(row.get("automation_opportunities") or 0) for row in linked_processes),
            }
        )
    return pd.DataFrame(rows)


def _coverage_rows(rollups: pd.DataFrame) -> pd.DataFrame:
    if rollups.empty:
        return rollups
    grouped = (
        rollups.groupby("Business Unit", as_index=False)
        .agg(
            Capabilities=("Capability", "nunique"),
            Services=("Business Services", "sum"),
            Processes=("Business Processes", "sum"),
            Applications=("Applications", "sum"),
            Technologies=("Technologies", "sum"),
            Monthly_Cost=("Monthly Cost", "sum"),
            Health=("Health Score", "mean"),
            Risk=("Risk Score", "mean"),
            Automation=("Automation", "sum"),
        )
        .rename(columns={"Monthly_Cost": "Monthly Cost"})
    )
    return grouped.sort_values("Monthly Cost", ascending=False)


def _coverage_paths(
    rollups: pd.DataFrame,
    services: list[dict[str, Any]],
    processes: list[dict[str, Any]],
) -> pd.DataFrame:
    rows = []
    if rollups.empty:
        return pd.DataFrame(rows)
    for _, capability in rollups.iterrows():
        capability_name = capability["Capability"]
        linked_services = [
            service for service in services
            if service.get("business_capability") == capability_name
        ] or [{"name": "Unmapped Service"}]
        for service in linked_services:
            linked_processes = [
                process for process in processes
                if process.get("business_capability") == capability_name
                and (
                    process.get("business_service") == service.get("name")
                    or service.get("name") == "Unmapped Service"
                )
            ] or [{"name": "Unmapped Process"}]
            for process in linked_processes:
                rows.append(
                    {
                        "Business Unit": capability["Business Unit"],
                        "Capability": capability_name,
                        "Business Service": service.get("name"),
                        "Business Process": process.get("name"),
                        "Health": _percent(capability["Health Score"]),
                        "Risk": _percent(capability["Risk Score"]),
                        "Monthly Cost": _money(capability["Monthly Cost"]),
                    }
                )
    return pd.DataFrame(rows)


def _display_rollups(rollups: pd.DataFrame) -> pd.DataFrame:
    if rollups.empty:
        return rollups
    output = rollups.copy()
    for column in ["Monthly Cost", "Annual Cost"]:
        output[column] = output[column].apply(_money)
    for column in ["Health Score", "Risk Score", "Governance Score"]:
        output[column] = output[column].apply(_percent)
    return output


def _display_coverage(coverage: pd.DataFrame) -> pd.DataFrame:
    if coverage.empty:
        return coverage
    output = coverage.copy()
    output["Monthly Cost"] = output["Monthly Cost"].apply(_money)
    for column in ["Health", "Risk"]:
        output[column] = output[column].apply(_percent)
    return output


def _executive_narrative(
    unit_summary: dict[str, Any],
    capability_summary: dict[str, Any],
    service_summary: dict[str, Any],
    process_summary: dict[str, Any],
    rollups: pd.DataFrame,
) -> str:
    highest = rollups.sort_values("Monthly Cost", ascending=False).head(2) if not rollups.empty else pd.DataFrame()
    highest_names = ", ".join(highest["Capability"].tolist()) if not highest.empty else "No mapped capabilities"
    elevated = int((rollups["Risk Score"] >= 35).sum()) if not rollups.empty else 0
    annual_cost = float(rollups["Annual Cost"].sum()) if not rollups.empty else 0.0
    sentences = [
        (
            f"The enterprise capability map connects {unit_summary.get('business_units', 0)} business unit(s), "
            f"{capability_summary.get('total_capabilities', 0)} capability/capabilities, "
            f"{service_summary.get('business_services', 0)} service(s), and "
            f"{process_summary.get('business_processes', 0)} process(es)."
        ),
        (
            f"{highest_names} represent the highest mapped investment areas, with annualized capability cost of "
            f"{_money(annual_cost)}."
        ),
        (
            f"{elevated} capability/capabilities show elevated risk signals, while "
            f"{process_summary.get('automation_opportunities', 0)} automation opportunity signal(s) are linked through process coverage."
        ),
    ]
    return _escape_money(" ".join(sentences))


configure_page(
    page_title="Enterprise Capability Map | Nexora",
    page_icon="ECM",
)

init_session()
require_role(["executive", "cio", "finance", "super_admin"])

role = st.session_state.get("role", "cio")
render_enterprise_sidebar(
    role,
    page_paths=PAGE_PATHS,
    role_pages=ROLE_PAGES,
    active_page=PAGE_PATHS.get("Enterprise Capability Map", "pages/enterprise_capability_map.py"),
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

rollups = _capability_rollups(capabilities, services, processes)
coverage = _coverage_rows(rollups)
paths = _coverage_paths(rollups, services, processes)


def render_enterprise_capability_map_content() -> None:
    render_section(
        "Enterprise Capability Summary",
        "Business-unit capability coverage across services, processes, applications, technologies, cost, health, risk, and automation.",
        divider=False,
    )

    kpi_cols = st.columns(4)
    with kpi_cols[0]:
        render_kpi_card(
            "Business Units",
            f"{unit_summary['business_units']:,}",
            "Operating units represented in the map",
            icon="enterprise",
            status="info",
        )
    with kpi_cols[1]:
        render_metric_card(
            "Capabilities",
            f"{capability_summary['total_capabilities']:,}",
            "Business capabilities mapped",
            icon="governance",
            status="info",
        )
    with kpi_cols[2]:
        render_metric_card(
            "Services",
            f"{service_summary['business_services']:,}",
            "Business services linked to capabilities",
            icon="service",
            status="info",
        )
    with kpi_cols[3]:
        render_metric_card(
            "Processes",
            f"{process_summary['business_processes']:,}",
            "Operational processes linked to services",
            icon="workflow",
            status="info",
        )

    signal_cols = st.columns(4)
    with signal_cols[0]:
        render_metric_card(
            "Annual Cost",
            _money(float(rollups["Annual Cost"].sum()) if not rollups.empty else 0),
            "Annualized capability investment",
            icon="cost",
            status="healthy" if not rollups.empty else "warning",
        )
    with signal_cols[1]:
        render_health_card(
            "Health",
            _percent(capability_summary["average_health"]),
            "Average capability health",
            icon="health",
            status=_status_from_score(capability_summary["average_health"]),
        )
    with signal_cols[2]:
        render_risk_card(
            "Risk",
            _percent(float(rollups["Risk Score"].mean()) if not rollups.empty else 0),
            "Average capability risk",
            icon="risk",
            status=_risk_status(float(rollups["Risk Score"].mean()) if not rollups.empty else 0),
        )
    with signal_cols[3]:
        render_metric_card(
            "Automation",
            f"{process_summary['automation_opportunities']:,}",
            "Automation opportunities linked through process coverage",
            icon="automation",
            status="info" if process_summary["automation_opportunities"] else "healthy",
        )

    _render_financial_reconciliation(financial_summary)

    render_section(
        "Executive Capability Narrative",
        "Executive interpretation of capability coverage, investment, risk, and automation signals.",
    )
    render_insight_card(
        "Enterprise Capability Map Signal",
        description=_executive_narrative(unit_summary, capability_summary, service_summary, process_summary, rollups),
        status=_status_from_score(capability_summary["average_health"]),
    )

    render_section(
        "Capability Heatmap",
        "Capability health and risk by business unit with cost and automation overlays.",
    )
    _show_dataframe(
        _display_rollups(rollups),
        "No capability rollup data is available yet.",
    )
    if not rollups.empty:
        fig = px.density_heatmap(
            rollups,
            x="Capability",
            y="Business Unit",
            z="Health Score",
            color_continuous_scale="RdYlGn",
            title="Capability Health Heatmap",
        )
        st.plotly_chart(fig, use_container_width=True)

    render_section(
        "Business Unit -> Capability -> Service -> Process Coverage",
        "Traceability coverage from business ownership into service and process execution.",
    )
    _show_dataframe(
        _display_coverage(coverage),
        "No business unit capability coverage is available yet.",
    )
    _show_dataframe(
        paths,
        "No capability service/process paths are available yet.",
    )

    render_section(
        "Cost, Health, Risk, and Automation Rollups",
        "Portfolio-level capability rollup for investment, health, risk, governance, and automation planning.",
    )
    if not rollups.empty:
        fig = px.scatter(
            rollups,
            x="Risk Score",
            y="Health Score",
            size="Monthly Cost",
            color="Business Unit",
            hover_name="Capability",
            title="Capability Cost, Health, and Risk",
            size_max=48,
        )
        st.plotly_chart(fig, use_container_width=True)

        fig = px.bar(
            rollups.sort_values("Monthly Cost", ascending=False),
            x="Capability",
            y="Monthly Cost",
            color="Automation",
            title="Capability Monthly Cost and Automation Signals",
        )
        st.plotly_chart(fig, use_container_width=True)

    render_section(
        "Detailed Evidence",
        "Standard evidence for source data, data coverage, relationship completeness, AI interpretation, and raw capability map records.",
    )
    business_units_df = pd.DataFrame(unit_dashboard.get("business_units", []))
    process_df = pd.DataFrame(processes)
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
    governance = float(capability_summary.get("governance_score") or capability_summary.get("mapping_coverage") or 0)
    source_df = pd.DataFrame(
        [
            {"Section": "Business Units", "Source": "business_units", "Status": "Live or Derived"},
            {"Section": "Capabilities", "Source": "business_capabilities", "Status": "Live or Derived"},
            {"Section": "Services", "Source": "business_services", "Status": "Live or Derived"},
            {"Section": "Processes", "Source": "business_processes", "Status": "Live or Derived"},
            {"Section": "Applications", "Source": "application_registry", "Status": "Derived through capability paths"},
            {"Section": "Technologies", "Source": "technology_inventory", "Status": "Derived through capability paths"},
            {"Section": "Costs", "Source": "mart_application_spend", "Status": "Derived through capability cost allocation"},
            {"Section": "Relationships", "Source": "technology_relationships", "Status": "Derived through coverage paths"},
        ]
    )
    coverage_df = pd.DataFrame(
        [
            {"Indicator": "Mapping Coverage", "Value": _percent(governance), "Executive Meaning": "Capability coverage across business, service, and process layers"},
            {"Indicator": "Missing Owners", "Value": f"{missing_owners:,}", "Executive Meaning": "Architecture records without accountable ownership"},
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
            {"Relationship": "Applications", "Count": process_summary.get("applications", 0)},
            {"Relationship": "Technologies", "Count": process_summary.get("technologies", 0)},
            {"Relationship": "Relationships", "Count": len(paths)},
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
            f"The enterprise capability map includes {capability_summary.get('total_capabilities', 0):,} capability record(s) and {len(paths):,} coverage path(s). "
            f"{missing_owners:,} owner gap(s), {missing_cost:,} cost allocation gap(s), "
            f"{missing_app_mapping:,} application mapping gap(s), and {missing_tech_mapping:,} technology mapping gap(s) remain."
        ).replace("$", r"\$"),
        status=_status_from_score(governance),
    )
    st.markdown("#### Raw Evidence")
    with st.expander("Business Units", expanded=False):
        _show_dataframe(business_units_df, "No business unit evidence is available yet.")
    with st.expander("Capabilities", expanded=True):
        _show_dataframe(_display_rollups(rollups), "No capability evidence is available yet.")
    with st.expander("Services", expanded=False):
        _show_dataframe(pd.DataFrame(services), "No service evidence is available yet.")
    with st.expander("Processes", expanded=False):
        _show_dataframe(process_df, "No process coverage evidence is available yet.")
    with st.expander("Applications", expanded=False):
        _show_dataframe(paths, "No application evidence is available yet.")
    with st.expander("Technologies", expanded=False):
        _show_dataframe(paths, "No technology evidence is available yet.")
    with st.expander("Cost Allocation", expanded=False):
        _show_dataframe(_display_coverage(coverage), "No cost allocation evidence is available yet.")
    with st.expander("Relationships", expanded=False):
        _show_dataframe(paths, "No relationship evidence is available yet.")
    with st.expander("Recommendations", expanded=False):
        _show_dataframe(
            pd.DataFrame(
                [
                    {"Recommendation": "Assign missing owners", "Count": missing_owners},
                    {"Recommendation": "Complete cost allocation", "Count": missing_cost},
                    {"Recommendation": "Complete application mappings", "Count": missing_app_mapping},
                    {"Recommendation": "Complete technology mappings", "Count": missing_tech_mapping},
                ]
            ),
            "No recommendation evidence is available yet.",
        )


render_page(
    title="Enterprise Capability Map",
    description="Capability map connecting business units, capabilities, services, processes, applications, technology, cost, health, risk, and automation.",
    breadcrumbs=["Home", "Enterprise Digital Twin", "Enterprise Capability Map"],
    content=render_enterprise_capability_map_content,
    status=_status_from_score(capability_summary["average_health"]),
    footer_version="E7.1.9",
)
