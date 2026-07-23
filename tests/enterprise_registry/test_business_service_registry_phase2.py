from __future__ import annotations

from dataclasses import replace

import pytest

from data_fabric.contracts import (
    EnterpriseEntity,
    EnterpriseRelationship,
    EntityLineage,
    EntityProvenance,
    EntityQuality,
    EntityType,
    RelationshipType,
)
from data_fabric.foundation import DataFabricTenantBoundaryError, TenantContext
from data_fabric.lineage import InMemoryLineageTracker, InMemoryProvenanceTracker
from data_fabric.quality import InMemoryDataQualityEvaluator
from data_fabric.registry import InMemoryRelationshipRegistry
from data_fabric.semantic import InMemoryOntologyRegistry, SemanticConcept
from data_fabric.versioning import InMemoryVersionStore
from enterprise_registry import (
    BusinessServiceLifecycle,
    BusinessServiceNotFoundError,
    BusinessServiceRegistry,
    BusinessServiceRelationshipError,
    BusinessServiceValidationError,
    InMemoryBusinessServiceRepository,
    create_business_service,
)


@pytest.fixture
def context() -> TenantContext:
    return TenantContext("org-1", "tenant-a")


def service(context: TenantContext, **overrides):
    values = {
        "context": context,
        "business_service_id": "payments",
        "name": "Payments",
        "description": "Processes customer payments",
        "business_domain": "payments-domain",
        "service_type": "customer_facing",
        "criticality": "critical",
        "owner_id": "owner-1",
        "source_system": "service-catalog",
        "source_id": "svc-100",
    }
    values.update(overrides)
    return create_business_service(**values)


def target(
    context: TenantContext,
    entity_type: EntityType,
    sequence: int,
) -> EnterpriseEntity:
    return EnterpriseEntity(
        id=f"target-{sequence}",
        canonical_id=f"{entity_type.value}:target-{sequence}",
        entity_type=entity_type,
        name=f"Target {sequence}",
        source_system="enterprise-catalog",
        source_identifier=f"target-{sequence}",
        organization_id=context.organization_id,
        tenant_id=context.tenant_id,
    )


def test_lifecycle_convenience_operations_are_controlled(
    context: TenantContext,
) -> None:
    registry = BusinessServiceRegistry(
        context,
        InMemoryBusinessServiceRepository(),
    )
    registered = registry.register(service(context))

    active = registry.activate(registered.canonical_id, expected_version=1)
    suspended = registry.deactivate(active.canonical_id, expected_version=2)
    reactivated = registry.activate(suspended.canonical_id, expected_version=3)

    assert reactivated.lifecycle_state is BusinessServiceLifecycle.ACTIVE
    assert reactivated.version == 4
    with pytest.raises(BusinessServiceValidationError):
        registry.archive(reactivated.canonical_id, expected_version=4)


def test_archive_hides_service_from_default_lookup(
    context: TenantContext,
) -> None:
    registry = BusinessServiceRegistry(
        context,
        InMemoryBusinessServiceRepository(),
    )
    registered = registry.register(service(context))
    archived = registry.archive(registered.canonical_id, expected_version=1)

    with pytest.raises(BusinessServiceNotFoundError):
        registry.get_by_canonical_id(archived.canonical_id)
    assert registry.get_by_canonical_id(
        archived.canonical_id,
        include_inactive=True,
    ).lifecycle_state is BusinessServiceLifecycle.ARCHIVED


def test_owner_assignment_is_versioned_and_validated(
    context: TenantContext,
) -> None:
    versions = InMemoryVersionStore()
    registry = BusinessServiceRegistry(
        context,
        InMemoryBusinessServiceRepository(),
        versions=versions,
    )
    registered = registry.register(service(context))

    updated = registry.assign_owner(
        registered.canonical_id,
        owner_id="owner-2",
        owner_name="Treasury",
        owner_email="treasury@example.com",
        department_id="finance",
        cost_center_id="cc-200",
        accountability="accountable",
        expected_version=1,
    )

    assert updated.owner.owner_id == "owner-2"
    assert updated.owner.department_id == "finance"
    assert updated.cost_center == "cc-200"
    assert [snapshot.version for snapshot in registry.list_versions(updated.canonical_id)] == [
        1,
        2,
    ]
    with pytest.raises(BusinessServiceValidationError):
        registry.assign_owner(
            updated.canonical_id,
            owner_id=" ",
            expected_version=2,
        )


def test_cross_tenant_owner_change_is_hidden(
    context: TenantContext,
) -> None:
    repository = InMemoryBusinessServiceRepository()
    registered = BusinessServiceRegistry(context, repository).register(service(context))
    other_registry = BusinessServiceRegistry(
        TenantContext("org-1", "tenant-b"),
        repository,
    )

    with pytest.raises(BusinessServiceNotFoundError):
        other_registry.assign_owner(
            registered.canonical_id,
            owner_id="owner-2",
            expected_version=1,
        )


def test_metadata_and_lifecycle_changes_create_temporal_versions(
    context: TenantContext,
) -> None:
    versions = InMemoryVersionStore()
    registry = BusinessServiceRegistry(
        context,
        InMemoryBusinessServiceRepository(),
        versions=versions,
    )
    registered = registry.register(service(context))
    updated = registry.update_metadata(
        registered.canonical_id,
        expected_version=1,
        description="Global payment processing",
        attributes={"tier": "one"},
    )
    active = registry.activate(updated.canonical_id, expected_version=2)

    snapshots = registry.list_versions(active.canonical_id)
    assert [snapshot.version for snapshot in snapshots] == [1, 2, 3]
    assert snapshots[1].payload["entity_version"]["supersedes_version"] == 1
    assert snapshots[2].payload["metadata"]["lifecycle_state"] == "active"


@pytest.mark.parametrize(
    ("entity_type", "relationship_type"),
    [
        (EntityType.APPLICATION, RelationshipType.DEPENDS_ON),
        (EntityType.TECHNOLOGY, RelationshipType.RUNS_ON),
        (EntityType.OWNER, RelationshipType.OWNED_BY),
        (EntityType.DEPARTMENT, RelationshipType.ASSOCIATED_WITH),
        (EntityType.COST_CENTER, RelationshipType.FUNDS),
        (EntityType.BUSINESS_CAPABILITY, RelationshipType.ASSOCIATED_WITH),
    ],
)
def test_supported_canonical_relationships(
    context: TenantContext,
    entity_type: EntityType,
    relationship_type: RelationshipType,
) -> None:
    relationship_registry = InMemoryRelationshipRegistry()
    version_store = InMemoryVersionStore()
    registry = BusinessServiceRegistry(
        context,
        InMemoryBusinessServiceRepository(),
        relationships=relationship_registry,
        versions=version_store,
    )
    registered = registry.register(service(context))
    relationship_target = target(context, entity_type, 1)
    relationship = EnterpriseRelationship(
        id=f"rel-{entity_type.value}",
        relationship_type=relationship_type,
        source_entity_id=registered.canonical_id,
        target_entity_id=relationship_target.id,
        organization_id=context.organization_id,
        tenant_id=context.tenant_id,
        source_system="service-catalog",
        source_identifier=f"rel-{entity_type.value}",
    )

    stored = registry.register_relationship(
        relationship,
        target=relationship_target,
    )

    assert stored == relationship
    assert version_store.list_relationship_versions(
        stored.id,
        organization_id=context.organization_id,
        tenant_id=context.tenant_id,
    )[0].version == 1


def test_cross_tenant_and_invalid_relationships_are_rejected(
    context: TenantContext,
) -> None:
    registry = BusinessServiceRegistry(
        context,
        InMemoryBusinessServiceRepository(),
        relationships=InMemoryRelationshipRegistry(),
    )
    registered = registry.register(service(context))
    other_context = TenantContext("org-1", "tenant-b")
    wrong_tenant_target = target(other_context, EntityType.APPLICATION, 1)
    cross_tenant = EnterpriseRelationship(
        id="cross-tenant",
        relationship_type=RelationshipType.DEPENDS_ON,
        source_entity_id=registered.canonical_id,
        target_entity_id=wrong_tenant_target.id,
        organization_id=context.organization_id,
        tenant_id=context.tenant_id,
    )
    invalid_target = target(context, EntityType.VENDOR, 2)
    invalid = replace(
        cross_tenant,
        id="invalid",
        target_entity_id=invalid_target.id,
    )

    with pytest.raises(DataFabricTenantBoundaryError):
        registry.register_relationship(cross_tenant, target=wrong_tenant_target)
    with pytest.raises(BusinessServiceRelationshipError):
        registry.register_relationship(invalid, target=invalid_target)


def test_ontology_controls_domain_service_type_and_criticality(
    context: TenantContext,
) -> None:
    ontology = InMemoryOntologyRegistry()
    ontology.register_concept(
        SemanticConcept(
            concept_id="payments-domain",
            canonical_name="Payments",
            display_name="Payments",
            description="Payments domain semantics",
            concept_type="capability",
            parent_concept_id=None,
            organization_id=context.organization_id,
            tenant_id=context.tenant_id,
            attributes={
                "service_types": ("customer_facing",),
                "criticalities": ("critical", "high"),
            },
        )
    )
    registry = BusinessServiceRegistry(
        context,
        InMemoryBusinessServiceRepository(),
        ontology=ontology,
    )

    assert registry.register(service(context)).service_type.value == "customer_facing"
    with pytest.raises(BusinessServiceValidationError):
        registry.register(
            service(
                context,
                business_service_id="shared-payments",
                source_id="svc-200",
                service_type="shared",
            )
        )


def test_ontology_controls_relationship_semantics(
    context: TenantContext,
) -> None:
    ontology = InMemoryOntologyRegistry()
    ontology.register_concept(
        SemanticConcept(
            concept_id="payments-domain",
            canonical_name="Payments",
            display_name="Payments",
            description="Payments domain semantics",
            concept_type="capability",
            parent_concept_id=None,
            organization_id=context.organization_id,
            tenant_id=context.tenant_id,
            attributes={
                "relationship_types": {
                    "application": ("associated_with",),
                },
            },
        )
    )
    registry = BusinessServiceRegistry(
        context,
        InMemoryBusinessServiceRepository(),
        ontology=ontology,
        relationships=InMemoryRelationshipRegistry(),
    )
    registered = registry.register(service(context))
    application = target(context, EntityType.APPLICATION, 1)
    disallowed = EnterpriseRelationship(
        id="ontology-rejected",
        relationship_type=RelationshipType.DEPENDS_ON,
        source_entity_id=registered.canonical_id,
        target_entity_id=application.id,
        organization_id=context.organization_id,
        tenant_id=context.tenant_id,
    )

    with pytest.raises(BusinessServiceRelationshipError):
        registry.register_relationship(disallowed, target=application)


def test_lineage_provenance_and_contracts_are_preserved(
    context: TenantContext,
) -> None:
    lineage = InMemoryLineageTracker()
    provenance = InMemoryProvenanceTracker()
    contract_lineage = EntityLineage(
        connector="catalog",
        raw_record_id="raw-100",
    )
    contract_provenance = EntityProvenance(
        source_system="service-catalog",
        source_identifier="svc-100",
        collection_method="catalog_sync",
    )
    registered = BusinessServiceRegistry(
        context,
        InMemoryBusinessServiceRepository(),
        lineage=lineage,
        provenance=provenance,
    ).register(
        service(
            context,
            lineage=contract_lineage,
            provenance=contract_provenance,
        )
    )

    assert registered.entity.lineage == contract_lineage
    assert registered.entity.provenance == contract_provenance
    assert lineage.trace_lineage_by_entity_id(registered.canonical_id).events[0].event_type == (
        "canonicalization"
    )
    assert "service-catalog/svc-100" in provenance.explain_entity_origin(
        registered.canonical_id
    )


def test_quality_and_trust_use_existing_evaluator(
    context: TenantContext,
) -> None:
    registry = BusinessServiceRegistry(
        context,
        InMemoryBusinessServiceRepository(),
        quality=InMemoryDataQualityEvaluator(),
    )
    registered = registry.register(
        service(
            context,
            quality=EntityQuality(trust_score=0.9),
        )
    )

    assessment = registry.assess_quality(
        registered.canonical_id,
        observed_at=registered.updated_at,
    )

    assert assessment.subject_id == registered.canonical_id
    assert assessment.organization_id == context.organization_id
    assert 0.0 <= assessment.trust_score.final_score <= 100.0


def test_deterministic_lookup_remains_stable_after_updates(
    context: TenantContext,
) -> None:
    registry = BusinessServiceRegistry(
        context,
        InMemoryBusinessServiceRepository(),
    )
    registered = registry.register(service(context, aliases=("payment-service",)))
    updated = registry.assign_owner(
        registered.canonical_id,
        owner_id="owner-2",
        expected_version=1,
    )

    assert registry.get_by_business_service_id("PAYMENTS") == updated
    assert registry.resolve_alias("PAYMENT SERVICE") == updated
