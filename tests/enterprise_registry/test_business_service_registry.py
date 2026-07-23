from __future__ import annotations

from dataclasses import replace

import pytest

from data_fabric.contracts import (
    EnterpriseEntity,
    EnterpriseRelationship,
    EntityIdentity,
    EntityType,
    RelationshipType,
)
from data_fabric.foundation import DataFabricTenantBoundaryError, TenantContext
from data_fabric.registry import InMemoryRelationshipRegistry
from data_fabric.semantic import InMemoryOntologyRegistry, SemanticConcept
from enterprise_registry import (
    BusinessServiceLifecycle,
    BusinessServiceNotFoundError,
    BusinessServiceRegistry,
    BusinessServiceRelationshipError,
    BusinessServiceValidationError,
    BusinessServiceVersionConflictError,
    DuplicateBusinessServiceError,
    InMemoryBusinessServiceRepository,
    canonical_business_service_id,
    create_business_service,
)


@pytest.fixture
def context() -> TenantContext:
    return TenantContext("org-1", "tenant-a")


@pytest.fixture
def repository() -> InMemoryBusinessServiceRepository:
    return InMemoryBusinessServiceRepository()


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
        "owner_name": "Payments Operations",
        "cost_center": "cc-100",
        "source_system": "service-catalog",
        "source_id": "svc-100",
        "aliases": ("payment-service",),
    }
    values.update(overrides)
    return create_business_service(**values)


def target_entity(
    context: TenantContext,
    *,
    entity_id: str = "application-1",
    entity_type: EntityType = EntityType.APPLICATION,
) -> EnterpriseEntity:
    return EnterpriseEntity(
        id=entity_id,
        canonical_id=f"{entity_type.value}:{entity_id}",
        entity_type=entity_type,
        name="Payment Application",
        source_system="application-catalog",
        source_identifier=entity_id,
        organization_id=context.organization_id,
        tenant_id=context.tenant_id,
    )


def test_successful_registration_reuses_canonical_contracts(
    context: TenantContext,
    repository: InMemoryBusinessServiceRepository,
) -> None:
    registry = BusinessServiceRegistry(context, repository)

    registered = registry.register(service(context))

    assert registered.entity.entity_type is EntityType.BUSINESS_SERVICE
    assert registered.entity.identity is not None
    assert registered.owner.owner_id == "owner-1"
    assert registered.cost_center == "cc-100"
    assert registered.version == 1
    assert registered.canonical_id == canonical_business_service_id(
        context,
        "payments",
    )
    assert registry.get_by_canonical_id(registered.canonical_id) == registered
    assert registry.get_by_business_service_id("PAYMENTS") == registered


def test_canonical_identity_is_deterministic_and_tenant_scoped() -> None:
    tenant_a = TenantContext("org-1", "tenant-a")
    tenant_b = TenantContext("org-1", "tenant-b")

    first = service(tenant_a)
    repeated = service(tenant_a, source_id="different-source")
    other_tenant = service(tenant_b)

    assert first.canonical_id == repeated.canonical_id
    assert first.canonical_id != other_tenant.canonical_id


def test_duplicate_canonical_and_source_identity_are_rejected(
    context: TenantContext,
    repository: InMemoryBusinessServiceRepository,
) -> None:
    registry = BusinessServiceRegistry(context, repository)
    registry.register(service(context))

    with pytest.raises(DuplicateBusinessServiceError):
        registry.register(service(context))
    with pytest.raises(DuplicateBusinessServiceError):
        registry.register(
            service(
                context,
                business_service_id="settlements",
                name="Settlements",
            )
        )


def test_source_identity_must_match_canonical_entity(
    context: TenantContext,
) -> None:
    valid = service(context)
    invalid_identity = replace(
        valid.entity.identity,
        source_identifier="different-source",
    )

    with pytest.raises(BusinessServiceValidationError):
        replace(
            valid,
            entity=replace(valid.entity, identity=invalid_identity),
        )


def test_tenant_and_organization_isolation_hide_reads(
    context: TenantContext,
    repository: InMemoryBusinessServiceRepository,
) -> None:
    registered = BusinessServiceRegistry(context, repository).register(service(context))
    other_tenant = BusinessServiceRegistry(
        TenantContext("org-1", "tenant-b"),
        repository,
    )
    other_organization = BusinessServiceRegistry(
        TenantContext("org-2", "tenant-a"),
        repository,
    )

    with pytest.raises(BusinessServiceNotFoundError):
        other_tenant.get_by_canonical_id(registered.canonical_id)
    with pytest.raises(BusinessServiceNotFoundError):
        other_organization.get_by_business_service_id("payments")


def test_cross_tenant_registration_is_rejected(
    context: TenantContext,
    repository: InMemoryBusinessServiceRepository,
) -> None:
    registry = BusinessServiceRegistry(
        TenantContext("org-1", "tenant-b"),
        repository,
    )

    with pytest.raises(DataFabricTenantBoundaryError):
        registry.register(service(context))


def test_domain_query_and_alias_resolution_are_tenant_scoped(
    context: TenantContext,
    repository: InMemoryBusinessServiceRepository,
) -> None:
    registry = BusinessServiceRegistry(context, repository)
    payments = registry.register(service(context))
    registry.register(
        service(
            context,
            business_service_id="support",
            name="Customer Support",
            business_domain="customer-domain",
            source_id="svc-200",
            aliases=("support-service",),
        )
    )

    assert registry.resolve_alias("PAYMENT SERVICE") == payments
    assert [item.business_service_id for item in registry.list_services()] == [
        "payments",
        "support",
    ]
    assert [
        item.business_service_id
        for item in registry.list_services(business_domain="PAYMENTS-DOMAIN")
    ] == ["payments"]


def test_metadata_update_increments_version_and_preserves_identity(
    context: TenantContext,
    repository: InMemoryBusinessServiceRepository,
) -> None:
    registry = BusinessServiceRegistry(context, repository)
    registered = registry.register(service(context))

    updated = registry.update_metadata(
        registered.canonical_id,
        expected_version=1,
        name="Global Payments",
        criticality="high",
        attributes={"region": "global"},
    )

    assert updated.version == 2
    assert updated.name == "Global Payments"
    assert updated.criticality.value == "high"
    assert updated.attributes["region"] == "global"
    assert updated.canonical_id == registered.canonical_id
    assert updated.source_id == registered.source_id
    with pytest.raises(BusinessServiceVersionConflictError):
        repository.update(context, updated, expected_version=1)


def test_lifecycle_transitions_and_archive_visibility(
    context: TenantContext,
    repository: InMemoryBusinessServiceRepository,
) -> None:
    registry = BusinessServiceRegistry(context, repository)
    registered = registry.register(service(context))
    active = registry.transition_lifecycle(
        registered.canonical_id,
        BusinessServiceLifecycle.ACTIVE,
        expected_version=1,
    )

    with pytest.raises(BusinessServiceValidationError):
        registry.transition_lifecycle(
            active.canonical_id,
            BusinessServiceLifecycle.ARCHIVED,
            expected_version=2,
        )
    retired = registry.transition_lifecycle(
        active.canonical_id,
        BusinessServiceLifecycle.RETIRED,
        expected_version=2,
    )
    archived = registry.transition_lifecycle(
        retired.canonical_id,
        BusinessServiceLifecycle.ARCHIVED,
        expected_version=3,
    )

    assert archived.active is False
    with pytest.raises(BusinessServiceNotFoundError):
        registry.get_by_canonical_id(archived.canonical_id)
    assert (
        registry.get_by_canonical_id(
            archived.canonical_id,
            include_inactive=True,
        ).lifecycle_state
        is BusinessServiceLifecycle.ARCHIVED
    )


def test_active_tenant_ontology_controls_business_domain(
    context: TenantContext,
    repository: InMemoryBusinessServiceRepository,
) -> None:
    ontology = InMemoryOntologyRegistry()
    ontology.register_concept(
        SemanticConcept(
            concept_id="payments-domain",
            canonical_name="Payments Domain",
            display_name="Payments Domain",
            description="Payments capability domain",
            concept_type="capability",
            parent_concept_id=None,
            organization_id=context.organization_id,
            tenant_id=context.tenant_id,
        )
    )
    registry = BusinessServiceRegistry(context, repository, ontology=ontology)

    assert registry.register(service(context)).business_domain == "payments-domain"
    with pytest.raises(BusinessServiceValidationError):
        registry.register(
            service(
                context,
                business_service_id="support",
                name="Support",
                business_domain="unknown-domain",
                source_id="svc-200",
            )
        )


def test_ownership_and_required_scope_are_validated(
    context: TenantContext,
) -> None:
    with pytest.raises(BusinessServiceValidationError):
        service(context, owner_id="")
    with pytest.raises(BusinessServiceValidationError):
        service(context, business_domain="")


def test_relationship_compatibility_reuses_existing_registry(
    context: TenantContext,
    repository: InMemoryBusinessServiceRepository,
) -> None:
    relationships = InMemoryRelationshipRegistry()
    registry = BusinessServiceRegistry(
        context,
        repository,
        relationships=relationships,
    )
    registered = registry.register(service(context))
    target = target_entity(context)
    relationship = EnterpriseRelationship(
        id="relationship-1",
        relationship_type=RelationshipType.DEPENDS_ON,
        source_entity_id=registered.canonical_id,
        target_entity_id=target.id,
        organization_id=context.organization_id,
        tenant_id=context.tenant_id,
        source_system="service-catalog",
        source_identifier="rel-100",
    )

    stored = registry.register_relationship(relationship, target=target)

    assert stored.relationship_type is RelationshipType.DEPENDS_ON
    assert registry.list_relationships(registered.canonical_id) == [stored]


def test_invalid_and_cross_tenant_relationships_are_rejected(
    context: TenantContext,
    repository: InMemoryBusinessServiceRepository,
) -> None:
    registry = BusinessServiceRegistry(
        context,
        repository,
        relationships=InMemoryRelationshipRegistry(),
    )
    registered = registry.register(service(context))
    application = target_entity(context)
    owner = target_entity(
        context,
        entity_id="owner-1",
        entity_type=EntityType.OWNER,
    )
    invalid_type = EnterpriseRelationship(
        id="relationship-1",
        relationship_type=RelationshipType.RUNS_ON,
        source_entity_id=registered.canonical_id,
        target_entity_id=application.id,
        organization_id=context.organization_id,
        tenant_id=context.tenant_id,
        source_system="service-catalog",
        source_identifier="rel-100",
    )
    cross_tenant = replace(
        invalid_type,
        id="relationship-2",
        relationship_type=RelationshipType.OWNED_BY,
        target_entity_id=owner.id,
        tenant_id="tenant-b",
    )

    with pytest.raises(BusinessServiceRelationshipError):
        registry.register_relationship(invalid_type, target=application)
    with pytest.raises(DataFabricTenantBoundaryError):
        registry.register_relationship(cross_tenant, target=owner)


def test_business_service_model_rejects_incorrect_canonical_type(
    context: TenantContext,
) -> None:
    valid = service(context)
    invalid_entity = replace(
        valid.entity,
        entity_type=EntityType.APPLICATION,
        identity=EntityIdentity(
            id=valid.canonical_id,
            canonical_id=valid.canonical_id,
            source_system=valid.source_system,
            source_identifier=valid.source_id,
            organization_id=valid.organization_id,
            tenant_id=valid.tenant_id,
        ),
    )

    with pytest.raises(BusinessServiceValidationError):
        replace(valid, entity=invalid_entity)
