from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4

import pandas as pd
import streamlit as st

from auth.role_constants import normalize_role
from components.cards import (
    render_health_card,
    render_insight_card,
    render_kpi_card,
    render_metric_card,
    render_risk_card,
)
from components.layout import render_page as render_layout_page, render_section as render_layout_section
from components.navigation import render_enterprise_sidebar
from components.sidebar_navigation import PAGE_PATHS, ROLE_PAGES
from repositories.entity_repository import EntityRepository
from services.technology_twin_service import TechnologyTwinService


ALLOWED_ROLES = {"super_admin", "cio", "technical"}
ACTIVE_PAGE = "pages/technology_digital_twin.py"


def _require_authorized_role() -> None:
    role = normalize_role(st.session_state.get("role", ""))
    if role not in ALLOWED_ROLES:
        st.error("Technology Digital Twin is available only to CIO, Technical, and Super Admin users.")
        st.stop()


def _render_sidebar() -> None:
    role = normalize_role(st.session_state.get("role", "cio"))
    render_enterprise_sidebar(
        role,
        page_paths=PAGE_PATHS,
        role_pages=ROLE_PAGES,
        active_page=ACTIVE_PAGE,
    )


def _service() -> TechnologyTwinService:
    return TechnologyTwinService()


def _organization_id(service: TechnologyTwinService) -> UUID:
    for key in ("organization_id", "org_id"):
        value = st.session_state.get(key)
        if value:
            try:
                return UUID(str(value))
            except ValueError:
                continue

    latest_twins = sorted(service.twin_repository._twins.values(), key=lambda twin: twin.generated_at, reverse=True)
    if latest_twins:
        return latest_twins[0].organization_id

    entities = service.entity_repository.get_entities()
    if entities:
        return entities[0].organization_id
    return uuid4()


def _dataframe(rows: list[dict[str, Any]], empty_message: str) -> None:
    if rows:
        st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
    else:
        st.info(empty_message)


def _money(value: float | int | str | None) -> str:
    try:
        return f"${float(value or 0):,.0f}"
    except (TypeError, ValueError):
        return "$0"


def _percent(value: float | int | str | None) -> str:
    try:
        return f"{float(value or 0):.1f}%"
    except (TypeError, ValueError):
        return "0.0%"


def _status_for_health(value: float) -> str:
    if value >= 85:
        return "healthy"
    if value >= 70:
        return "warning"
    return "critical"


def _selected_context(
    service: TechnologyTwinService,
    organization_id: UUID,
    portfolio: list[dict[str, Any]],
) -> dict[str, Any] | None:
    if not portfolio:
        return None
    options = {
        f"{item['name']} | {item['technology_type']} | {item['technology_id']}": item["technology_id"]
        for item in portfolio
    }
    selected_label = st.selectbox("Technology", list(options), key="technology_twin_selected_node")
    return service.technology_context(organization_id, options[selected_label])


def _portfolio_rows(portfolio: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "Technology": item["name"],
            "Type": item["technology_type"],
            "Vendor": item["vendor"],
            "Provider": item["cloud_provider"],
            "Environment": item["environment"],
            "Region": item["region"],
            "Status": item["status"],
            "Health": _percent(item["health"]),
            "Risk": _percent(item["risk"]),
            "Monthly Cost": _money(item["monthly_cost"]),
            "Applications": item["applications"],
            "Business Services": item["business_services"],
        }
        for item in portfolio
    ]


def _render_kpis(service: TechnologyTwinService, organization_id: UUID, portfolio: list[dict[str, Any]]) -> None:
    healthy = sum(1 for item in portfolio if float(item.get("health") or 0) >= 85)
    degraded = sum(1 for item in portfolio if float(item.get("health") or 0) < 70)
    monthly_cost = sum(float(item.get("monthly_cost") or 0) for item in portfolio)
    critical_risks = service.get_critical_risks(organization_id) if portfolio else []
    active_incidents = service.get_active_incidents(organization_id) if portfolio else []
    recommendations = service.get_recommendations(organization_id) if portfolio else []
    automation_candidates = service.get_automation_candidates(organization_id) if portfolio else []

    cols = st.columns(4)
    with cols[0]:
        render_kpi_card("Technology Twins", len(portfolio), status="info", icon="technology")
    with cols[1]:
        render_health_card("Healthy Twins", healthy, status="healthy", icon="success")
    with cols[2]:
        render_risk_card("Degraded Twins", degraded, status="critical" if degraded else "healthy", icon="warning")
    with cols[3]:
        render_metric_card("Monthly Cost", _money(monthly_cost), status="info", icon="cost")

    cols = st.columns(4)
    with cols[0]:
        render_risk_card("Critical Risks", len(critical_risks), status="critical" if critical_risks else "healthy")
    with cols[1]:
        render_metric_card("Active Incidents", len(active_incidents), status="warning" if active_incidents else "healthy")
    with cols[2]:
        render_insight_card("AI Recommendations", len(recommendations), status="info", icon="ai")
    with cols[3]:
        render_insight_card("Automation Candidates", len(automation_candidates), status="success" if automation_candidates else "info", icon="automation")


def _render_portfolio(portfolio: list[dict[str, Any]]) -> None:
    render_layout_section("Technology Portfolio", "All canonical technology twins in the selected organization.")
    _dataframe(_portfolio_rows(portfolio), "No Technology Twin nodes are available yet.")


def _render_explorer(context: dict[str, Any] | None) -> None:
    render_layout_section("Technology Explorer", "Entity-centered view of the selected Technology Twin.")
    if not context:
        st.info("Build the Technology Digital Twin after technology entities are registered.")
        return

    node = context["node"]
    health = context.get("health") or {}
    state = context.get("state") or {}
    cols = st.columns(4)
    cols[0].metric("Name", node.get("name", ""))
    cols[1].metric("Type", node.get("technology_type", ""))
    cols[2].metric("Status", node.get("status", ""))
    cols[3].metric("Health", _percent(state.get("health_score") or health.get("health_score")))

    rows = [
        {"Dimension": "Applications", "Value": len(context.get("applications", []))},
        {"Dimension": "Business Services", "Value": len(context.get("business_services", []))},
        {"Dimension": "Relationships", "Value": len(context.get("relationships", []))},
        {"Dimension": "Infrastructure Resources", "Value": len((context.get("infrastructure_layer") or {}).get("resources", []))},
    ]
    _dataframe(rows, "No context is available for the selected technology.")


def _render_health(context: dict[str, Any] | None) -> None:
    render_layout_section("Health Intelligence", "Availability, performance, capacity, utilization, reliability, and operational score.")
    if not context:
        st.info("No health context is available.")
        return
    health = context.get("health") or {}
    cols = st.columns(3)
    for index, key in enumerate(["availability", "performance", "capacity", "utilization", "reliability", "operational_score"]):
        with cols[index % 3]:
            render_health_card(key.replace("_", " ").title(), _percent(health.get(key, 100)), status=_status_for_health(float(health.get(key, 100))))


def _render_infrastructure(context: dict[str, Any] | None) -> None:
    render_layout_section("Infrastructure Layer", "Cloud and infrastructure resources supporting this Technology Twin.")
    if not context:
        st.info("No infrastructure context is available.")
        return
    layer = context.get("infrastructure_layer") or {}
    resources = layer.get("resources", [])
    rows = [
        {
            "Name": item.get("name", ""),
            "Type": item.get("resource_type", ""),
            "Provider": item.get("provider", ""),
            "Region": item.get("region", ""),
            "Environment": item.get("environment", ""),
            "Cost": _money(item.get("cost")),
            "Health": _percent(item.get("health")),
            "Risk": _percent(item.get("risk")),
        }
        for item in resources
    ]
    _dataframe(rows, "No infrastructure resources have been mapped to this Technology Twin.")


def _render_cost(context: dict[str, Any] | None) -> None:
    render_layout_section("Cost Intelligence", "Spend, forecast, budget variance, ROI, and optimization opportunity.")
    if not context:
        st.info("No cost context is available.")
        return
    cost = context.get("cost") or {}
    breakdown = cost.get("breakdown") or {}
    cols = st.columns(4)
    cols[0].metric("Monthly", _money(cost.get("monthly")))
    cols[1].metric("Annual", _money(cost.get("annual")))
    cols[2].metric("Forecast", _money(cost.get("forecast")))
    cols[3].metric("Savings", _money(cost.get("savings_opportunity")))
    _dataframe(
        [{"Metric": key, "Value": value} for key, value in breakdown.get("dimensions", {}).items()],
        "No cost breakdown has been calculated for this Technology Twin.",
    )


def _render_risk(context: dict[str, Any] | None) -> None:
    render_layout_section("Risk Intelligence", "Security, compliance, operational, financial, business, and technical debt risk.")
    if not context:
        st.info("No risk context is available.")
        return
    risk = context.get("risk") or {}
    breakdown = risk.get("breakdown") or {}
    cols = st.columns(3)
    cols[0].metric("Risk Score", _percent(risk.get("risk_score")))
    cols[1].metric("Posture", risk.get("risk_posture", ""))
    cols[2].metric("Critical Risks", len(breakdown.get("critical_risks", [])))
    _dataframe(breakdown.get("critical_risks", []), "No critical risks are currently attached to this Technology Twin.")
    _dataframe(breakdown.get("mitigations", []), "No mitigation actions have been recorded.")


def _render_operations(context: dict[str, Any] | None) -> None:
    render_layout_section("Operational Intelligence", "Incidents, alerts, deployments, changes, maintenance, and stability.")
    if not context:
        st.info("No operational context is available.")
        return
    operations = context.get("operations") or {}
    breakdown = operations.get("breakdown") or {}
    dimensions = breakdown.get("dimensions", {})
    cols = st.columns(4)
    cols[0].metric("Operational Health", _percent(operations.get("operational_health")))
    cols[1].metric("Incidents", dimensions.get("Open Incidents", operations.get("incidents", 0)))
    cols[2].metric("Alerts", dimensions.get("Active Alerts", operations.get("open_alerts", 0)))
    cols[3].metric("Deployments", dimensions.get("Recent Deployments", operations.get("deployments", 0)))
    _dataframe(breakdown.get("active_incidents", []), "No active incidents are linked to this Technology Twin.")
    _dataframe(breakdown.get("active_alerts", []), "No active alerts are linked to this Technology Twin.")


def _render_ai(context: dict[str, Any] | None) -> None:
    render_layout_section("AI Insights", "Recommendations, predictions, root-cause explanations, confidence, and automation readiness.")
    if not context:
        st.info("No AI insight context is available.")
        return
    ai = context.get("ai") or {}
    breakdown = ai.get("breakdown") or {}
    cols = st.columns(4)
    cols[0].metric("Confidence", f"{float(ai.get('confidence') or 0):.2f}")
    cols[1].metric("Band", ai.get("confidence_band", ""))
    cols[2].metric("Recommendations", len(ai.get("recommendations", [])))
    cols[3].metric("Automation", len(ai.get("automation_candidates", [])))
    _dataframe(ai.get("recommendations", []), "No AI recommendations have been recorded.")
    _dataframe(ai.get("predictions", []), "No AI predictions have been recorded.")
    if breakdown.get("root_cause_summary"):
        st.info(breakdown["root_cause_summary"])


def _render_graph(service: TechnologyTwinService, organization_id: UUID) -> None:
    render_layout_section("Dependency Graph", "Technology and infrastructure graph evidence.")
    graph = service.graph(organization_id)
    cols = st.columns(3)
    cols[0].metric("Technology Nodes", len(graph.get("nodes", [])))
    cols[1].metric("Infrastructure Nodes", len(graph.get("infrastructure_nodes", [])))
    cols[2].metric("Edges", len(graph.get("edges", [])))
    _dataframe(graph.get("edges", []), "No graph edges are available yet.")


def _render_evidence(context: dict[str, Any] | None) -> None:
    render_layout_section("Technical Evidence / Drilldown", "Raw twin evidence for engineering review.")
    if not context:
        st.info("No technical evidence is available.")
        return
    with st.expander("Selected Technology Context", expanded=True):
        st.json(context)


def _content() -> None:
    service = _service()
    organization_id = _organization_id(service)
    twin = service.get_latest_technology_twin(organization_id) or service.build_technology_twin(organization_id)
    portfolio = service.technology_portfolio(organization_id)

    _render_kpis(service, organization_id, portfolio)
    selected_context = _selected_context(service, organization_id, portfolio)

    tabs = st.tabs(
        [
            "Technology Portfolio",
            "Technology Explorer",
            "Health Intelligence",
            "Infrastructure Layer",
            "Cost Intelligence",
            "Risk Intelligence",
            "Operational Intelligence",
            "AI Insights",
            "Dependency Graph",
            "Technical Evidence",
        ]
    )
    with tabs[0]:
        _render_portfolio(portfolio)
    with tabs[1]:
        _render_explorer(selected_context)
    with tabs[2]:
        _render_health(selected_context)
    with tabs[3]:
        _render_infrastructure(selected_context)
    with tabs[4]:
        _render_cost(selected_context)
    with tabs[5]:
        _render_risk(selected_context)
    with tabs[6]:
        _render_operations(selected_context)
    with tabs[7]:
        _render_ai(selected_context)
    with tabs[8]:
        _render_graph(service, organization_id)
    with tabs[9]:
        _render_evidence(selected_context)

    st.caption(f"Twin generated at {twin.generated_at}")


def render_section() -> None:
    render_layout_page(
        title="Technology Digital Twin",
        description="Entity-centered workspace for technology health, cost, risk, operations, AI insights, dependencies, and evidence.",
        breadcrumbs=["Digital Twin", "Technology"],
        content=_content,
        status="Active",
        footer_version="3.3.8",
    )


def render_page() -> None:
    st.set_page_config(page_title="Technology Digital Twin", layout="wide")
    _require_authorized_role()
    _render_sidebar()
    render_section()


if __name__ == "__main__":
    render_page()
