from __future__ import annotations

import html
from collections import Counter
from uuid import UUID

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
from components.navigation.sidebar import render_enterprise_sidebar
from components.sidebar_navigation import PAGE_PATHS, ROLE_PAGES
from core.digital_twin.business_twin import (
    HIERARCHY_ORDER,
    BusinessTwin,
    BusinessTwinLevel,
    BusinessTwinNode,
)
from core.entities.entity import EntityRelationship, EntityType
from repositories.entity_repository import EntityRepository
from services.business_digital_twin_service import BusinessDigitalTwinService
from services.demo_tenant_service import demo_mode_enabled, is_demo_tenant, load_demo_tenant
from shared.styles import configure_page

ALLOWED_ROLES = {"super_admin", "client_admin", "executive", "cio", "finance", "technical"}
ACTIVE_PAGE = "pages/twin_explorer.py"

CONTEXT_TYPES = {
    "Cloud Resources": {EntityType.CLOUD_RESOURCE.value, EntityType.CLOUD_ACCOUNT.value},
    "SaaS": {EntityType.SAAS_APPLICATION.value},
    "Owners": {EntityType.USER.value, EntityType.TEAM.value},
    "Risk": {EntityType.RISK.value},
    "Compliance": {EntityType.CONTROL.value, EntityType.POLICY.value},
    "Incidents": {EntityType.INCIDENT.value},
    "Recommendations": {EntityType.RECOMMENDATION.value},
    "Vendors": {EntityType.VENDOR.value},
}

BUSINESS_ENTITY_TYPES = {
    EntityType.ORGANIZATION.value,
    EntityType.BUSINESS_UNIT.value,
    EntityType.DEPARTMENT.value,
    EntityType.BUSINESS_CAPABILITY.value,
    EntityType.BUSINESS_SERVICE.value,
}


def _require_authorized_role() -> None:
    role = normalize_role(st.session_state.get("role", ""))
    if role not in ALLOWED_ROLES:
        st.error("Twin Explorer is available only to enterprise workspace roles.")
        st.stop()


def _render_sidebar() -> None:
    role = normalize_role(st.session_state.get("role", "cio"))
    render_enterprise_sidebar(
        role,
        page_paths=PAGE_PATHS,
        role_pages=ROLE_PAGES,
        active_page=ACTIVE_PAGE,
    )


def _entity_repository() -> EntityRepository:
    return EntityRepository()


def _organization_id(repository: EntityRepository) -> UUID | None:
    session_value = st.session_state.get("organization_id")
    if session_value:
        try:
            return UUID(str(session_value))
        except ValueError:
            pass
    entities = repository.get_entities()
    return entities[0].organization_id if entities else None


def _business_twin(repository: EntityRepository) -> BusinessTwin | None:
    organization_id = _organization_id(repository)
    if not organization_id:
        return None
    service = BusinessDigitalTwinService(entity_repository=repository)
    return service.build_business_twin(organization_id)


def _path_for_node(twin: BusinessTwin, node: BusinessTwinNode) -> list[BusinessTwinNode]:
    path = [node]
    current = node
    while current.parent_entity_id and current.parent_entity_id in twin.nodes:
        current = twin.nodes[current.parent_entity_id]
        path.append(current)
    return list(reversed(path))


def _node_label(twin: BusinessTwin, node: BusinessTwinNode) -> str:
    path = _path_for_node(twin, node)
    return " / ".join(item.display_name for item in path)


def _focus_options(twin: BusinessTwin) -> dict[str, UUID]:
    nodes = sorted(
        twin.nodes.values(),
        key=lambda node: (HIERARCHY_ORDER.index(node.level), _node_label(twin, node).lower()),
    )
    return {f"{_node_label(twin, node)}  [{node.level}]": node.entity_id for node in nodes}


def _selected_node_id(twin: BusinessTwin, options: dict[str, UUID]) -> UUID:
    selected_key = st.session_state.get("twin_explorer_focus")
    if selected_key:
        try:
            selected_id = UUID(str(selected_key))
        except ValueError:
            selected_id = next(iter(options.values()))
        if selected_id in twin.nodes:
            return selected_id
    return next(iter(options.values()))


def _related_entity_ids(
    scope_ids: set[UUID],
    relationships: list[EntityRelationship],
    include_types: set[str],
    entity_types: dict[UUID, str],
) -> set[UUID]:
    matches: set[UUID] = set()
    for relationship in relationships:
        if relationship.source_entity_id in scope_ids and entity_types.get(relationship.target_entity_id) in include_types:
            matches.add(relationship.target_entity_id)
        if relationship.target_entity_id in scope_ids and entity_types.get(relationship.source_entity_id) in include_types:
            matches.add(relationship.source_entity_id)
    return matches


def _scope_ids(twin: BusinessTwin, selected_id: UUID) -> set[UUID]:
    return {selected_id, *{node.entity_id for node in twin.descendants(selected_id)}}


def _table(rows: list[dict], empty_message: str) -> None:
    if rows:
        st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
    else:
        st.info(empty_message)


def _entity_rows(entity_ids: list[UUID] | set[UUID], repository: EntityRepository) -> list[dict]:
    rows = []
    for entity_id in sorted(entity_ids, key=str):
        entity = repository.get_entity(entity_id)
        if not entity:
            continue
        rows.append(
            {
                "Name": entity.display_name,
                "Type": entity.entity_type,
                "Owner": str(entity.owner_id) if entity.owner_id else "",
                "Lifecycle": entity.lifecycle_state,
                "Sources": ", ".join(reference.system for reference in entity.source_systems),
            }
        )
    return rows


def _application_rows(applications: list[BusinessTwinNode], repository: EntityRepository) -> list[dict]:
    rows = []
    for app in applications:
        source = repository.get_entity(app.entity_id)
        rows.append(
            {
                "Application": app.display_name,
                "Owner": str(app.owner_id) if app.owner_id else "",
                "Health": f"{app.health_score:.1f}%",
                "Risk": f"{app.risk_score:.1f}",
                "Cost": f"${app.cost:,.0f}",
                "Sources": ", ".join(reference.system for reference in source.source_systems) if source else "",
            }
        )
    return rows


def _kpi_rows(nodes: list[BusinessTwinNode]) -> list[dict]:
    rows = []
    for node in nodes:
        for name, value in node.kpis.items():
            rows.append({"Entity": node.display_name, "KPI": name, "Value": value})
    return rows


def _metadata_number(entity, keys: tuple[str, ...]) -> float:
    for key in keys:
        value = entity.metadata.get(key) if entity.metadata else None
        if value is None:
            continue
        try:
            return float(value or 0)
        except (TypeError, ValueError):
            continue
    return 0.0


def _money(value: float) -> str:
    if abs(value) >= 1_000_000:
        return f"${value / 1_000_000:,.1f}M".replace(".0M", "M")
    if abs(value) >= 1_000:
        return f"${value / 1_000:,.1f}K".replace(".0K", "K")
    return f"${value:,.0f}"


def _is_ai_entity(entity) -> bool:
    haystack = " ".join(
        [
            str(entity.display_name or ""),
            str(entity.description or ""),
            " ".join(f"{key} {value}" for key, value in (entity.metadata or {}).items()),
            " ".join(f"{key} {value}" for key, value in (entity.tags or {}).items()),
        ]
    ).lower()
    return any(term in haystack for term in ("ai", "agent", "copilot", "openai", "chatgpt", "llm"))


def _score_status(score: float) -> str:
    if score >= 85:
        return "healthy"
    if score >= 65:
        return "warning"
    return "critical"


def _relationship_model(mapped_dependencies: int, active_relationships: list[EntityRelationship], relationships: list[EntityRelationship]) -> dict:
    mapped = max(mapped_dependencies, len(active_relationships))
    if mapped <= 0:
        expected = max(len(relationships), 1)
    elif active_relationships:
        expected = max(mapped, len(relationships))
    else:
        expected = mapped + max(4, round(mapped * 0.18))
    missing = max(expected - mapped, 0)
    coverage = round((mapped / expected) * 100, 1) if expected else 0.0
    return {"mapped": mapped, "expected": expected, "missing": missing, "coverage": coverage}


def _dimension_scores(
    *,
    business_count: int,
    application_count: int,
    technology_count: int,
    relationship_coverage: float,
    total_spend: float,
    risk_count: int,
    ai_count: int,
    vendor_count: int,
) -> dict[str, int]:
    return {
        "Business": 100 if business_count else 0,
        "Applications": min(100, application_count * 50),
        "Technology": 100 if technology_count else 0,
        "Infrastructure": int(min(100, max(relationship_coverage, 70 if technology_count else 0))),
        "Cost": 100 if total_spend else 0,
        "Risk": min(100, 55 + risk_count * 5) if risk_count else 35,
        "AI": min(100, ai_count * 15) if ai_count else 0,
        "Evidence": int(min(100, max(relationship_coverage, 70 if technology_count and total_spend else 0))),
        "Vendors": 100 if vendor_count else 60 if technology_count else 0,
    }


def _recommendation_count_for(name: str, recommendations: list[dict]) -> int:
    target = str(name or "").lower()
    if not target:
        return 0
    return sum(
        1
        for row in recommendations
        if target in " ".join(str(value or "") for value in row.values()).lower()
    )


def _live_enterprise_signals(repository: EntityRepository) -> dict:
    entities = repository.get_entities()
    relationships = repository.get_relationships()
    active_relationships = [relationship for relationship in relationships if str(relationship.status).lower() == "active"]
    business_entities = [entity for entity in entities if entity.entity_type in BUSINESS_ENTITY_TYPES]
    applications = [entity for entity in entities if entity.entity_type == EntityType.APPLICATION.value]
    technology_entities = [
        entity
        for entity in entities
        if entity.entity_type in {EntityType.TECHNOLOGY.value, EntityType.CLOUD_RESOURCE.value, EntityType.CLOUD_ACCOUNT.value}
    ]
    vendors = [entity for entity in entities if entity.entity_type == EntityType.VENDOR.value]
    risks = [entity for entity in entities if entity.entity_type == EntityType.RISK.value]
    ai_agents = [entity for entity in entities if _is_ai_entity(entity)]
    metadata_cost = sum(
        _metadata_number(entity, ("cost", "total_cost", "monthly_cost", "annual_cost", "spend", "annual_spend"))
        for entity in entities
    )

    technology_portfolio = []
    critical_risks = []
    recommendations = []
    automation_candidates = []
    total_spend = metadata_cost
    average_health = 0.0
    try:
        from services.technology_digital_twin_service import TechnologyDigitalTwinService

        technology_service = TechnologyDigitalTwinService()
        organization_id = technology_service.organization_id()
        technology_portfolio = technology_service.technology_portfolio(organization_id)
        critical_risks = technology_service.get_critical_risks(organization_id)
        recommendations = technology_service.get_recommendations(organization_id)
        automation_candidates = technology_service.get_automation_candidates(organization_id)
        if technology_portfolio:
            total_spend = sum(float(item.get("monthly_cost") or 0) for item in technology_portfolio)
            average_health = sum(float(item.get("health") or 0) for item in technology_portfolio) / len(technology_portfolio)
    except Exception:
        technology_portfolio = []

    if not applications:
        try:
            from services.technology_health_service import TechnologyHealthService

            applications = TechnologyHealthService.get_applications()
        except Exception:
            applications = []

    portfolio_application_count = sum(int(item.get("applications") or 0) for item in technology_portfolio)
    portfolio_business_service_count = sum(int(item.get("business_services") or 0) for item in technology_portfolio)
    portfolio_dependency_count = sum(int(item.get("dependencies") or 0) for item in technology_portfolio)
    technology_count = max(len(technology_portfolio), len(technology_entities))
    application_count = max(len(applications), portfolio_application_count)
    business_signal_count = max(len(business_entities), portfolio_business_service_count)
    relationship_model = _relationship_model(portfolio_dependency_count, active_relationships, relationships)
    risk_count = max(len(critical_risks), len(risks))
    ai_count = max(len(recommendations), len(ai_agents))
    vendor_count = max(len(vendors), len({item.get("vendor") for item in technology_portfolio if item.get("vendor")}))
    dimension_scores = _dimension_scores(
        business_count=business_signal_count,
        application_count=application_count,
        technology_count=technology_count,
        relationship_coverage=relationship_model["coverage"],
        total_spend=total_spend,
        risk_count=risk_count,
        ai_count=ai_count,
        vendor_count=vendor_count,
    )
    twin_score = int(round(sum(dimension_scores.values()) / len(dimension_scores)))

    return {
        "entities": entities,
        "relationships": relationships,
        "active_relationships": active_relationships,
        "business_entities": business_entities,
        "applications": applications,
        "technology_entities": technology_entities,
        "technology_portfolio": technology_portfolio,
        "vendors": vendors,
        "risks": risks,
        "critical_risks": critical_risks,
        "ai_agents": ai_agents,
        "recommendations": recommendations,
        "automation_candidates": automation_candidates,
        "total_spend": total_spend,
        "relationship_coverage": relationship_model["coverage"],
        "relationship_model": relationship_model,
        "average_health": average_health,
        "technology_count": technology_count,
        "application_count": application_count,
        "business_signal_count": business_signal_count,
        "portfolio_business_service_count": portfolio_business_service_count,
        "twin_score": twin_score,
        "coverage_dimensions": dimension_scores,
    }


def _render_live_enterprise_snapshot(signals: dict) -> None:
    technology_count = signals["technology_count"]
    application_count = signals["application_count"]
    relationship_model = signals["relationship_model"]
    relationship_count = relationship_model["mapped"]
    business_count = signals["business_signal_count"]
    risk_count = max(len(signals["critical_risks"]), len(signals["risks"]))
    ai_count = max(len(signals["recommendations"]), len(signals["ai_agents"]))

    st.title("Enterprise Digital Twin Explorer")
    st.caption("Live business-to-technology map across applications, technologies, cost, risk, AI, and operating evidence.")

    summary_cols = st.columns(4)
    with summary_cols[0]:
        render_kpi_card("Business Services", f"{business_count:,}", "Business services and capability signals mapped through the twin", icon="enterprise", status="info")
    with summary_cols[1]:
        render_kpi_card("Applications", f"{application_count:,}", "Applications visible from live enterprise data", icon="application", status="info")
    with summary_cols[2]:
        render_kpi_card("Technologies", f"{technology_count:,}", "Technology and cloud entities in the twin", icon="technology", status="healthy" if technology_count else "warning")
    with summary_cols[3]:
        render_kpi_card(
            "Relationships",
            f"{relationship_count:,} of {relationship_model['expected']:,}",
            f"{relationship_model['missing']:,} relationship mappings still expected",
            icon="graph",
            status=_score_status(relationship_model["coverage"]),
        )

    signal_cols = st.columns(4)
    with signal_cols[0]:
        render_metric_card("Monthly Spend", _money(float(signals["total_spend"] or 0)), "Spend attached to the enterprise twin", icon="cost", status="info" if signals["total_spend"] else "warning")
    with signal_cols[1]:
        render_health_card("Avg Technology Health", f"{float(signals['average_health'] or 0):.1f}%", "Technology health across the live portfolio", icon="health", status="healthy" if float(signals["average_health"] or 0) >= 85 else "warning")
    with signal_cols[2]:
        render_risk_card("Risk Signals", f"{risk_count:,}", "Risk drivers linked to technologies or entities", icon="risk", status="warning" if risk_count else "healthy")
    with signal_cols[3]:
        render_insight_card("AI Signals", f"{ai_count:,}", "Recommendations, AI platforms, and automation candidates", icon="intelligence", status="info" if ai_count else "warning")

    score_cols = st.columns(3)
    with score_cols[0]:
        render_health_card("Enterprise Twin Score", f"{signals['twin_score']}%", "Weighted maturity across mapping, cost, risk, AI, evidence, and vendors", icon="graph", status=_score_status(signals["twin_score"]))
    with score_cols[1]:
        render_health_card(
            "Relationship Coverage",
            f"{signals['relationship_coverage']:.1f}%",
            f"{relationship_model['mapped']:,} mapped of {relationship_model['expected']:,} expected",
            icon="graph",
            status=_score_status(signals["relationship_coverage"]),
        )
    with score_cols[2]:
        render_insight_card("Automation Candidates", f"{len(signals['automation_candidates']):,}", "Optimization actions ready for automation review", icon="automation", status="success" if signals["automation_candidates"] else "info")


def _render_live_signal_tables(signals: dict) -> None:
    st.subheader("Live Enterprise Twin Signals")
    recommendations = signals["recommendations"]
    portfolio_rows = [
        {
            "Technology": item.get("name"),
            "Type": item.get("technology_type"),
            "Criticality": "Business Critical" if int(item.get("business_services") or 0) else "Operational",
            "Owner": item.get("owner"),
            "Health": f"{float(item.get('health') or 0):.1f}%",
            "Risk": item.get("risk_label"),
            "Monthly Spend": _money(float(item.get("monthly_cost") or 0)),
            "Cost Trend": "Rising" if float(item.get("monthly_cost") or 0) >= 3000 else "Stable",
            "Recommendations": _recommendation_count_for(str(item.get("name") or ""), recommendations),
            "Automation Ready": "Yes" if _recommendation_count_for(str(item.get("name") or ""), signals["automation_candidates"]) else "Review",
            "Last Updated": "Live",
            "Applications": item.get("applications"),
            "Services": item.get("business_services"),
            "Dependencies": item.get("dependencies"),
        }
        for item in signals["technology_portfolio"][:12]
    ]
    coverage_rows = [
        {
            "Twin Dimension": key,
            "Score": f"{value}%",
            "Status": "Live" if value >= 80 else "Partial" if value else "Needs Mapping",
        }
        for key, value in signals["coverage_dimensions"].items()
    ]
    left, right = st.columns([2, 1])
    with left:
        _table(portfolio_rows, "No live technology portfolio signals are available yet.")
    with right:
        _table(coverage_rows, "No twin coverage dimensions are available yet.")


def _render_enterprise_twin_home(repository: EntityRepository, signals: dict) -> None:
    entities = signals["entities"]
    relationships = signals["relationships"]
    business_entities = signals["business_entities"]
    applications = signals["applications"]
    technology_count = signals["technology_count"]
    relationship_coverage = signals["relationship_coverage"]

    st.divider()
    st.subheader("Enterprise Map Readiness")
    readiness_cols = st.columns(3)
    with readiness_cols[0]:
        render_health_card(
            "Relationship Coverage",
            f"{relationship_coverage:.1f}%",
            f"{signals['relationship_model']['mapped']:,} mapped of {signals['relationship_model']['expected']:,} expected",
            icon="graph",
            status=_score_status(relationship_coverage),
        )
    with readiness_cols[1]:
        render_health_card(
            "Business-to-Application",
            "Ready" if business_entities and applications else "Needs Mapping",
            "Requires business services and applications connected by relationships",
            icon="application",
            status="healthy" if business_entities and applications and relationships else "warning",
        )
    with readiness_cols[2]:
        render_health_card(
            "Application-to-Technology",
            "Ready" if signals["application_count"] and technology_count else "Needs Mapping",
            "Requires applications connected to technology and cloud resources",
            icon="technology",
            status="healthy" if signals["application_count"] and technology_count and signals["relationship_model"]["mapped"] else "warning",
        )

    st.subheader("Enterprise Twin Journey")
    journey_cols = st.columns(2)
    with journey_cols[0]:
        render_insight_card(
            "Business Impact Path",
            "Business -> Application -> Technology",
            description=(
                "The next maturity step is to connect business capabilities and services to applications, "
                "then connect those applications to technology, cloud, cost, risk, and operational evidence."
            ),
            icon="graph",
            status="info",
        )
    with journey_cols[1]:
        render_insight_card(
            "Recommended Next Action",
            "Populate Digital Twin Relationships",
            description=(
                "Register or sync business units, services, applications, technologies, vendors, owners, costs, "
                "and risks so this page becomes the enterprise map rather than a placeholder."
            ),
            icon="governance",
            status="warning" if not relationships else "healthy",
        )

    preview_rows = [
        {
            "Name": entity.display_name,
            "Type": entity.entity_type,
            "Lifecycle": entity.lifecycle_state,
            "Owner": str(entity.owner_id) if entity.owner_id else "",
        }
        for entity in entities[:25]
    ]
    _table(preview_rows, "No enterprise entities are registered yet.")


def _render_hierarchy(twin: BusinessTwin, selected_id: UUID) -> None:
    selected = twin.nodes[selected_id]
    st.subheader("Hierarchy")
    st.write(" > ".join(node.display_name for node in _path_for_node(twin, selected)))
    children = twin.children_of(selected_id)
    if children:
        for child in children:
            if st.button(child.display_name, key=f"child_{child.entity_id}", use_container_width=True):
                st.session_state["twin_explorer_focus"] = str(child.entity_id)
                st.rerun()
    elif selected.parent_entity_id:
        parent = twin.nodes.get(selected.parent_entity_id)
        if parent and st.button(f"Back to {parent.display_name}", key="twin_explorer_parent", use_container_width=True):
            st.session_state["twin_explorer_focus"] = str(parent.entity_id)
            st.rerun()


def _render_metrics(twin: BusinessTwin, selected_id: UUID, repository: EntityRepository) -> None:
    selected = twin.nodes[selected_id]
    descendants = twin.descendants(selected_id)
    scope = [selected, *descendants]
    level_counts = Counter(node.level for node in scope)
    relationships = repository.get_relationships()
    scope_entity_ids = {node.entity_id for node in scope}
    relationship_count = sum(
        1
        for relationship in relationships
        if relationship.source_entity_id in scope_entity_ids or relationship.target_entity_id in scope_entity_ids
    )
    col1, col2, col3, col4, col5, col6 = st.columns(6)
    col1.metric("Health", f"{twin.health_score(selected_id):.1f}%")
    col2.metric("Cost", f"${twin.total_cost(selected_id):,.0f}")
    col3.metric("Applications", level_counts.get(BusinessTwinLevel.APPLICATION.value, 0))
    col4.metric("Dependencies", relationship_count)
    col5.metric("Risk", f"{selected.risk_score:.1f}")
    col6.metric("Children", len(twin.children_of(selected_id)))


def _render_context(twin: BusinessTwin, selected_id: UUID, repository: EntityRepository) -> None:
    all_entities = repository.get_entities()
    entity_types = {entity.id: entity.entity_type for entity in all_entities}
    relationships = repository.get_relationships()
    scope = _scope_ids(twin, selected_id)
    selected = twin.nodes[selected_id]
    descendants = twin.descendants(selected_id)
    applications = (
        [selected]
        if selected.level == BusinessTwinLevel.APPLICATION.value
        else twin.applications_for_service(selected_id)
        if selected.level == BusinessTwinLevel.BUSINESS_SERVICE.value
        else [node for node in descendants if node.level == BusinessTwinLevel.APPLICATION.value]
    )
    technology_ids = set(selected.technology_entity_ids)
    vendor_ids = set(selected.vendor_entity_ids)
    for app in applications:
        technology_ids.update(app.technology_entity_ids)
        vendor_ids.update(app.vendor_entity_ids)

    tabs = st.tabs(
        [
            "Applications",
            "Technologies",
            "Cloud",
            "SaaS",
            "Owners",
            "Cost",
            "Risk",
            "Compliance",
            "Incidents",
            "Recommendations",
            "Health",
            "KPIs",
        ]
    )
    with tabs[0]:
        _table(_application_rows(applications, repository), "No applications are mapped under this twin node.")
    with tabs[1]:
        _table(_entity_rows(technology_ids, repository), "No technologies are mapped under this twin node.")
    with tabs[2]:
        _table(
            _entity_rows(_related_entity_ids(scope, relationships, CONTEXT_TYPES["Cloud Resources"], entity_types), repository),
            "No cloud resources are mapped under this twin node.",
        )
    with tabs[3]:
        _table(
            _entity_rows(_related_entity_ids(scope, relationships, CONTEXT_TYPES["SaaS"], entity_types), repository),
            "No SaaS applications are mapped under this twin node.",
        )
    with tabs[4]:
        owner_ids = {node.owner_id for node in [selected, *descendants] if node.owner_id}
        owner_ids.update(_related_entity_ids(scope, relationships, CONTEXT_TYPES["Owners"], entity_types))
        _table(_entity_rows(owner_ids, repository), "No owners are mapped under this twin node.")
    with tabs[5]:
        cost_rows = [
            {"Entity": node.display_name, "Level": node.level, "Cost": f"${node.cost:,.0f}"}
            for node in [selected, *descendants]
            if node.cost
        ]
        _table(cost_rows, "No cost metadata is mapped under this twin node.")
    with tabs[6]:
        risk_ids = set(twin.inherited_risks(selected_id))
        risk_ids.update(_related_entity_ids(scope, relationships, CONTEXT_TYPES["Risk"], entity_types))
        _table(_entity_rows(risk_ids, repository), "No risks are mapped under this twin node.")
    with tabs[7]:
        _table(
            _entity_rows(_related_entity_ids(scope, relationships, CONTEXT_TYPES["Compliance"], entity_types), repository),
            "No controls or policies are mapped under this twin node.",
        )
    with tabs[8]:
        _table(
            _entity_rows(_related_entity_ids(scope, relationships, CONTEXT_TYPES["Incidents"], entity_types), repository),
            "No incidents are mapped under this twin node.",
        )
    with tabs[9]:
        _table(
            _entity_rows(_related_entity_ids(scope, relationships, CONTEXT_TYPES["Recommendations"], entity_types), repository),
            "No recommendations are mapped under this twin node.",
        )
    with tabs[10]:
        health_rows = [
            {
                "Entity": node.display_name,
                "Level": node.level,
                "Health": f"{node.health_score:.1f}%",
                "Risk": f"{node.risk_score:.1f}",
            }
            for node in [selected, *descendants]
        ]
        _table(health_rows, "No health data is available for this twin node.")
    with tabs[11]:
        _table(_kpi_rows([selected, *descendants]), "No KPIs are mapped under this twin node.")


def render_section() -> None:
    repository = _entity_repository()
    signals = _live_enterprise_signals(repository)
    _render_live_enterprise_snapshot(signals)
    _render_live_signal_tables(signals)

    twin = _business_twin(repository)
    if not twin or not twin.nodes:
        _render_enterprise_twin_home(repository, signals)
        return

    st.divider()
    st.subheader("Business Twin Hierarchy")
    st.caption("Program 3.2.1 - Business Digital Twin exploration workspace")

    options = _focus_options(twin)
    selected_id = _selected_node_id(twin, options)
    labels_by_id = {value: label for label, value in options.items()}

    selected_label = st.selectbox(
        "Explore",
        list(options),
        index=list(options).index(labels_by_id[selected_id]),
        key="twin_explorer_select",
    )
    selected_id = options[selected_label]
    st.session_state["twin_explorer_focus"] = str(selected_id)

    left, right = st.columns([1, 3])
    with left:
        _render_hierarchy(twin, selected_id)
    with right:
        selected = twin.nodes[selected_id]
        st.subheader(selected.display_name)
        st.caption(f"{selected.level} | {selected.entity_type}")
        _render_metrics(twin, selected_id, repository)
        _render_context(twin, selected_id, repository)


def _render_demo_decision_twin(organization_id: str) -> None:
    payload = load_demo_tenant(organization_id)
    decisions = payload.get("decisions") or []
    journeys = {item["decision_id"]: item for item in payload.get("journeys") or []}
    labels = {f"{item['id']} · {item['title']}": item for item in decisions}
    requested_id = str(st.session_state.get("executive_decision_id") or "")
    selected_index = next(
        (index for index, item in enumerate(decisions) if item["id"] == requested_id),
        0,
    )

    st.title("Decision Digital Twin")
    st.caption(
        "Trace an executive decision from business service through technology, cost, risk, "
        "evidence, and accountable action."
    )
    st.warning("SYNTHETIC DEMONSTRATION DATA — isolated from production records.")
    selected_label = st.selectbox("Executive decision", list(labels), index=selected_index)
    decision = labels[selected_label]
    st.session_state["executive_decision_id"] = decision["id"]
    journey = journeys[decision["id"]]
    impact = decision.get("financial_impact")

    st.markdown(f"## {decision['title']}")
    metrics = st.columns(4)
    metrics[0].metric("Business service", decision["business_service"])
    metrics[1].metric(
        "Financial impact", f"${impact / 1_000_000:.1f}M" if impact else "UNKNOWN"
    )
    metrics[2].metric("Confidence", f"{decision['confidence']}%")
    metrics[3].metric("Evidence coverage", f"{decision['evidence_coverage']}%")

    st.subheader("Business-to-decision trace")
    st.caption("Follow the governed relationship from business outcome to accountable action.")
    path = journey.get("twin_path") or []
    nodes = "".join(
        "<div class='nexora-twin-node'>"
        f"<span>{html.escape(str(item['layer']).upper())}</span>"
        f"<strong>{html.escape(str(item['entity']))}</strong></div>"
        + ("<div class='nexora-twin-arrow' aria-hidden='true'>→</div>" if index < len(path) - 1 else "")
        for index, item in enumerate(path)
    )
    st.markdown(f"<div class='nexora-twin-path'>{nodes}</div>", unsafe_allow_html=True)

    left, right = st.columns(2)
    with left:
        st.subheader("Decision case")
        st.markdown(f"**What changed:** {journey['change']}")
        st.markdown(f"**Business impact:** {journey['impact']}")
        st.markdown(f"**Recommendation:** {journey['recommendation']}")
    with right:
        st.subheader("Authority and evidence")
        st.markdown(f"**Status:** {decision['status'].replace('_', ' ').title()}")
        st.markdown(f"**Evidence:** {journey['evidence']}")
        st.info(f"Next accountable step — {journey['next_step']}")

    actions = st.columns(3)
    with actions[0]:
        st.page_link("pages/decision_intelligence.py", label="Back to executive decisions")
    with actions[1]:
        st.page_link("pages/business_services.py", label="Open business services")
    with actions[2]:
        st.page_link("pages/approval_center.py", label="Open approval path")


def render_page() -> None:
    configure_page(page_title="Decision Digital Twin | Nexora", page_icon="N")
    _require_authorized_role()
    _render_sidebar()
    organization_id = str(st.session_state.get("organization_id") or "")
    if demo_mode_enabled() and is_demo_tenant(organization_id):
        _render_demo_decision_twin(organization_id)
        return
    render_section()


if __name__ == "__main__":
    render_page()
