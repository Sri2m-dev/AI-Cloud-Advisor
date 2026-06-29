from __future__ import annotations

from collections import Counter

import pandas as pd
import streamlit as st

from auth.role_constants import normalize_role
from components.navigation.sidebar import render_enterprise_sidebar
from components.sidebar_navigation import PAGE_PATHS, ROLE_PAGES
from core.correlation.correlation_event import CorrelationEventType
from core.identity.identity_match import IdentityResolutionStatus
from repositories.correlation_repository import CorrelationRepository
from repositories.entity_repository import EntityRepository
from repositories.identity_resolution_repository import IdentityResolutionRepository
from repositories.metadata_catalog_repository import MetadataCatalogRepository
from repositories.ontology_repository import OntologyRepository
from services.entity_service import EntityService


ALLOWED_ROLES = {"super_admin", "enterprise_architect", "platform_administrator"}
ACTIVE_PAGE = "pages/enterprise_data_fabric.py"


def _require_authorized_role() -> None:
    role = normalize_role(st.session_state.get("role", ""))
    if role not in ALLOWED_ROLES:
        st.error("Enterprise Data Fabric is available only to platform administration roles.")
        st.stop()


def _render_sidebar() -> None:
    role = normalize_role(st.session_state.get("role", "super_admin"))
    render_enterprise_sidebar(
        role,
        page_paths=PAGE_PATHS,
        role_pages=ROLE_PAGES,
        active_page=ACTIVE_PAGE,
    )


def _repositories() -> tuple[
    EntityService,
    EntityRepository,
    IdentityResolutionRepository,
    OntologyRepository,
    MetadataCatalogRepository,
    CorrelationRepository,
]:
    entity_repository = EntityRepository()
    return (
        EntityService(entity_repository),
        entity_repository,
        IdentityResolutionRepository(),
        OntologyRepository(),
        MetadataCatalogRepository(),
        CorrelationRepository(),
    )


def _dataframe(rows: list[dict], empty_message: str) -> None:
    if rows:
        st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
    else:
        st.info(empty_message)


def _score(values: list[float]) -> float:
    if not values:
        return 100.0
    return round(sum(values) / len(values), 2)


def _fabric_health_score(
    entity_service: EntityService,
    identity_repository: IdentityResolutionRepository,
    metadata_repository: MetadataCatalogRepository,
    correlation_repository: CorrelationRepository,
) -> tuple[float, dict[str, float]]:
    entity_metrics = entity_service.quality_metrics()
    candidates = identity_repository.list_candidates()
    results = correlation_repository.list_results()
    stale_records = metadata_repository.get_stale_entities()
    low_confidence_records = metadata_repository.get_low_confidence_entities()

    identity_total = max(len(candidates), 1)
    identity_success = round(
        (
            sum(
                1
                for candidate in candidates
                if candidate.status
                in {IdentityResolutionStatus.AUTO_MATCHED.value, IdentityResolutionStatus.MERGED.value}
            )
            / identity_total
        )
        * 100,
        2,
    )
    metadata_freshness = max(0.0, 100.0 - len(stale_records) * 10.0)
    lineage_completeness = min(100.0, len(metadata_repository.get_lineage_edges()) * 10.0)
    correlation_quality = _score([result.confidence_score for result in results])
    data_quality = entity_metrics.sync_health
    source_health = entity_metrics.source_coverage

    components = {
        "Identity Resolution": identity_success,
        "Metadata Freshness": metadata_freshness,
        "Lineage Completeness": lineage_completeness,
        "Correlation Quality": correlation_quality,
        "Data Quality": data_quality,
        "Source Health": source_health,
        "Confidence": max(0.0, 100.0 - len(low_confidence_records) * 10.0),
    }
    return _score(list(components.values())), components


def _render_fabric_health(
    entity_service: EntityService,
    identity_repository: IdentityResolutionRepository,
    metadata_repository: MetadataCatalogRepository,
    correlation_repository: CorrelationRepository,
) -> None:
    score, components = _fabric_health_score(
        entity_service,
        identity_repository,
        metadata_repository,
        correlation_repository,
    )
    st.metric("Fabric Health Score", f"{score:.1f}%")
    _dataframe(
        [{"Component": name, "Score": f"{value:.1f}%"} for name, value in components.items()],
        "Fabric health components will appear after data fabric activity is recorded.",
    )


def _render_entity_registry(entity_service: EntityService) -> None:
    metrics = entity_service.quality_metrics()
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Entities", metrics.total_entities)
    col2.metric("Duplicate Candidates", metrics.duplicate_candidates)
    col3.metric("Missing Owners", metrics.missing_owners)
    col4.metric("Missing Relationships", metrics.missing_relationships)

    type_rows = [
        {"Entity Type": entity_type, "Count": count}
        for entity_type, count in entity_service.entity_type_summary().items()
    ]
    recent_rows = [
        {
            "Name": entity.display_name,
            "Type": entity.entity_type,
            "Lifecycle": entity.lifecycle_state,
            "Sources": ", ".join(reference.system for reference in entity.source_systems),
            "Updated": entity.updated_at,
        }
        for entity in entity_service.recent_changes(10)
    ]
    left, right = st.columns(2)
    with left:
        st.subheader("Entity Types")
        _dataframe(type_rows, "No entities have been registered yet.")
    with right:
        st.subheader("Recently Changed")
        _dataframe(recent_rows, "No recent entity activity is available.")


def _render_identity_resolution(identity_repository: IdentityResolutionRepository) -> None:
    candidates = identity_repository.list_candidates()
    status_counts = Counter(candidate.status for candidate in candidates)
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Pending Reviews", status_counts.get(IdentityResolutionStatus.NEEDS_REVIEW.value, 0))
    col2.metric("Auto Matched", status_counts.get(IdentityResolutionStatus.AUTO_MATCHED.value, 0))
    col3.metric("Rejected", status_counts.get(IdentityResolutionStatus.REJECTED.value, 0))
    col4.metric("Merged", status_counts.get(IdentityResolutionStatus.MERGED.value, 0))

    rows = [
        {
            "Source": candidate.source_display_name,
            "Target": candidate.target_display_name,
            "Type": candidate.entity_type,
            "Confidence": candidate.confidence_score,
            "Status": candidate.status,
            "Signals": ", ".join(signal.name for signal in candidate.signals),
        }
        for candidate in candidates
    ]
    _dataframe(rows, "No identity match candidates are queued.")
    st.caption("Approve, reject, merge, and split actions are shown here as the review workflow matures.")


def _render_ontology_explorer(ontology_repository: OntologyRepository) -> None:
    ontology = ontology_repository.load()
    definitions = sorted(ontology.relationship_definitions.values(), key=lambda item: (item.group.value, item.name))
    rules = sorted(ontology.relationship_rules, key=lambda item: (item.relationship_type, item.description))

    definition_rows = [
        {
            "Group": definition.group.value,
            "Relationship": definition.name,
            "Direction": definition.direction,
            "Strength": definition.default_strength,
            "Description": definition.description,
        }
        for definition in definitions
    ]
    rule_rows = [
        {
            "Source": ", ".join(sorted(rule.source_entity_types)),
            "Relationship": rule.relationship_type,
            "Target": ", ".join(sorted(rule.target_entity_types)),
            "Cardinality": rule.cardinality.label,
            "Direction": rule.direction,
            "Description": rule.description,
        }
        for rule in rules
    ]

    st.subheader("Relationship Taxonomy")
    _dataframe(definition_rows, "No ontology definitions are available.")
    st.subheader("Validation Rules")
    _dataframe(rule_rows, "No ontology validation rules are available.")


def _render_metadata_health(metadata_repository: MetadataCatalogRepository) -> None:
    records = list(metadata_repository._metadata_records.values())
    assessments = list(metadata_repository._quality_assessments)
    stale_records = metadata_repository.get_stale_entities()
    low_confidence_records = metadata_repository.get_low_confidence_entities()

    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Metadata Records", len(records))
    col2.metric("Stale Metadata", len(stale_records))
    col3.metric("Low Confidence", len(low_confidence_records))
    col4.metric("Lineage Edges", len(metadata_repository.get_lineage_edges()))
    col5.metric("Quality Assessments", len(assessments))

    rows = [
        {
            "Entity ID": str(record.entity_id),
            "Source": record.source_system,
            "Freshness": record.freshness_status,
            "Completeness": record.completeness_score,
            "Confidence": record.confidence_score,
            "Owner Coverage": record.owner_coverage,
            "Relationship Coverage": record.relationship_coverage,
            "Staleness Days": record.staleness_days,
        }
        for record in sorted(records, key=lambda item: item.updated_at, reverse=True)[:25]
    ]
    _dataframe(rows, "No metadata catalog records are available yet.")


def _render_lineage_explorer(metadata_repository: MetadataCatalogRepository, entity_repository: EntityRepository) -> None:
    edges = metadata_repository.get_lineage_edges()
    rows = []
    for edge in edges:
        source = entity_repository.get_entity(edge.source_entity_id)
        target = entity_repository.get_entity(edge.target_entity_id)
        rows.append(
            {
                "Source": source.display_name if source else str(edge.source_entity_id),
                "Transformation": edge.transformation,
                "Target": target.display_name if target else str(edge.target_entity_id),
                "System": edge.source_system,
                "Confidence": edge.confidence_score,
                "Updated": edge.updated_at,
            }
        )
    _dataframe(rows, "No lineage edges have been recorded yet.")


def _render_correlation_center(correlation_repository: CorrelationRepository) -> None:
    results = correlation_repository.list_results()
    events = correlation_repository.list_events()
    event_counts = Counter(event.event_type for event in events)

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Events", len(events))
    col2.metric("Correlations", len(results))
    col3.metric("Event Types", len(event_counts))
    col4.metric("Avg Confidence", f"{_score([result.confidence_score for result in results]):.1f}%")

    result_rows = [
        {
            "Pattern": result.pattern_type,
            "Severity": result.severity,
            "Confidence": result.confidence_score,
            "Summary": result.summary,
            "Created": result.created_at,
        }
        for result in results[:25]
    ]
    _dataframe(result_rows, "No correlation results have been generated yet.")

    st.subheader("Event Type Coverage")
    coverage_rows = [
        {"Event Type": event_type.value, "Events": event_counts.get(event_type.value, 0)}
        for event_type in CorrelationEventType
    ]
    _dataframe(coverage_rows, "No event coverage data is available.")


def _render_data_quality(entity_service: EntityService, metadata_repository: MetadataCatalogRepository) -> None:
    metrics = entity_service.quality_metrics()
    rows = [
        {"Metric": "Orphan Entities", "Value": metrics.orphan_entities},
        {"Metric": "Duplicate Candidates", "Value": metrics.duplicate_candidates},
        {"Metric": "Missing Owners", "Value": metrics.missing_owners},
        {"Metric": "Missing Relationships", "Value": metrics.missing_relationships},
        {"Metric": "Stale Metadata", "Value": len(metadata_repository.get_stale_entities())},
        {"Metric": "Broken Lineage", "Value": _broken_lineage_count(metadata_repository, entity_service.repository)},
    ]
    _dataframe(rows, "No data quality metrics are available.")


def _render_source_systems(entity_service: EntityService, metadata_repository: MetadataCatalogRepository) -> None:
    source_counts = Counter(entity_service.source_system_summary())
    metadata_records = list(metadata_repository._metadata_records.values())
    for record in metadata_records:
        source_counts[record.source_system] += 0

    rows = []
    for source, count in sorted(source_counts.items()):
        source_records = [record for record in metadata_records if record.source_system == source]
        stale_count = sum(1 for record in source_records if record.freshness_status == "Stale")
        rows.append(
            {
                "Source System": source,
                "Entity Count": count,
                "Last Sync": max((record.sync_time for record in source_records), default=""),
                "Health": "Attention" if stale_count else "Healthy",
                "Error Count": stale_count,
            }
        )
    _dataframe(rows, "No source systems have reported entity or metadata coverage.")


def _broken_lineage_count(metadata_repository: MetadataCatalogRepository, entity_repository: EntityRepository) -> int:
    broken = 0
    for edge in metadata_repository.get_lineage_edges():
        if not entity_repository.get_entity(edge.source_entity_id) or not entity_repository.get_entity(edge.target_entity_id):
            broken += 1
    return broken


def render_section() -> None:
    st.title("Enterprise Data Fabric")
    st.caption("Program 1.6 - Administration workspace for the Enterprise Data Fabric Core")

    (
        entity_service,
        entity_repository,
        identity_repository,
        ontology_repository,
        metadata_repository,
        correlation_repository,
    ) = _repositories()

    _render_fabric_health(entity_service, identity_repository, metadata_repository, correlation_repository)

    tabs = st.tabs(
        [
            "Entity Registry",
            "Identity Resolution",
            "Ontology Explorer",
            "Metadata Health",
            "Lineage Explorer",
            "Correlation Center",
            "Data Quality",
            "Source Systems",
            "Fabric Health",
        ]
    )
    with tabs[0]:
        _render_entity_registry(entity_service)
    with tabs[1]:
        _render_identity_resolution(identity_repository)
    with tabs[2]:
        _render_ontology_explorer(ontology_repository)
    with tabs[3]:
        _render_metadata_health(metadata_repository)
    with tabs[4]:
        _render_lineage_explorer(metadata_repository, entity_repository)
    with tabs[5]:
        _render_correlation_center(correlation_repository)
    with tabs[6]:
        _render_data_quality(entity_service, metadata_repository)
    with tabs[7]:
        _render_source_systems(entity_service, metadata_repository)
    with tabs[8]:
        _render_fabric_health(entity_service, identity_repository, metadata_repository, correlation_repository)


def render_page() -> None:
    st.set_page_config(page_title="Enterprise Data Fabric", layout="wide")
    _require_authorized_role()
    _render_sidebar()
    render_section()


if __name__ == "__main__":
    render_page()
