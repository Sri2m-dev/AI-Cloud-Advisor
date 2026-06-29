from __future__ import annotations

from uuid import UUID, uuid5, NAMESPACE_DNS

import pandas as pd
import streamlit as st

from auth.role_constants import normalize_role
from components.navigation.sidebar import render_enterprise_sidebar
from components.sidebar_navigation import PAGE_PATHS, ROLE_PAGES
from core.entities.entity import EnterpriseEntity, EntityType, RelationshipType
from repositories.entity_repository import EntityRepository
from services.entity_service import EntityService


DEMO_ORG_ID = uuid5(NAMESPACE_DNS, "nexora.default.organization")
ALLOWED_ROLES = {"super_admin"}


def _service() -> EntityService:
    return EntityService(EntityRepository())


def _require_super_admin() -> None:
    role = normalize_role(st.session_state.get("role", ""))
    if role not in ALLOWED_ROLES:
        st.error("Entity Registry is available only to Super Admin users.")
        st.stop()


def _render_sidebar() -> None:
    role = normalize_role(st.session_state.get("role", "super_admin"))
    render_enterprise_sidebar(
        role,
        page_paths=PAGE_PATHS,
        role_pages=ROLE_PAGES,
        active_page="pages/entity_registry.py",
    )


def _seed_foundation_entities(service: EntityService) -> None:
    repository = service.repository
    if repository.get_entities():
        return

    owner = EnterpriseEntity(
        display_name="Platform Architecture Office",
        organization_id=DEMO_ORG_ID,
        entity_type=EntityType.TEAM.value,
        description="Enterprise team accountable for technology intelligence data quality.",
        tags={"domain": "platform", "tier": "enterprise"},
    )
    owner.add_source_reference("HRIS", "team-platform-architecture", "Platform Architecture Office")
    service.save(owner)

    vendor = EnterpriseEntity(
        display_name="Amazon Web Services",
        organization_id=DEMO_ORG_ID,
        entity_type=EntityType.VENDOR.value,
        owner_id=owner.id,
        description="Cloud infrastructure provider.",
        tags={"provider": "aws"},
    )
    vendor.add_source_reference("VendorManagement", "vendor-aws", "Amazon Web Services")
    service.save(vendor)

    cloud_account = EnterpriseEntity(
        display_name="AWS Production",
        organization_id=DEMO_ORG_ID,
        entity_type=EntityType.CLOUD_ACCOUNT.value,
        owner_id=owner.id,
        description="Primary production AWS account.",
        tags={"environment": "production", "provider": "aws"},
    )
    cloud_account.add_source_reference("AWS", "123456789012", "AWS Production")
    service.save(cloud_account)

    technology = EnterpriseEntity(
        display_name="Customer Analytics Cluster",
        organization_id=DEMO_ORG_ID,
        entity_type=EntityType.TECHNOLOGY.value,
        description="Analytics runtime supporting customer reporting workloads.",
        tags={"platform": "analytics", "criticality": "high"},
    )
    technology.add_source_reference("AWS", "i-0123456789", "analytics-prod-01")
    technology.add_source_reference("Datadog", "host-998", "analytics-prod-01")
    service.save(technology)

    application = EnterpriseEntity(
        display_name="Customer Insights",
        organization_id=DEMO_ORG_ID,
        entity_type=EntityType.APPLICATION.value,
        owner_id=owner.id,
        description="Internal application for customer profitability and usage analysis.",
        tags={"portfolio": "revenue", "criticality": "high"},
    )
    application.add_source_reference("CMDB", "CI0001234", "Customer Insights")
    service.save(application)

    business_service = EnterpriseEntity(
        display_name="Revenue Intelligence",
        organization_id=DEMO_ORG_ID,
        entity_type=EntityType.BUSINESS_SERVICE.value,
        owner_id=owner.id,
        description="Business service used by finance and sales leadership.",
        tags={"business_unit": "finance"},
    )
    business_service.add_source_reference("KnowledgeGraph", "kg-node-445", "Revenue Intelligence")
    service.save(business_service)

    recommendation = EnterpriseEntity(
        display_name="Right-size analytics compute",
        organization_id=DEMO_ORG_ID,
        entity_type=EntityType.RECOMMENDATION.value,
        description="Reduce oversized production analytics compute resources.",
        tags={"category": "cost_optimization"},
    )
    recommendation.add_source_reference("AIRecommendationEngine", "rec-aws-analytics-001")
    service.save(recommendation)

    service.add_relationship(business_service.id, RelationshipType.USES.value, application.id)
    service.add_relationship(application.id, RelationshipType.RUNS_ON.value, technology.id)
    service.add_relationship(technology.id, RelationshipType.DEPLOYED_IN.value, cloud_account.id)
    service.add_relationship(vendor.id, RelationshipType.SUPPLIES.value, technology.id)
    service.add_relationship(technology.id, RelationshipType.MITIGATED_BY.value, recommendation.id)


def _entity_rows(entities: list[EnterpriseEntity]) -> list[dict]:
    rows = []
    for entity in entities:
        rows.append(
            {
                "Name": entity.display_name,
                "Type": entity.entity_type,
                "Lifecycle": entity.lifecycle_state,
                "Owner": str(entity.owner_id) if entity.owner_id else "",
                "Sources": ", ".join(reference.system for reference in entity.source_systems),
                "Updated": entity.updated_at,
                "ID": str(entity.id),
            }
        )
    return rows


def _relationship_rows(service: EntityService, entity_id: UUID) -> list[dict]:
    rows = []
    for relationship in service.repository.get_relationships(entity_id):
        source = service.repository.get_entity(relationship.source_entity_id)
        target = service.repository.get_entity(relationship.target_entity_id)
        rows.append(
            {
                "Source": source.display_name if source else str(relationship.source_entity_id),
                "Relationship": relationship.relationship_type,
                "Target": target.display_name if target else str(relationship.target_entity_id),
                "System": relationship.source_system,
                "Confidence": relationship.confidence,
            }
        )
    return rows


def _render_summary(service: EntityService) -> None:
    metrics = service.quality_metrics()
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Entities", metrics.total_entities)
    col2.metric("Duplicate Candidates", metrics.duplicate_candidates)
    col3.metric("Source Coverage", f"{metrics.source_coverage:.1f}%")
    col4.metric("Sync Health", f"{metrics.sync_health:.1f}%")

    quality_col, source_col = st.columns(2)
    with quality_col:
        st.subheader("Data Quality")
        st.dataframe(
            pd.DataFrame(
                [
                    {"Metric": "Orphan Entities", "Value": metrics.orphan_entities},
                    {"Metric": "Missing Owners", "Value": metrics.missing_owners},
                    {"Metric": "Missing Relationships", "Value": metrics.missing_relationships},
                    {"Metric": "Stale Records", "Value": metrics.stale_records},
                ]
            ),
            hide_index=True,
            width="stretch",
        )
    with source_col:
        st.subheader("Source Systems")
        source_summary = service.source_system_summary()
        source_rows = [{"Source System": key, "References": value} for key, value in source_summary.items()]
        st.dataframe(pd.DataFrame(source_rows), hide_index=True, width="stretch")


def _render_type_summary(service: EntityService) -> None:
    rows = [
        {"Entity Type": entity_type, "Entities": count}
        for entity_type, count in service.entity_type_summary().items()
    ]
    st.subheader("Entity Types")
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")


def _render_duplicates(service: EntityService) -> None:
    st.subheader("Duplicate Candidates")
    rows = [
        {
            "Primary": primary.display_name,
            "Candidate": candidate.display_name,
            "Reason": reason,
            "Type": primary.entity_type,
        }
        for primary, candidate, reason in service.find_duplicate_candidates()
    ]
    if rows:
        st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
    else:
        st.success("No duplicate candidates detected.")


def _render_recent_changes(service: EntityService) -> None:
    st.subheader("Recent Changes")
    st.dataframe(
        pd.DataFrame(_entity_rows(service.recent_changes())),
        hide_index=True,
        width="stretch",
    )


def _render_entity_explorer(service: EntityService) -> None:
    st.subheader("Entity Explorer")
    search_col, type_col = st.columns([2, 1])
    query = search_col.text_input("Search", value="", placeholder="AWS, application, owner, source ID")
    type_options = ["All"] + sorted(service.entity_type_summary().keys())
    selected_type = type_col.selectbox("Entity Type", type_options)

    entities = service.repository.search(query)
    if selected_type != "All":
        entities = [entity for entity in entities if entity.entity_type == selected_type]

    if not entities:
        st.info("No entities match the current filters.")
        return

    st.dataframe(pd.DataFrame(_entity_rows(entities)), hide_index=True, width="stretch")

    selected_name = st.selectbox("Inspect Entity", [entity.display_name for entity in entities])
    selected_entity = next(entity for entity in entities if entity.display_name == selected_name)

    detail_col, relationship_col = st.columns([1, 1])
    with detail_col:
        st.markdown("#### Identity")
        st.json(
            {
                "id": str(selected_entity.id),
                "type": selected_entity.entity_type,
                "name": selected_entity.display_name,
                "lifecycle": selected_entity.lifecycle_state,
                "owner_id": str(selected_entity.owner_id) if selected_entity.owner_id else None,
                "organization_id": str(selected_entity.organization_id),
                "tags": selected_entity.tags,
                "metadata": selected_entity.metadata,
            }
        )
        st.markdown("#### Source Systems")
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "System": reference.system,
                        "External ID": reference.external_id,
                        "External Name": reference.external_name,
                        "Last Seen": reference.last_seen_at,
                    }
                    for reference in selected_entity.source_systems
                ]
            ),
            hide_index=True,
            width="stretch",
        )
    with relationship_col:
        st.markdown("#### Relationships")
        relationship_rows = _relationship_rows(service, selected_entity.id)
        if relationship_rows:
            st.dataframe(pd.DataFrame(relationship_rows), hide_index=True, width="stretch")
        else:
            st.info("No relationships registered for this entity.")


def render_section() -> None:
    st.title("Enterprise Entity Registry")
    st.caption("Program 1.1 - Universal Entity Registry foundation")

    service = _service()
    action_col, status_col = st.columns([1, 3])
    if action_col.button("Seed Foundation Sample", width="stretch"):
        _seed_foundation_entities(service)
        st.rerun()
    status_col.caption("This admin view validates the canonical entity model before existing modules migrate to it.")

    tab_summary, tab_types, tab_duplicates, tab_changes, tab_explorer = st.tabs(
        ["Summary", "Entity Types", "Duplicates", "Recent Changes", "Explorer"]
    )
    with tab_summary:
        _render_summary(service)
    with tab_types:
        _render_type_summary(service)
    with tab_duplicates:
        _render_duplicates(service)
    with tab_changes:
        _render_recent_changes(service)
    with tab_explorer:
        _render_entity_explorer(service)


def render_page() -> None:
    st.set_page_config(page_title="Entity Registry", layout="wide")
    _require_super_admin()
    _render_sidebar()
    render_section()


if __name__ == "__main__":
    render_page()
