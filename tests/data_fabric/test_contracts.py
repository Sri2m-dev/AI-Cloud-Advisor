from datetime import datetime, timezone

import pytest

from data_fabric.contracts import (
    EnterpriseEntity,
    EnterpriseRelationship,
    EntityIdentity,
    EntityLineage,
    EntityOwnership,
    EntityProvenance,
    EntityQuality,
    EntityType,
    EntityVersion,
    RelationshipType,
)


def test_entity_type_values_preserve_p3_baseline() -> None:
    assert {
        "business_capability",
        "business_service",
        "application",
        "technology",
        "cloud_resource",
        "saas_application",
        "vendor",
        "contract",
        "cost_center",
        "department",
        "owner",
        "project",
        "environment",
        "business_process",
        "risk",
        "recommendation",
        "approval",
        "policy",
        "evidence",
    } <= {item.value for item in EntityType}


def test_relationship_type_values_preserve_p3_baseline() -> None:
    assert {
        "depends_on",
        "runs_on",
        "owned_by",
        "supplied_by",
        "funds",
        "impacts",
        "targets",
        "monitors",
        "governs",
        "approves",
        "evidences",
        "associated_with",
    } <= {item.value for item in RelationshipType}


def test_enterprise_entity_accepts_string_enum_and_common_fields() -> None:
    entity = EnterpriseEntity(
        id="ent-1",
        canonical_id="application:checkout",
        entity_type="application",
        name="Checkout",
        source_system="servicenow",
        source_identifier="app-123",
        organization_id="org-1",
        tenant_id="tenant-1",
        confidence_score=0.92,
        quality_score=0.88,
        tags=["tier-1"],
        metadata={"criticality": "high"},
    )

    assert entity.entity_type is EntityType.APPLICATION
    assert entity.canonical_id == "application:checkout"
    assert entity.metadata["criticality"] == "high"
    assert entity.tags == ["tier-1"]


def test_enterprise_relationship_accepts_string_enum() -> None:
    relationship = EnterpriseRelationship(
        id="rel-1",
        relationship_type="runs_on",
        source_entity_id="app-1",
        target_entity_id="resource-1",
        organization_id="org-1",
        confidence_score=0.9,
        quality_score=0.85,
    )

    assert relationship.relationship_type is RelationshipType.RUNS_ON
    assert relationship.source_entity_id == "app-1"
    assert relationship.target_entity_id == "resource-1"


def test_nested_contracts_can_attach_to_entity() -> None:
    now = datetime.now(timezone.utc)
    identity = EntityIdentity(
        id="identity-1",
        canonical_id="application:checkout",
        source_system="servicenow",
        source_identifier="app-123",
        organization_id="org-1",
        aliases=["checkout-service"],
    )
    lineage = EntityLineage(
        connector="servicenow",
        raw_record_id="raw-1",
        normalized_record_id="norm-1",
    )
    provenance = EntityProvenance(
        source_system="servicenow",
        source_identifier="app-123",
        collection_method="connector_sync",
        captured_at=now,
    )
    version = EntityVersion(version=2, effective_from=now, change_reason="source refresh")
    quality = EntityQuality(completeness=0.9, freshness=0.8, trust_score=0.85)
    ownership = EntityOwnership(owner_id="owner-1", owner_name="Platform Team")

    entity = EnterpriseEntity(
        id="ent-1",
        canonical_id="application:checkout",
        entity_type=EntityType.APPLICATION,
        name="Checkout",
        source_system="servicenow",
        source_identifier="app-123",
        organization_id="org-1",
        identity=identity,
        lineage=lineage,
        provenance=provenance,
        entity_version=version,
        quality=quality,
        ownership=ownership,
    )

    assert entity.identity is identity
    assert entity.lineage is lineage
    assert entity.provenance is provenance
    assert entity.entity_version is version
    assert entity.quality is quality
    assert entity.ownership is ownership


def test_metadata_defaults_are_not_shared() -> None:
    first = EnterpriseEntity(
        id="ent-1",
        canonical_id="application:first",
        entity_type=EntityType.APPLICATION,
        name="First",
        source_system="source",
        source_identifier="first",
        organization_id="org-1",
    )
    second = EnterpriseEntity(
        id="ent-2",
        canonical_id="application:second",
        entity_type=EntityType.APPLICATION,
        name="Second",
        source_system="source",
        source_identifier="second",
        organization_id="org-1",
    )

    first.metadata["only_first"] = True

    assert "only_first" not in second.metadata


def test_score_validation_rejects_out_of_range_values() -> None:
    with pytest.raises(ValueError):
        EnterpriseEntity(
            id="ent-1",
            canonical_id="application:bad",
            entity_type=EntityType.APPLICATION,
            name="Bad",
            source_system="source",
            source_identifier="bad",
            organization_id="org-1",
            confidence_score=1.2,
        )

    with pytest.raises(ValueError):
        EntityQuality(trust_score=-0.1)
