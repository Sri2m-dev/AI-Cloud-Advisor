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


def _list_text(values: list[Any] | tuple[Any, ...] | None) -> str:
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
        "Canonical financial model status across service cost, forecast, savings, and unallocated spend.",
    )
    cols = st.columns(3)
    status = summary.get("status", "Unmapped")
    with cols[0]:
        render_risk_card("Data Reconciliation Status", status, "Enterprise Financial Model", icon="governance", status=_financial_status_level(status))
    with cols[1]:
        render_metric_card("Allocation Coverage", _percent(summary.get("allocation_coverage")), "Canonical spend mapped to business services", icon="graph", status=_financial_status_level(status))
    with cols[2]:
        render_metric_card("Unallocated Spend", _money(summary.get("unallocated_spend")), "Spend not yet mapped to a canonical business path", icon="cost", status="warning" if summary.get("unallocated_spend") else "healthy")


def _selected_service(services: list[dict[str, Any]]) -> dict[str, Any]:
    if not services:
        return {}
    service_names = [service["name"] for service in services]
    selected_name = st.selectbox("Business Service", service_names)
    return next(
        (service for service in services if service["name"] == selected_name),
        services[0],
    )


def _summary_narrative(
    service_summary: dict[str, Any],
    capability_summary: dict[str, Any],
    unit_summary: dict[str, Any],
) -> str:
    sentences = [
        (
            f"The business service model currently connects {service_summary.get('business_services', 0)} "
            f"service(s), {capability_summary.get('total_capabilities', 0)} capability/capabilities, "
            f"and {unit_summary.get('business_units', 0)} business unit(s)."
        ),
        (
            f"These services map {service_summary.get('applications', 0)} application(s) to "
            f"{service_summary.get('technologies', 0)} technology platform(s), creating the business "
            "context needed for impact analysis and digital twin navigation."
        ),
        (
            f"Mapped monthly service cost is {_money(service_summary.get('monthly_cost'))}, "
            f"with {_money(service_summary.get('potential_savings'))} in optimization signals."
        ),
        (
            f"Average service health is {_percent(service_summary.get('average_health'))} and "
            f"average service risk is {_percent(service_summary.get('average_risk'))}."
        ),
    ]
    return _escape_money(" ".join(sentences))


def _service_table_rows(services: list[dict[str, Any]]) -> pd.DataFrame:
    rows = []
    for service in services:
        rows.append(
            {
                "Business Service": service.get("name"),
                "Business Unit": service.get("business_unit"),
                "Capability": service.get("business_capability"),
                "Owner": service.get("owner"),
                "Tier": service.get("tier"),
                "SLA": service.get("sla"),
                "Applications": len(service.get("applications") or []),
                "Technologies": len(service.get("technologies") or []),
                "Monthly Cost": _money(service.get("monthly_cost")),
                "Forecast Cost": _money(service.get("forecast_cost")),
                "Potential Savings": _money(service.get("potential_savings")),
                "Health": _percent(service.get("health_score")),
                "Risk": _percent(service.get("risk_score")),
                "Governance": _percent(service.get("governance_score")),
                "Status": service.get("status"),
            }
        )
    return pd.DataFrame(rows)


def _application_mapping(service: dict[str, Any]) -> pd.DataFrame:
    rows = [
        {
            "Business Service": service.get("name"),
            "Application": app,
            "Business Unit": service.get("business_unit"),
            "Capability": service.get("business_capability"),
            "Owner": service.get("owner"),
            "Tier": service.get("tier"),
            "SLA": service.get("sla"),
        }
        for app in service.get("applications") or []
    ]
    return pd.DataFrame(rows)


def _technology_mapping(service: dict[str, Any]) -> pd.DataFrame:
    technologies = service.get("technologies") or []
    vendors = service.get("vendors") or []
    rows = []
    for index, technology in enumerate(technologies):
        rows.append(
            {
                "Business Service": service.get("name"),
                "Technology": technology,
                "Vendor": vendors[index] if index < len(vendors) else _list_text(vendors),
                "Cloud Resources": _count(service.get("cloud_resources")),
                "Health": _percent(service.get("health_score")),
                "Risk": _percent(service.get("risk_score")),
            }
        )
    return pd.DataFrame(rows)


def _cost_forecast_rows(service: dict[str, Any]) -> pd.DataFrame:
    monthly = float(service.get("monthly_cost") or 0)
    forecast = float(service.get("forecast_cost") or 0)
    savings = float(service.get("potential_savings") or 0)
    return pd.DataFrame(
        [
            {
                "Metric": "Current Monthly Cost",
                "Value": _money(monthly),
                "Signal": "Mapped business service run cost",
            },
            {
                "Metric": "Forecast Monthly Cost",
                "Value": _money(forecast),
                "Signal": "Projected service run cost from current signals",
            },
            {
                "Metric": "Potential Savings",
                "Value": _money(savings),
                "Signal": "Optimization opportunity associated with this service",
            },
            {
                "Metric": "Forecast Variance",
                "Value": _money(forecast - monthly),
                "Signal": "Expected movement between current and forecast cost",
            },
        ]
    )


def _health_risk_rows(service: dict[str, Any]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "Dimension": "Health",
                "Score": _percent(service.get("health_score")),
                "Interpretation": "Operational and technology posture for this service",
            },
            {
                "Dimension": "Risk",
                "Score": _percent(service.get("risk_score")),
                "Interpretation": "Business and technology risk associated with the service",
            },
            {
                "Dimension": "Governance",
                "Score": _percent(service.get("governance_score")),
                "Interpretation": "Owner, policy, and control mapping completeness",
            },
            {
                "Dimension": "Active Incidents",
                "Score": f"{_count(service.get('active_incidents')):,}",
                "Interpretation": "Open operational incidents linked to this service",
            },
        ]
    )


def _recommendation_rows(service: dict[str, Any]) -> pd.DataFrame:
    recommendations = _count(service.get("recommendations"))
    automation = _count(service.get("automation_candidates"))
    return pd.DataFrame(
        [
            {
                "Signal": "Recommendations",
                "Count": f"{recommendations:,}",
                "Business Meaning": "AI or rule-based actions available for review",
            },
            {
                "Signal": "Automation Candidates",
                "Count": f"{automation:,}",
                "Business Meaning": "Actions that may be eligible for workflow automation",
            },
            {
                "Signal": "Potential Savings",
                "Count": _money(service.get("potential_savings")),
                "Business Meaning": "Estimated financial upside linked to recommendations",
            },
            {
                "Signal": "Suggested Action",
                "Count": "Review" if recommendations or automation else "Monitor",
                "Business Meaning": "Recommended operating posture for this service",
            },
        ]
    )


def _path_rows(
    service: dict[str, Any],
    relationship_paths: list[dict[str, Any]],
) -> pd.DataFrame:
    service_name = service.get("name")
    rows = [
        row for row in relationship_paths
        if row.get("Business Service") == service_name or row.get("Service") == service_name
    ]
    if rows:
        return pd.DataFrame(rows)
    applications = service.get("applications") or ["Unmapped Application"]
    technologies = service.get("technologies") or ["Unmapped Technology"]
    return pd.DataFrame(
        [
            {
                "Business Unit": service.get("business_unit"),
                "Capability": service.get("business_capability"),
                "Business Service": service_name,
                "Application": app,
                "Technology": technology,
                "Cost": _money(service.get("monthly_cost")),
                "Risk": _percent(service.get("risk_score")),
            }
            for app in applications
            for technology in technologies
        ]
    )


def _evidence_rows(services: list[dict[str, Any]]) -> pd.DataFrame:
    rows = []
    for service in services:
        rows.append(
            {
                "Service ID": service.get("id"),
                "Business Service": service.get("name"),
                "Service Code": service.get("service_code") or "Derived",
                "Business Unit": service.get("business_unit"),
                "Capability": service.get("business_capability"),
                "Applications": _list_text(service.get("applications")),
                "Technologies": _list_text(service.get("technologies")),
                "Vendors": _list_text(service.get("vendors")),
                "Source": service.get("source"),
                "Last Updated": service.get("last_updated"),
            }
        )
    return pd.DataFrame(rows)


configure_page(
    page_title="Business Services | Nexora",
    page_icon="BS",
)

init_session()
require_role(["executive", "cio", "finance", "super_admin", "technical"])

role = st.session_state.get("role", "cio")
render_enterprise_sidebar(
    role,
    page_paths=PAGE_PATHS,
    role_pages=ROLE_PAGES,
    active_page=PAGE_PATHS.get("Business Services", "pages/business_services.py"),
)

service_dashboard = BusinessServiceService.get_service_dashboard()
service_summary = service_dashboard["summary"]
business_services = service_dashboard["business_services"]
services_by_unit = service_dashboard["services_by_business_unit"]
services_by_capability = service_dashboard["services_by_capability"]
relationship_paths = service_dashboard["relationship_paths"]

capability_summary = BusinessCapabilityService.get_capability_summary()
unit_summary = BusinessUnitService.get_summary()
business_units = BusinessUnitService.get_business_units()

process_dashboard = BusinessProcessService.get_process_dashboard()
process_summary = process_dashboard["summary"]
processes = process_dashboard["business_processes"]

financial_summary = EnterpriseFinancialModel.get_enterprise_summary()


def render_business_services_content() -> None:
    render_section(
        "Can this service safely support the business?",
        "Start with business impact, ownership, cost, health, and the action required.",
        divider=False,
    )
    selected_service = _selected_service(business_services)
    if selected_service:
        health = selected_service.get("health_score")
        cost = selected_service.get("monthly_cost")
        risk = selected_service.get("risk_score")
        applications = selected_service.get("applications") or []
        technologies = selected_service.get("technologies") or []
        recommendations = _count(selected_service.get("recommendations"))
        needs_action = recommendations > 0 or (risk is not None and float(risk) >= 35)
        brief = st.columns([1.35, 1, 1, 1, 1, 1.15])
        brief[0].metric("Business service", selected_service.get("name") or "UNKNOWN")
        brief[1].metric("Health", _percent(health) if health is not None else "UNKNOWN")
        brief[2].metric("Monthly cost", _money(cost) if cost is not None else "UNKNOWN")
        brief[3].metric("Owner", selected_service.get("owner") or "UNMAPPED")
        brief[4].metric("Dependencies", len(applications) + len(technologies))
        brief[5].metric("Required action", "Review" if needs_action else "Monitor")
        st.markdown(
            f"**Business impact:** {selected_service.get('tier') or 'Unclassified'} service · "
            f"SLA {selected_service.get('sla') or 'NOT ASSESSED'} · "
            f"{len(applications)} application(s) and {len(technologies)} technology "
            "dependency/dependencies."
        )
        st.info(
            "Recommended action — Review linked recommendations and impact evidence."
            if needs_action
            else "Recommended action — Continue monitoring; no evidenced intervention is due."
        )

        if not st.toggle(
            "Show operational mappings and certification detail",
            value=False,
            help=(
                "Reveal application, technology, dependency, financial reconciliation, "
                "and evidence views."
            ),
        ):
            st.caption(
                "Technical mappings and evidence are intentionally hidden in the executive view."
            )
            return

    with st.expander("Enterprise service portfolio and certification detail"):
        st.write(
            f"{service_summary['business_services']:,} services connect "
            f"{service_summary['applications']:,} applications and "
            f"{service_summary['technologies']:,} technologies."
        )

    render_section(
        "Business Service Summary",
        "Service-centered view of business capability, application, technology, cost, health, risk, governance, and automation signals.",
        divider=False,
    )

    kpi_cols = st.columns(5)
    with kpi_cols[0]:
        render_kpi_card(
            "Business Services",
            f"{service_summary['business_services']:,}",
            "Services connecting business outcomes to technology",
            icon="service",
            status="info",
        )
    with kpi_cols[1]:
        render_metric_card(
            "Applications",
            f"{service_summary['applications']:,}",
            "Applications mapped to business services",
            icon="application",
            status="info",
        )
    with kpi_cols[2]:
        render_metric_card(
            "Technologies",
            f"{service_summary['technologies']:,}",
            "Technology platforms supporting services",
            icon="technology",
            status="info",
        )
    with kpi_cols[3]:
        render_metric_card(
            "Monthly Service Cost",
            _money(service_summary["monthly_cost"]),
            "Mapped monthly service run cost",
            icon="cost",
            status="healthy" if service_summary["monthly_cost"] else "warning",
        )
    with kpi_cols[4]:
        render_health_card(
            "Average Service Health",
            _percent(service_summary["average_health"]),
            "Average health across mapped services",
            icon="health",
            status=_status_from_score(service_summary["average_health"]),
        )

    signal_cols = st.columns(4)
    with signal_cols[0]:
        render_metric_card(
            "Business Units",
            f"{len(business_units):,}",
            "Operating units connected to the service model",
            icon="enterprise",
            status="info",
        )
    with signal_cols[1]:
        render_metric_card(
            "Capabilities",
            f"{capability_summary['total_capabilities']:,}",
            "Capabilities represented by mapped services",
            icon="governance",
            status="info",
        )
    with signal_cols[2]:
        render_risk_card(
            "Average Service Risk",
            _percent(service_summary["average_risk"]),
            "Average risk across mapped services",
            icon="risk",
            status=_risk_status(service_summary["average_risk"]),
        )
    with signal_cols[3]:
        render_metric_card(
            "Automation Candidates",
            f"{service_summary['automation_candidates']:,}",
            "Recommended actions eligible for automation review",
            icon="automation",
            status="info" if service_summary["automation_candidates"] else "healthy",
        )

    _render_financial_reconciliation(financial_summary)

    render_section(
        "Executive Service Narrative",
        "Business interpretation of the current service model coverage and operating signal.",
    )
    render_insight_card(
        "Enterprise Business Service Signal",
        description=_summary_narrative(service_summary, capability_summary, unit_summary),
        status=_status_from_score(service_summary["average_health"]),
    )

    render_section(
        "Service Explorer",
        "Select a business service to inspect ownership, delivery mappings, cost posture, health, risk, recommendations, and evidence.",
    )
    if not selected_service:
        st.info("No business services are available yet.")
        return

    hero_cols = st.columns([1.4, 1, 1, 1])
    with hero_cols[0]:
        render_kpi_card(
            selected_service["name"],
            selected_service.get("business_capability") or "Unmapped Capability",
            f"{selected_service.get('business_unit')} | Owner: {selected_service.get('owner')}",
            icon="service",
            status=_status_from_score(selected_service.get("health_score")),
        )
    with hero_cols[1]:
        render_metric_card(
            "Tier / SLA",
            selected_service.get("tier") or "Unassigned",
            f"SLA {selected_service.get('sla') or 'Not set'}",
            icon="governance",
            status="info",
        )
    with hero_cols[2]:
        render_metric_card(
            "Monthly Cost",
            _money(selected_service.get("monthly_cost")),
            f"Forecast {_money(selected_service.get('forecast_cost'))}",
            icon="cost",
            status="healthy" if selected_service.get("monthly_cost") else "warning",
        )
    with hero_cols[3]:
        render_risk_card(
            "Service Risk",
            _percent(selected_service.get("risk_score")),
            f"Status: {selected_service.get('status')}",
            icon="risk",
            status=_risk_status(selected_service.get("risk_score")),
        )

    detail_cols = st.columns(4)
    with detail_cols[0]:
        render_metric_card(
            "Applications",
            f"{len(selected_service.get('applications') or []):,}",
            _list_text(selected_service.get("applications")),
            icon="application",
            status="info",
        )
    with detail_cols[1]:
        render_metric_card(
            "Technologies",
            f"{len(selected_service.get('technologies') or []):,}",
            _list_text(selected_service.get("technologies")),
            icon="technology",
            status="info",
        )
    with detail_cols[2]:
        render_health_card(
            "Governance Score",
            _percent(selected_service.get("governance_score")),
            "Ownership and control completeness",
            icon="governance",
            status=_status_from_score(selected_service.get("governance_score")),
        )
    with detail_cols[3]:
        render_metric_card(
            "Potential Savings",
            _money(selected_service.get("potential_savings")),
            f"{_count(selected_service.get('recommendations')):,} recommendations",
            icon="optimization",
            status="warning" if selected_service.get("potential_savings") else "healthy",
        )

    with st.expander("Applications, technologies, and service mappings"):
        st.markdown("#### Application mapping")
        _show_dataframe(
            _application_mapping(selected_service),
            "No application mappings are available for this service yet.",
        )
        st.markdown("#### Technology mapping")
        _show_dataframe(
            _technology_mapping(selected_service),
            "No technology mappings are available for this service yet.",
        )

    render_section(
        "Cost & Forecast",
        "Current service run cost, forecast movement, and optimization opportunity.",
    )
    _show_dataframe(
        _cost_forecast_rows(selected_service),
        "No service cost or forecast data is available yet.",
    )

    render_section(
        "Health / Risk / Governance",
        "Operating posture for service reliability, business risk, and governance completeness.",
    )
    _show_dataframe(
        _health_risk_rows(selected_service),
        "No health, risk, or governance signals are available yet.",
    )

    render_section(
        "Recommendations & Automation",
        "AI and rule-based operating signals linked to the selected business service.",
    )
    _show_dataframe(
        _recommendation_rows(selected_service),
        "No recommendations or automation candidates are available yet.",
    )

    path_df = _path_rows(selected_service, relationship_paths)
    with st.expander("Dependency and Digital Twin path"):
        st.caption(
            "Business Unit → Capability → Service → Application → Technology impact path."
        )
        _show_dataframe(
            path_df,
            "No service dependency path is available yet.",
        )

    render_section(
        "Business Service Portfolio",
        "All mapped services with ownership, cost, forecast, health, risk, and governance signals.",
    )
    portfolio_df = _service_table_rows(business_services)
    with st.expander("Open complete service portfolio"):
        _show_dataframe(
            portfolio_df,
            "No business service portfolio is available yet.",
        )

    if business_services:
        chart_df = pd.DataFrame(
            [
                {
                    "Business Service": service.get("name"),
                    "Monthly Cost": float(service.get("monthly_cost") or 0),
                    "Health Score": float(service.get("health_score") or 0),
                    "Risk Score": float(service.get("risk_score") or 0),
                    "Business Unit": service.get("business_unit"),
                }
                for service in business_services
            ]
        )
        fig = px.scatter(
            chart_df,
            x="Risk Score",
            y="Health Score",
            size="Monthly Cost",
            color="Business Unit",
            hover_name="Business Service",
            title="Business Service Health, Risk, and Cost",
            size_max=45,
        )
        st.plotly_chart(fig, use_container_width=True)

    render_section(
        "Detailed Evidence",
        "Standard evidence for source data, data coverage, relationship completeness, AI interpretation, and raw service records.",
    )
    if not st.checkbox("Show detailed certification evidence", value=False):
        st.caption(
            "Source data, coverage, relationships, reconciliation, AI interpretation, "
            "and raw records are hidden by default for executive users."
        )
        return
    missing_owners = sum(
        1
        for row in [*business_units, *business_services, *processes]
        if str(row.get("Owner") or row.get("owner") or "").strip().lower() in {"", "unknown", "unassigned"}
    )
    missing_cost = sum(
        1
        for row in [*business_services, *processes]
        if float(row.get("monthly_cost") or row.get("Allocated Spend") or 0) <= 0
    )
    missing_app_mapping = sum(1 for row in [*business_services, *processes] if not row.get("applications"))
    missing_tech_mapping = sum(1 for row in [*business_services, *processes] if not row.get("technologies"))
    source_df = pd.DataFrame(
        [
            {"Section": "Business Units", "Source": "business_units", "Status": "Live or Derived"},
            {"Section": "Capabilities", "Source": "business_capabilities", "Status": "Derived through service capability mapping"},
            {"Section": "Services", "Source": "business_services", "Status": "Live or Derived"},
            {"Section": "Processes", "Source": "business_processes", "Status": "Derived for coverage context"},
            {"Section": "Applications", "Source": "application_registry", "Status": "Derived through service mappings"},
            {"Section": "Technologies", "Source": "technology_inventory", "Status": "Derived through service mappings"},
            {"Section": "Costs", "Source": "mart_application_spend", "Status": "Derived through service cost allocation"},
            {"Section": "Relationships", "Source": "technology_relationships", "Status": "Derived through service dependency paths"},
        ]
    )
    coverage_df = pd.DataFrame(
        [
            {"Indicator": "Mapping Coverage", "Value": _percent(service_summary.get("governance_score")), "Executive Meaning": "Service ownership and mapping completeness"},
            {"Indicator": "Missing Owners", "Value": f"{missing_owners:,}", "Executive Meaning": "Business service records without accountable ownership"},
            {"Indicator": "Missing Cost Allocation", "Value": f"{missing_cost:,}", "Executive Meaning": "Services or processes without mapped monthly cost"},
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
            f"Business service evidence contains {service_summary.get('business_services', 0):,} service(s), "
            f"{service_summary.get('applications', 0):,} application mapping(s), and {service_summary.get('technologies', 0):,} technology mapping(s). "
            f"{missing_owners:,} owner gap(s), {missing_cost:,} cost allocation gap(s), "
            f"{missing_app_mapping:,} application mapping gap(s), and {missing_tech_mapping:,} technology mapping gap(s) remain."
        ).replace("$", r"\$"),
        status=_status_from_score(service_summary.get("average_health")),
    )
    st.markdown("#### Raw Evidence")
    with st.expander("Business Units", expanded=False):
        _show_dataframe(pd.DataFrame(business_units), "No business unit evidence is available yet.")
    with st.expander("Capabilities", expanded=False):
        _show_dataframe(pd.DataFrame([capability_summary]), "No capability evidence is available yet.")
    with st.expander("Services", expanded=True):
        _show_dataframe(_evidence_rows(business_services), "No detailed service evidence is available yet.")
    with st.expander("Processes", expanded=False):
        _show_dataframe(pd.DataFrame(processes), "No process evidence is available yet.")
    with st.expander("Applications", expanded=False):
        _show_dataframe(portfolio_df, "No application evidence is available yet.")
    with st.expander("Technologies", expanded=False):
        _show_dataframe(portfolio_df, "No technology evidence is available yet.")
    with st.expander("Cost Allocation", expanded=False):
        _show_dataframe(portfolio_df, "No cost allocation evidence is available yet.")
    with st.expander("Relationships", expanded=False):
        _show_dataframe(pd.DataFrame(relationship_paths), "No relationship evidence is available yet.")
    with st.expander("Recommendations", expanded=False):
        _show_dataframe(_recommendation_rows(selected_service), "No service recommendation evidence is available yet.")


render_page(
    title="Business Services",
    description="Business-service operating model across capabilities, applications, technologies, cost, health, risk, recommendations, automation, and evidence.",
    breadcrumbs=["Home", "Enterprise Digital Twin", "Business Services"],
    content=render_business_services_content,
    status=_status_from_score(service_summary["average_health"]),
    footer_version="E7.1.5",
)
