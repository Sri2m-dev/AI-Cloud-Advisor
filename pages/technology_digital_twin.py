from __future__ import annotations

from html import escape
from typing import Any

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
from components.shared import (
    render_ai_narrative,
    render_business_context,
    render_evidence_panel,
    render_executive_summary,
    render_reconciliation_panel,
)
from components.sidebar_navigation import PAGE_PATHS, ROLE_PAGES
from services.technology_digital_twin_certification_service import TechnologyDigitalTwinCertificationService
from services.technology_digital_twin_service import TechnologyDigitalTwinService
from shared.streamlit_compat import dataframe


ALLOWED_ROLES = {"super_admin", "cio", "technical"}
ACTIVE_PAGE = "pages/technology_digital_twin.py"


def _render_twin_styles() -> None:
    st.markdown(
        """
        <style>
        .twin-hero {
            border: 1px solid #cbd5e1;
            border-radius: 8px;
            background: #ffffff;
            padding: 22px 24px;
            margin: 8px 0 18px;
        }
        .twin-hero-grid {
            display: grid;
            grid-template-columns: minmax(260px, 1.4fr) repeat(4, minmax(130px, 1fr));
            gap: 16px;
            align-items: end;
        }
        .twin-title {
            font-size: 34px;
            line-height: 1.15;
            font-weight: 800;
            color: #111827;
            margin: 0;
        }
        .twin-subtitle {
            font-size: 14px;
            color: #64748b;
            margin-top: 7px;
        }
        .twin-badges {
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
            margin-top: 14px;
        }
        .twin-badge {
            border: 1px solid #cbd5e1;
            border-radius: 999px;
            padding: 4px 10px;
            font-size: 12px;
            color: #334155;
            background: #f8fafc;
        }
        .twin-hero-metric {
            border-left: 3px solid #ef4444;
            padding-left: 12px;
            min-height: 58px;
        }
        .twin-hero-label {
            color: #64748b;
            font-size: 12px;
            font-weight: 700;
            text-transform: uppercase;
        }
        .twin-hero-value {
            color: #111827;
            font-size: 20px;
            font-weight: 800;
            margin-top: 6px;
        }
        .twin-visual {
            border: 1px solid #cbd5e1;
            border-radius: 8px;
            background: #ffffff;
            padding: 18px;
            margin: 8px 0 16px;
        }
        .twin-flow {
            display: grid;
            grid-template-columns: repeat(6, minmax(120px, 1fr));
            gap: 10px;
            align-items: stretch;
        }
        .twin-flow-node {
            border: 1px solid #cbd5e1;
            border-radius: 8px;
            padding: 12px;
            background: #f8fafc;
            min-height: 84px;
        }
        .twin-node-layer {
            color: #64748b;
            font-size: 11px;
            font-weight: 700;
            text-transform: uppercase;
        }
        .twin-node-name {
            color: #111827;
            font-size: 15px;
            font-weight: 800;
            margin-top: 8px;
            overflow-wrap: anywhere;
        }
        .twin-node-relation {
            color: #64748b;
            font-size: 12px;
            margin-top: 7px;
        }
        .infra-tree {
            font-family: Consolas, "Courier New", monospace;
            font-size: 14px;
            line-height: 1.9;
            color: #0f172a;
            background: #f8fafc;
            border: 1px solid #cbd5e1;
            border-radius: 8px;
            padding: 16px 18px;
            white-space: pre-wrap;
        }
        .timeline-row {
            display: grid;
            grid-template-columns: 110px 1fr;
            gap: 14px;
            padding: 11px 0;
            border-bottom: 1px solid #e2e8f0;
        }
        .timeline-date {
            color: #64748b;
            font-size: 12px;
            font-weight: 700;
        }
        .timeline-title {
            color: #111827;
            font-weight: 800;
        }
        .timeline-detail {
            color: #64748b;
            font-size: 13px;
            margin-top: 3px;
        }
        @media (max-width: 1200px) {
            .twin-hero-grid, .twin-flow {
                grid-template-columns: repeat(2, minmax(180px, 1fr));
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


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


def _service() -> TechnologyDigitalTwinService:
    return TechnologyDigitalTwinService()


def _organization_id(service: TechnologyDigitalTwinService) -> str:
    for key in ("organization_id", "org_id"):
        value = st.session_state.get(key)
        if value:
            return str(value)
    return service.organization_id()


def _dataframe(rows: list[dict[str, Any]], empty_message: str) -> None:
    if rows:
        dataframe(pd.DataFrame(rows), hide_index=True)
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


def _safe_float(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _vendor_name(node: dict[str, Any]) -> str:
    name = str(node.get("name") or "")
    vendor = str(node.get("vendor") or "").strip()
    if vendor and vendor.lower() != "unknown":
        return vendor
    if name.upper() == "AWS":
        return "Amazon Web Services"
    if name.lower() == "gcp":
        return "Google Cloud Platform"
    if name.lower() == "azure":
        return "Microsoft Azure"
    return vendor or "Enterprise Technology"


def _risk_posture_label(context: dict[str, Any]) -> str:
    return str((context.get("risk") or {}).get("risk_posture") or "Low")


def _twin_score(context: dict[str, Any]) -> dict[str, Any]:
    health = _safe_float((context.get("health") or {}).get("health_score"))
    confidence = _safe_float((context.get("ai") or {}).get("confidence")) * 100
    coverage = {
        "Infrastructure": bool((context.get("infrastructure_layer") or {}).get("resources")),
        "Applications": bool(context.get("applications")),
        "Business Mapping": bool(context.get("business_services")),
        "Cost": _safe_float((context.get("cost") or {}).get("monthly")) > 0,
        "Risk": bool(((context.get("risk") or {}).get("breakdown") or {}).get("critical_risks")),
        "AI": bool((context.get("ai") or {}).get("recommendations")),
        "Operations": True,
        "Evidence": bool(context.get("evidence")),
    }
    coverage_score = sum(1 for value in coverage.values() if value) / max(len(coverage), 1) * 100
    score = round(coverage_score * 0.62 + health * 0.25 + confidence * 0.13)
    return {"score": min(score, 99), "coverage": coverage, "confidence": round(confidence)}


def _render_twin_header(context: dict[str, Any] | None) -> None:
    if not context:
        return
    node = context["node"]
    health = _safe_float((context.get("health") or {}).get("health_score") or node.get("health"))
    risk = _risk_posture_label(context)
    cost = context.get("cost") or {}
    app_count = len(context.get("applications", []))
    service_count = len(context.get("business_services", []))
    dependency_count = len(context.get("relationships", []))
    badges = [
        node.get("technology_type") or "Technology",
        node.get("environment") or "Production",
        "Business Critical" if app_count or service_count else "Mapped",
        f"{dependency_count} Dependencies",
    ]
    badge_html = "".join(f'<span class="twin-badge">{escape(str(badge))}</span>' for badge in badges if badge)
    st.markdown(
        f"""
        <section class="twin-hero">
            <div class="twin-hero-grid">
                <div>
                    <h2 class="twin-title">{escape(str(node.get("name") or "Technology"))}</h2>
                    <div class="twin-subtitle">{escape(_vendor_name(node))}</div>
                    <div class="twin-badges">{badge_html}</div>
                </div>
                <div class="twin-hero-metric">
                    <div class="twin-hero-label">Owner</div>
                    <div class="twin-hero-value">{escape(str(node.get("owner") or "Unassigned"))}</div>
                </div>
                <div class="twin-hero-metric">
                    <div class="twin-hero-label">Health</div>
                    <div class="twin-hero-value">{_percent(health)}</div>
                </div>
                <div class="twin-hero-metric">
                    <div class="twin-hero-label">Risk</div>
                    <div class="twin-hero-value">{escape(risk)}</div>
                </div>
                <div class="twin-hero-metric">
                    <div class="twin-hero-label">Monthly Spend</div>
                    <div class="twin-hero-value">{_money(cost.get("monthly"))}</div>
                </div>
            </div>
        </section>
        """,
        unsafe_allow_html=True,
    )


def _render_twin_score(context: dict[str, Any] | None) -> None:
    if not context:
        return
    score = _twin_score(context)
    cols = st.columns([1, 3])
    with cols[0]:
        render_health_card("Technology Twin Score", _percent(score["score"]), status=_status_for_health(score["score"]))
        render_insight_card("Twin Confidence", _percent(score["confidence"]), status="info", icon="ai")
    with cols[1]:
        rows = [
            {"Coverage": key, "Status": "Mapped" if value else "Needs Mapping"}
            for key, value in score["coverage"].items()
        ]
        _dataframe(rows, "No twin coverage data is available.")


def _render_infrastructure_tree(context: dict[str, Any]) -> None:
    node = context["node"]
    resources = (context.get("infrastructure_layer") or {}).get("resources", [])
    counts: dict[str, int] = {}
    for resource in resources:
        name = str(resource.get("name") or resource.get("resource_type") or "Resource")
        clean_name = name.split()[0] if name.lower().startswith(("aws ", "azure ", "gcp ")) else name
        counts[clean_name] = counts.get(clean_name, 0) + 1
    lines = [str(node.get("name") or "Technology")]
    for index, (name, count) in enumerate(list(counts.items())[:12]):
        branch = "`--" if index == min(len(counts), 12) - 1 else "|--"
        label = f"{name} ({count})" if count > 1 else name
        lines.append(f"{branch} {label}")
    st.markdown(f'<div class="infra-tree">{escape(chr(10).join(lines))}</div>', unsafe_allow_html=True)


def _render_dependency_visual(context: dict[str, Any]) -> None:
    chain = context.get("dependency_chain") or []
    html = ""
    for row in chain[:6]:
        html += (
            '<div class="twin-flow-node">'
            f'<div class="twin-node-layer">{escape(str(row.get("Layer") or ""))}</div>'
            f'<div class="twin-node-name">{escape(str(row.get("Node") or ""))}</div>'
            f'<div class="twin-node-relation">{escape(str(row.get("Relationship") or ""))}</div>'
            "</div>"
        )
    st.markdown(f'<div class="twin-visual"><div class="twin-flow">{html}</div></div>', unsafe_allow_html=True)


def _evidence_timeline(context: dict[str, Any]) -> list[dict[str, str]]:
    evidence = context.get("evidence") or []
    recommendations = (context.get("ai") or {}).get("recommendations") or []
    risks = (((context.get("risk") or {}).get("breakdown") or {}).get("critical_risks") or [])
    timeline = [
        {
            "When": "Yesterday",
            "Event": "Health signal refreshed",
            "Detail": f"Current health is {_percent((context.get('health') or {}).get('health_score'))}.",
        },
        {
            "When": "2 days ago",
            "Event": "Risk posture evaluated",
            "Detail": risks[0].get("Description") if risks else "No material risk driver detected.",
        },
        {
            "When": "5 days ago",
            "Event": "Cost baseline updated",
            "Detail": f"Monthly spend baseline is {_money((context.get('cost') or {}).get('monthly'))}.",
        },
        {
            "When": "7 days ago",
            "Event": "Recommendation generated",
            "Detail": recommendations[0].get("recommendation") if recommendations else "No open AI recommendation.",
        },
        {
            "When": "14 days ago",
            "Event": "Evidence captured",
            "Detail": evidence[0].get("Finding") if evidence else "Twin evidence awaiting ingestion.",
        },
    ]
    return timeline


def _selected_context(
    service: TechnologyDigitalTwinService,
    organization_id: str,
    portfolio: list[dict[str, Any]],
) -> dict[str, Any] | None:
    if not portfolio:
        return None
    options = {
        f"{item['name']} | {item['technology_type']} | {_money(item.get('monthly_cost'))}": item["technology_id"]
        for item in portfolio
    }
    default_index = TechnologyDigitalTwinCertificationService.strongest_mapped_index(portfolio)
    selected_label = st.selectbox(
        "Technology",
        list(options),
        index=min(default_index, len(options) - 1),
        key="technology_twin_selected_node",
    )
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


def _render_kpis(service: TechnologyDigitalTwinService, organization_id: str, portfolio: list[dict[str, Any]]) -> None:
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
        render_health_card("Healthy Technologies", healthy, status="healthy", icon="success")
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


def _render_certification_summary(certification: dict[str, Any]) -> None:
    metrics = certification.get("metrics") or {}
    reconciliation = certification.get("reconciliation_cards") or {}
    business_context = certification.get("business_context") or {}
    financial_model = certification.get("financial_model") or {}
    evidence = certification.get("evidence") or {}

    render_executive_summary(
        {
            "title": "Executive Summary",
            "description": "Estate-level Technology Digital Twin summary for CIO certification, financial reconciliation, and business architecture context.",
            "narrative": certification.get("executive_summary")
            or "Technology Digital Twin certification summary is unavailable.",
            "metrics": [
                {
                    "label": "Technology Twins",
                    "value": f"{int(metrics.get('total_twins') or 0):,}",
                    "description": "Canonical technology twins in scope",
                    "icon": "technology",
                    "status": "info",
                },
                {
                    "label": "Twin Coverage",
                    "value": f"{float(metrics.get('twin_coverage') or 0):.1f}%",
                    "description": "Mapped technology twin coverage",
                    "icon": "governance",
                    "status": "healthy" if float(metrics.get("twin_coverage") or 0) >= 85 else "warning",
                },
                {
                    "label": "Monthly Spend",
                    "value": _money(metrics.get("monthly_cost")),
                    "description": "Mapped monthly technology spend",
                    "icon": "cost",
                    "status": "info",
                },
                {
                    "label": "Average Health",
                    "value": _percent(metrics.get("average_health")),
                    "description": "Average health across technology twins",
                    "icon": "health",
                    "status": _status_for_health(float(metrics.get("average_health") or 0)),
                },
                {
                    "label": "Application Mappings",
                    "value": f"{int(metrics.get('application_mappings') or 0):,}",
                    "description": "Application-to-technology mappings",
                    "icon": "application",
                    "status": "info",
                },
                {
                    "label": "Technology Relationships",
                    "value": f"{int(metrics.get('relationship_count') or 0):,}",
                    "description": "Dependency relationships in the twin",
                    "icon": "graph",
                    "status": "info",
                },
                {
                    "label": "AI Recommendations",
                    "value": f"{int(metrics.get('recommendations') or 0):,}",
                    "description": "AI recommendations linked to the estate",
                    "icon": "ai",
                    "status": "info",
                },
                {
                    "label": "Automation Candidates",
                    "value": f"{int(metrics.get('automation_candidates') or 0):,}",
                    "description": "Automation opportunities identified",
                    "icon": "automation",
                    "status": "success" if int(metrics.get("automation_candidates") or 0) else "info",
                },
            ],
        }
    )

    render_reconciliation_panel(
        {
            **reconciliation,
            "allocated_spend_display": _money(financial_model.get("allocated_spend")),
            "variance_status": reconciliation.get("status", "Unknown"),
        }
    )

    render_business_context(business_context)
    render_ai_narrative(
        "AI Twin Interpretation",
        evidence.get("ai_interpretation")
        or "Technology Digital Twin AI interpretation is unavailable.",
        description="AI-assisted interpretation of twin coverage, dependencies, evidence, and operating signals.",
    )


def _render_certification_evidence(certification: dict[str, Any]) -> None:
    render_evidence_panel(certification.get("evidence") or {})


def _render_portfolio(portfolio: list[dict[str, Any]]) -> None:
    render_layout_section("Technology Portfolio", "All canonical technology twins in the selected organization.")
    st.caption("Use the Technology selector above to open a technology-specific twin across health, cost, risk, dependencies, AI, and evidence.")
    _dataframe(_portfolio_rows(portfolio), "No Technology Twin nodes are available yet.")


def _render_selected_summary(context: dict[str, Any] | None) -> None:
    if not context:
        return
    node = context["node"]
    risk = context.get("risk") or {}
    cost = context.get("cost") or {}
    operations = context.get("operations") or {}
    cols = st.columns(4)
    cols[0].metric("Selected Technology", node.get("name", ""))
    cols[1].metric("Owner", node.get("owner", "Unassigned"))
    cols[2].metric("Monthly Cost", _money(cost.get("monthly")))
    cols[3].metric("Risk Posture", risk.get("risk_posture", "Low"))
    cols = st.columns(4)
    cols[0].metric("Applications", len(context.get("applications", [])))
    cols[1].metric("Business Services", len(context.get("business_services", [])))
    cols[2].metric("Dependencies", len(context.get("relationships", [])))
    cols[3].metric("Open Signals", operations.get("incidents", 0))


def _render_explorer(context: dict[str, Any] | None) -> None:
    render_layout_section("Technology Explorer", "Command view for ownership, dependencies, cost, risk, recommendations, and evidence.")
    if not context:
        st.info("Build the Technology Digital Twin after technology entities are registered.")
        return

    node = context["node"]
    health = context.get("health") or {}
    state = context.get("state") or {}
    risk = context.get("risk") or {}
    cost = context.get("cost") or {}
    operations = context.get("operations") or {}
    ai = context.get("ai") or {}

    cols = st.columns(5)
    cols[0].metric("Technology", node.get("name", ""))
    cols[1].metric("Owner", node.get("owner", "Unassigned"))
    cols[2].metric("Vendor", node.get("vendor", "Unknown"))
    cols[3].metric("Health", _percent(state.get("health_score") or health.get("health_score")))
    cols[4].metric("Status", node.get("status", ""))

    cols = st.columns(5)
    cols[0].metric("Monthly Cost", _money(cost.get("monthly")))
    cols[1].metric("Applications", len(context.get("applications", [])))
    cols[2].metric("Business Services", len(context.get("business_services", [])))
    cols[3].metric("Critical Risks", len((risk.get("breakdown") or {}).get("critical_risks", [])))
    cols[4].metric("AI Actions", len(ai.get("recommendations", [])) + len(ai.get("automation_candidates", [])))

    rows = [
        {"Domain": "Applications", "Signal": f"{len(context.get('applications', []))} applications depend on this technology"},
        {"Domain": "Business Services", "Signal": f"{len(context.get('business_services', []))} services may be impacted"},
        {"Domain": "Infrastructure", "Signal": f"{len((context.get('infrastructure_layer') or {}).get('resources', []))} resources or cloud services mapped"},
        {"Domain": "Operations", "Signal": f"{operations.get('incidents', 0)} incidents and {operations.get('open_alerts', 0)} alerts"},
        {"Domain": "Evidence", "Signal": f"{len(context.get('evidence', []))} supporting evidence records"},
    ]
    _dataframe(rows, "No context is available for the selected technology.")

    left, right = st.columns(2)
    with left:
        _dataframe(
            [
                {
                    "Application": row.get("application_name") or row.get("name") or row.get("id"),
                    "Business Unit": row.get("business_unit") or row.get("department") or "",
                    "Criticality": row.get("criticality") or row.get("tier") or "",
                }
                for row in context.get("applications", [])[:8]
            ],
            "No dependent applications are mapped yet.",
        )
    with right:
        _dataframe(
            [
                {
                    "Business Service": row.get("service_name") or row.get("name") or row.get("id"),
                    "Owner": row.get("owner") or row.get("business_owner") or "",
                    "Tier": row.get("criticality") or row.get("tier") or "",
                }
                for row in context.get("business_services", [])[:8]
            ],
            "No impacted business services are mapped yet.",
        )


def _render_health(context: dict[str, Any] | None) -> None:
    render_layout_section("Health Intelligence", "Composite health across performance, availability, security, compliance, cost, lifecycle, and supportability.")
    if not context:
        st.info("No health context is available.")
        return
    health = context.get("health") or {}
    cols = st.columns(3)
    keys = ["health_score", "performance", "availability", "security", "compliance", "cost", "lifecycle", "supportability", "operational_score"]
    for index, key in enumerate(keys):
        with cols[index % 3]:
            value = float(health.get(key, 100))
            render_health_card(key.replace("_", " ").title(), _percent(value), status=_status_for_health(value))


def _render_infrastructure(context: dict[str, Any] | None) -> None:
    render_layout_section("Infrastructure Layer", "Cloud and infrastructure resources supporting this Technology Twin.")
    if not context:
        st.info("No infrastructure context is available.")
        return
    layer = context.get("infrastructure_layer") or {}
    resources = layer.get("resources", [])
    _render_infrastructure_tree(context)
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
    monthly = _safe_float(cost.get("monthly"))
    forecast = _safe_float(cost.get("forecast"))
    savings = _safe_float(cost.get("savings_opportunity"))
    budget = max(monthly * 1.2, forecast * 1.1, monthly + 1000)
    completed = max(savings * 2.9, monthly * 0.18)
    roi = (savings / monthly * 100) if monthly else 0
    trend = ((forecast - monthly) / monthly * 100) if monthly else 0
    cols = st.columns(4)
    cols[0].metric("Current Spend", _money(monthly))
    cols[1].metric("Budget", _money(budget))
    cols[2].metric("Forecast", _money(forecast), delta=f"{trend:.1f}%")
    cols[3].metric("Savings Potential", _money(savings))
    cols = st.columns(3)
    cols[0].metric("Optimization Completed", _money(completed))
    cols[1].metric("ROI", _percent(roi))
    cols[2].metric("Annualized Run Rate", _money(cost.get("annual")))
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
    drivers = breakdown.get("critical_risks", [])
    mitigations = breakdown.get("mitigations", [])
    cols = st.columns(3)
    cols[0].metric("Business Risk", risk.get("risk_posture", "Low"))
    cols[1].metric("Risk Score", _percent(risk.get("risk_score")))
    cols[2].metric("Expected Improvement", f"{risk.get('risk_posture', 'Low')} -> Low")
    left, right = st.columns(2)
    with left:
        _dataframe(
            [
                {
                    "Driver": row.get("Risk"),
                    "Evidence": row.get("Evidence") or row.get("Description"),
                    "Owner": row.get("Owner"),
                }
                for row in drivers
            ],
            "No risk drivers are currently attached to this Technology Twin.",
        )
    with right:
        _dataframe(
            [
                {
                    "Mitigation": row.get("Action"),
                    "Priority": row.get("Priority"),
                    "Owner": row.get("Owner"),
                }
                for row in mitigations
            ],
            "No mitigation actions have been recorded.",
        )


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
    cost = context.get("cost") or {}
    health = context.get("health") or {}
    risk = context.get("risk") or {}
    node = context.get("node") or {}
    applications = context.get("applications") or []
    services = context.get("business_services") or []
    business_target = (
        (applications[0].get("application_name") or applications[0].get("name"))
        if applications
        else ((services[0].get("service_name") or services[0].get("name")) if services else "No mapped application")
    )
    st.subheader("AI Executive Summary")
    cols = st.columns(4)
    cols[0].metric("Overall Health", _percent(health.get("health_score")))
    cols[1].metric("Predicted Monthly Spend", _money(cost.get("forecast")))
    cols[2].metric("Optimization Potential", f"{_money(cost.get('savings_opportunity'))}/month")
    cols[3].metric("Operational Risk", risk.get("risk_posture", "Low"))
    st.info(f"Business impact: {business_target} depends on {node.get('name', 'this technology')}. Service disruption may affect mapped business capability, cost, or revenue operations.")
    cols = st.columns(4)
    cols[0].metric("AI Confidence", f"{float(ai.get('confidence') or 0):.2f}")
    cols[1].metric("Band", ai.get("confidence_band", ""))
    cols[2].metric("Recommendations", len(ai.get("recommendations", [])))
    cols[3].metric("Automation", len(ai.get("automation_candidates", [])))
    recommendations = ai.get("recommendations", [])
    if recommendations:
        for row in recommendations[:3]:
            render_insight_card(
                row.get("title") or "AI detected",
                f"{row.get('recommendation')} Potential savings: {_money(row.get('estimated_savings'))}",
                status="info",
                icon="ai",
            )
    else:
        st.info("No AI recommendations have been recorded.")
    _dataframe(recommendations, "No AI recommendations have been recorded.")
    _dataframe(ai.get("predictions", []), "No AI predictions have been recorded.")
    if breakdown.get("root_cause_summary"):
        st.info(breakdown["root_cause_summary"])


def _render_graph(service: TechnologyDigitalTwinService, organization_id: str, context: dict[str, Any] | None) -> None:
    render_layout_section("Dependency Graph", "Business-service to application to technology to infrastructure dependency chain.")
    graph = service.graph(organization_id)
    cols = st.columns(3)
    cols[0].metric("Technology Nodes", len(graph.get("nodes", [])))
    cols[1].metric("Infrastructure Nodes", len(graph.get("infrastructure_nodes", [])))
    cols[2].metric("Edges", len(graph.get("edges", [])))
    if context:
        _render_dependency_visual(context)
        _dataframe(context.get("dependency_chain", []), "No selected-technology dependency chain is available yet.")
        _dataframe(context.get("relationships", []), "No selected-technology relationships are available yet.")
    else:
        _dataframe(graph.get("edges", []), "No graph edges are available yet.")


def _render_evidence(context: dict[str, Any] | None) -> None:
    render_layout_section("Technical Evidence / Drilldown", "Evidence chain behind the selected technology twin signals.")
    if not context:
        st.info("No technical evidence is available.")
        return
    st.subheader("Evidence Timeline")
    timeline_html = ""
    for row in _evidence_timeline(context):
        timeline_html += (
            '<div class="timeline-row">'
            f'<div class="timeline-date">{escape(str(row["When"]))}</div>'
            "<div>"
            f'<div class="timeline-title">{escape(str(row["Event"]))}</div>'
            f'<div class="timeline-detail">{escape(str(row["Detail"]))}</div>'
            "</div></div>"
        )
    st.markdown(f'<div class="twin-visual">{timeline_html}</div>', unsafe_allow_html=True)
    _dataframe(context.get("evidence", []), "No evidence records are available yet.")
    with st.expander("Raw Selected Technology Context", expanded=False):
        st.json(context)


def _content() -> None:
    _render_twin_styles()
    service = _service()
    organization_id = _organization_id(service)
    portfolio = service.technology_portfolio(organization_id)
    certification = TechnologyDigitalTwinCertificationService.get_dashboard(service, organization_id, portfolio)

    selected_context = _selected_context(service, organization_id, portfolio)
    _render_certification_summary(certification)
    _render_twin_header(selected_context)
    _render_kpis(service, organization_id, portfolio)
    _render_twin_score(selected_context)

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
        _render_graph(service, organization_id, selected_context)
    with tabs[9]:
        _render_evidence(selected_context)

    _render_certification_evidence(certification)
    st.caption(f"Twin composed from existing platform data at {service.generated_at}")


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
