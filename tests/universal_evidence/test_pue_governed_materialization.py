from __future__ import annotations

from dataclasses import dataclass

import pytest

from data_fabric.contracts import EnterpriseRelationship, EntityType, RelationshipType
from data_fabric.foundation import TenantContext
from data_fabric.identity import InMemoryIdentityResolver
from data_fabric.registry import InMemoryEntityRegistry, InMemoryRelationshipRegistry
from enterprise_registry.canonical_service import EnterpriseRegistryService
from enterprise_registry.knowledge_graph import EnterpriseKnowledgeGraphService
from enterprise_registry.relationship_intelligence import RelationshipIntelligenceService
from universal_evidence.governance import MappingDecisionState
from universal_evidence.pilot.materialization import (
    GovernedEntityMaterializationService,
    MaterializationObservation,
    MaterializationState,
)

ORG = "org-act006"
TENANT = "tenant-act006"


@dataclass
class Activation:
    stage: int = 2
    reason_codes: tuple = ()


def _service(context: TenantContext):
    entities = InMemoryEntityRegistry()
    relationships = InMemoryRelationshipRegistry()
    registry = EnterpriseRegistryService(
        context,
        role="operations",
        entities=entities,
        identities=InMemoryIdentityResolver(),
        relationships=relationships,
    )
    return registry, relationships


def _observation(concept, value, *, state=MappingDecisionState.CONFIRMED, row=2, **overrides):
    organization_id = overrides.pop("organization_id", ORG)
    tenant_id = overrides.pop("tenant_id", TENANT)
    return MaterializationObservation(
        semantic_concept_id=concept,
        normalized_value=value,
        mapping_decision_id=f"decision-{concept}-{row}",
        mapping_decision_state=state,
        normalization_fingerprint=f"normalized-{concept}-{row}",
        source_id="upload-1",
        file_id="fixture.csv",
        sheet_id="sheet-1",
        row_number=row,
        analysis_id="analysis-1",
        prospect_id="prospect-1",
        organization_id=organization_id,
        tenant_id=tenant_id,
        source_identifier=overrides.pop("source_identifier", None),
        **overrides,
    )


def _fixture():
    return (
        _observation("technology.provider", "AWS", source_identifier="aws"),
        _observation("cloud.resource_id", "i-test123", source_identifier="i-test123"),
        _observation("application.name", "Checkout", source_identifier="checkout"),
        _observation(
            "business_service.name", "Order Processing", source_identifier="order-processing"
        ),
        _observation("owner.name", "Alice", source_identifier="alice"),
        _observation("cost_center.name", "CC-1001", source_identifier="cc-1001"),
    )


def test_governed_fixture_materializes_into_existing_registries_and_graph_idempotently():
    context = TenantContext(ORG, TENANT)
    registry, relationships = _service(context)
    materializer = GovernedEntityMaterializationService(registry, relationships)

    first = materializer.materialize(_fixture(), context=context, activation=Activation())
    second = materializer.materialize(_fixture(), context=context, activation=Activation())

    assert len(first.entities) == 6
    assert len(registry.list_entities()) == 6
    assert len(relationships.search_relationships(organization_id=ORG)) == 4
    assert len(second.entities) == 6
    assert len(relationships.search_relationships(organization_id=ORG)) == 4
    assert all(item.proposal_fingerprint for item in first.entity_proposals)

    graph = EnterpriseKnowledgeGraphService(
        registry,
        RelationshipIntelligenceService(
            context,
            role="auditor",
            entities=registry.list_entities(),
            relationships=relationships.search_relationships(organization_id=ORG),
        ),
    )
    checkout = next(item for item in registry.list_entities() if item.name == "Checkout")
    assert graph.find_entity(checkout.canonical_id).relationships


@pytest.mark.parametrize("state", [MappingDecisionState.UNDECIDED, MappingDecisionState.REJECTED])
def test_candidate_or_rejected_mapping_cannot_materialize(state):
    context = TenantContext(ORG, TENANT)
    registry, relationships = _service(context)
    report = GovernedEntityMaterializationService(registry, relationships).materialize(
        [_observation("application.name", "Checkout", state=state)],
        context=context,
        activation=Activation(),
    )
    assert report.entities == ()
    assert report.entity_proposals[0].state is MaterializationState.BLOCKED


def test_stale_and_unsupported_observations_fail_closed():
    context = TenantContext(ORG, TENANT)
    registry, relationships = _service(context)
    rows = [
        _observation("application.name", "Checkout", stale=True),
        _observation("unknown.column", "Mystery"),
    ]
    report = GovernedEntityMaterializationService(registry, relationships).materialize(
        rows, context=context, activation=Activation()
    )
    assert {item.state for item in report.entity_proposals} == {
        MaterializationState.STALE,
        MaterializationState.UNSUPPORTED,
    }


def test_identity_includes_entity_type_and_tenant_scope():
    context = TenantContext(ORG, TENANT)
    registry, relationships = _service(context)
    app = GovernedEntityMaterializationService(registry, relationships).materialize(
        [_observation("application.name", "Payments", source_identifier="payments-app")],
        context=context,
        activation=Activation(),
    )
    service = GovernedEntityMaterializationService(registry, relationships).materialize(
        [_observation("business_service.name", "Payments", source_identifier="payments-service")],
        context=context,
        activation=Activation(),
    )
    assert app.entities[0].canonical_id != service.entities[0].canonical_id
    with pytest.raises(ValueError, match="organization or tenant"):
        GovernedEntityMaterializationService(registry, relationships).materialize(
            [_observation("application.name", "Foreign", organization_id="other-org")],
            context=context,
            activation=Activation(),
        )


def test_existing_owner_precedence_surfaces_conflict_without_overwrite():
    context = TenantContext(ORG, TENANT)
    registry, relationships = _service(context)
    app = registry.register_entity(
        EnterpriseEntityFactory.entity(context, EntityType.APPLICATION, "Checkout", "checkout")
    )
    alice = registry.register_entity(
        EnterpriseEntityFactory.entity(context, EntityType.OWNER, "Alice", "alice")
    )
    relationships.register_relationship(
        EnterpriseRelationship(
            id="existing-owner",
            relationship_type=RelationshipType.OWNED_BY,
            source_entity_id=app.id,
            target_entity_id=alice.id,
            organization_id=ORG,
            tenant_id=TENANT,
            source_system="cmdb",
            source_identifier="cmdb-owner",
        )
    )
    report = GovernedEntityMaterializationService(registry, relationships).materialize(
        [
            _observation("application.name", "Checkout", source_identifier="checkout"),
            _observation("owner.name", "Bob", source_identifier="bob"),
        ],
        context=context,
        activation=Activation(),
    )
    assert any(
        item.state is MaterializationState.CONFLICT for item in report.relationship_proposals
    )
    assert len(relationships.search_relationships(organization_id=ORG)) == 1
    assert any(entity.name == "Alice" for entity in registry.list_entities())
    assert not any(
        edge.target_entity_id
        == next(entity.id for entity in registry.list_entities() if entity.name == "Bob")
        for edge in relationships.search_relationships(organization_id=ORG)
    )


class EnterpriseEntityFactory:
    @staticmethod
    def entity(context, entity_type, name, source_identifier):
        from enterprise_registry.canonical import enterprise_entity_from_source

        return enterprise_entity_from_source(
            context=context,
            entity_type=entity_type,
            source_system="cmdb",
            source_entity_id=source_identifier,
            canonical_name=name,
        )
