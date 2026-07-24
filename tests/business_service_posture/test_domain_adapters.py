from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from uuid import UUID

import pytest

from business_service_posture import (
    AmbiguousPostureAttributionError,
    BusinessServiceAttributionResolver,
    BusinessServicePostureService,
    DomainPostureAdapters,
    InMemoryBusinessServicePostureRepository,
    MissingPostureAttributionError,
    PostureDimension,
    PostureEvidenceReference,
    UnsupportedPostureAttributionError,
)
from core.digital_twin.technology.cost_signal import CostSignal
from core.digital_twin.technology.health_signal import HealthSignal
from core.digital_twin.technology.risk_signal import RiskSignal
from data_fabric.contracts import (
    EnterpriseEntity,
    EnterpriseRelationship,
    EntityType,
    RelationshipType,
)
from data_fabric.foundation import DataFabricTenantBoundaryError, TenantContext
from data_fabric.registry import InMemoryEntityRegistry, InMemoryRelationshipRegistry
from enterprise_registry import (
    BusinessServiceRegistry,
    InMemoryBusinessServiceRepository,
    create_business_service,
)

TECHNOLOGY_ID = UUID("6fb9153e-aea5-4a89-b634-553ba0965ef0")
OBSERVED_AT = datetime(2026, 7, 24, 2, 0, tzinfo=timezone.utc)


@pytest.fixture
def adapter_setup():
    context = TenantContext("org-1", "tenant-a")
    service_repository = InMemoryBusinessServiceRepository()
    relationship_registry = InMemoryRelationshipRegistry()
    services = BusinessServiceRegistry(
        context,
        service_repository,
        relationships=relationship_registry,
    )
    registered = services.register(
        create_business_service(
            context=context,
            business_service_id="payments",
            name="Payments",
            description="Processes payments",
            business_domain="payments",
            service_type="customer_facing",
            criticality="critical",
            owner_id="owner-1",
            source_system="service-catalog",
            source_id="svc-100",
        )
    )
    entities = InMemoryEntityRegistry()
    technology = entities.register_entity(
        EnterpriseEntity(
            id=str(TECHNOLOGY_ID),
            canonical_id=f"technology:{TECHNOLOGY_ID}",
            entity_type=EntityType.TECHNOLOGY,
            name="Payments Runtime",
            source_system="technology-catalog",
            source_identifier=str(TECHNOLOGY_ID),
            organization_id=context.organization_id,
            tenant_id=context.tenant_id,
        )
    )
    relationship_registry.register_relationship(
        EnterpriseRelationship(
            id="service-technology",
            relationship_type=RelationshipType.RUNS_ON,
            source_entity_id=registered.canonical_id,
            target_entity_id=technology.id,
            organization_id=context.organization_id,
            tenant_id=context.tenant_id,
            source_system="service-catalog",
            source_identifier="service-technology",
        )
    )
    resolver = BusinessServiceAttributionResolver(
        context,
        services=services,
        entities=entities,
        relationships=relationship_registry,
    )
    return (
        context,
        services,
        entities,
        relationship_registry,
        registered,
        technology,
        DomainPostureAdapters(context, attribution=resolver),
    )


def test_cost_risk_and_health_adapters_reuse_owned_signals(adapter_setup) -> None:
    context, _, _, _, service, _, adapters = adapter_setup
    cost = replace(
        CostSignal.create(
            TECHNOLOGY_ID,
            provider="aws",
            service="ec2",
            amount=1200,
            confidence_score=0.9,
        ),
        observed_at=OBSERVED_AT.isoformat(),
    )
    risk = replace(
        RiskSignal.create(
            TECHNOLOGY_ID,
            risk_type="Operational Risk",
            severity="High",
            probability=80,
            impact=75,
            source_system="risk-register",
            confidence_score=0.8,
        ),
        last_observed=OBSERVED_AT.isoformat(),
    )
    health = replace(
        HealthSignal.create(
            TECHNOLOGY_ID,
            signal_type="Availability",
            value=92,
            source_system="observability",
            confidence_score=0.95,
        ),
        last_observed=OBSERVED_AT.isoformat(),
    )

    adapted = {
        PostureDimension.COST: adapters.cost(cost),
        PostureDimension.RISK: adapters.risk(risk),
        PostureDimension.HEALTH: adapters.health(health),
    }

    assert all(
        signal.business_service_id == service.canonical_id
        for signal in adapted.values()
    )
    assert adapted[PostureDimension.COST].score is None
    assert adapted[PostureDimension.COST].value["amount"] == 1200
    assert adapted[PostureDimension.RISK].score == 48.0
    assert adapted[PostureDimension.HEALTH].score == 92
    for signal in adapted.values():
        assert signal.organization_id == context.organization_id
        assert signal.observed_at == OBSERVED_AT
        assert signal.evidence[0].source_identifier


def test_missing_ambiguous_and_unsupported_attribution_are_rejected(
    adapter_setup,
) -> None:
    (
        context,
        services,
        entities,
        relationships,
        _,
        technology,
        _,
    ) = adapter_setup
    missing_relationships = InMemoryRelationshipRegistry()
    missing = BusinessServiceAttributionResolver(
        context,
        services=services,
        entities=entities,
        relationships=missing_relationships,
    )
    with pytest.raises(MissingPostureAttributionError):
        missing.resolve_technology(technology.id)

    unsupported_relationships = InMemoryRelationshipRegistry()
    unsupported_relationships.register_relationship(
        EnterpriseRelationship(
            id="unsupported",
            relationship_type=RelationshipType.OWNED_BY,
            source_entity_id=services.list_services()[0].canonical_id,
            target_entity_id=technology.id,
            organization_id=context.organization_id,
            tenant_id=context.tenant_id,
            source_system="catalog",
            source_identifier="unsupported",
        )
    )
    unsupported = BusinessServiceAttributionResolver(
        context,
        services=services,
        entities=entities,
        relationships=unsupported_relationships,
    )
    with pytest.raises(UnsupportedPostureAttributionError):
        unsupported.resolve_technology(technology.id)

    second = services.register(
        create_business_service(
            context=context,
            business_service_id="billing",
            name="Billing",
            description="Billing service",
            business_domain="finance",
            service_type="shared",
            criticality="high",
            owner_id="owner-2",
            source_system="service-catalog",
            source_id="svc-200",
        )
    )
    relationships.register_relationship(
        EnterpriseRelationship(
            id="ambiguous-path",
            relationship_type=RelationshipType.DEPENDS_ON,
            source_entity_id=second.canonical_id,
            target_entity_id=technology.id,
            organization_id=context.organization_id,
            tenant_id=context.tenant_id,
            source_system="catalog",
            source_identifier="ambiguous-path",
        )
    )
    ambiguous = BusinessServiceAttributionResolver(
        context,
        services=services,
        entities=entities,
        relationships=relationships,
    )
    with pytest.raises(AmbiguousPostureAttributionError):
        ambiguous.resolve_technology(technology.id)


def test_cross_tenant_attribution_and_evidence_are_rejected(adapter_setup) -> None:
    context, services, entities, _, _, technology, adapters = adapter_setup
    cross_tenant_relationships = InMemoryRelationshipRegistry()
    cross_tenant_relationships.register_relationship(
        EnterpriseRelationship(
            id="cross-tenant",
            relationship_type=RelationshipType.RUNS_ON,
            source_entity_id=services.list_services()[0].canonical_id,
            target_entity_id=technology.id,
            organization_id=context.organization_id,
            tenant_id="tenant-b",
            source_system="catalog",
            source_identifier="cross-tenant",
        )
    )
    resolver = BusinessServiceAttributionResolver(
        context,
        services=services,
        entities=entities,
        relationships=cross_tenant_relationships,
    )
    with pytest.raises(DataFabricTenantBoundaryError):
        resolver.resolve_technology(technology.id)

    cost = replace(
        CostSignal.create(
            TECHNOLOGY_ID,
            provider="aws",
            service="ec2",
            amount=1200,
        ),
        observed_at=OBSERVED_AT.isoformat(),
    )
    foreign_evidence = PostureEvidenceReference(
        evidence_id="foreign",
        organization_id=context.organization_id,
        tenant_id="tenant-b",
        source_system="billing",
        source_identifier="foreign",
    )
    with pytest.raises(DataFabricTenantBoundaryError):
        adapters.cost(cost, evidence=(foreign_evidence,))


def test_evidence_trace_survives_attribution_and_posture_query(
    adapter_setup,
) -> None:
    context, services, _, _, registered, _, adapters = adapter_setup
    cost = replace(
        CostSignal.create(
            TECHNOLOGY_ID,
            provider="aws",
            service="ec2",
            amount=1200,
        ),
        observed_at=OBSERVED_AT.isoformat(),
    )
    evidence = PostureEvidenceReference(
        evidence_id="billing-observation-1",
        organization_id=context.organization_id,
        tenant_id=context.tenant_id,
        source_system="aws-cur",
        source_identifier="line-item-1",
        lineage_ref="lineage:cost:1",
        provenance_ref="provenance:cost:1",
    )
    attributed = adapters.cost(cost, evidence=(evidence,))
    query = BusinessServicePostureService(
        context,
        services=services,
        repository=InMemoryBusinessServicePostureRepository(),
    )

    posture = query.publish(
        registered.canonical_id,
        {PostureDimension.COST: attributed},
        generated_at=OBSERVED_AT,
    )
    result = posture.dimensions[PostureDimension.COST]

    assert posture.business_service_id == registered.canonical_id
    assert result.evidence == (evidence,)
    assert result.source_system == "aws"
    assert result.observed_at == OBSERVED_AT
    assert result.reason == "domain_input_available"
