from __future__ import annotations

from collections import Counter
from uuid import UUID

import pandas as pd
import streamlit as st

from auth.role_constants import normalize_role
from components.navigation.sidebar import render_enterprise_sidebar
from components.sidebar_navigation import PAGE_PATHS, ROLE_PAGES
from core.digital_twin.business_twin import BusinessTwin, BusinessTwinLevel, BusinessTwinNode, HIERARCHY_ORDER
from core.entities.entity import EntityRelationship, EntityType
from repositories.entity_repository import EntityRepository
from services.business_digital_twin_service import BusinessDigitalTwinService


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
    st.title("Twin Explorer")
    st.caption("Program 3.2.1 - Business Digital Twin exploration workspace")

    repository = _entity_repository()
    twin = _business_twin(repository)
    if not twin or not twin.nodes:
        st.info("No Business Digital Twin nodes are available yet. Register organization, business unit, capability, service, and application entities to explore the enterprise twin.")
        return

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


def render_page() -> None:
    st.set_page_config(page_title="Twin Explorer", layout="wide")
    _require_authorized_role()
    _render_sidebar()
    render_section()


if __name__ == "__main__":
    render_page()
