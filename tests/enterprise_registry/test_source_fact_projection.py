from dataclasses import replace
from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest

from data_fabric.contracts import EnterpriseRelationship, RelationshipType
from data_fabric.foundation import DataFabricValidationError, TenantContext
from data_fabric.source_facts.models import (
    FactType,
    Freshness,
    LifecycleState,
    SourceFact,
)
from enterprise_registry.source_fact_projection import (
    EntityProjectionCandidate,
    EntityProjectionRule,
    GovernedCanonicalProjectionService,
    RelationshipProjectionCandidate,
    RelationshipProjectionRule,
)

NOW = datetime(2026, 10, 4, tzinfo=timezone.utc)
ORG = "11111111-1111-4111-8111-111111111111"
TENANT = ORG
SOURCE_ID = (
    "/subscriptions/sub-1/resourceGroups/rg-1/providers/"
    "Microsoft.Compute/virtualMachines/vm-1"
)
RULE = EntityProjectionRule(
    rule_id="azure.vm.identity.v1",
    version="1",
    source_system="azure",
    fact_type=FactType.RESOURCE_IDENTITY,
    predicate="resource_identity",
    entity_type="compute_resource",
    source_identifier_field="resource_id",
    canonical_name_field="name",
    metadata_fields=("provider", "resource_type", "subscription_id", "region"),
)


class RecordingExecutor:
    def __init__(self):
        self.entity_requests = []
        self.relationship_requests = []

    def execute_entity_write(self, request):
        self.entity_requests.append(request)
        return request

    def execute_relationship_write(self, request):
        self.relationship_requests.append(request)
        return request


def fact(*, organization_id=ORG, tenant_id=TENANT, fact_type=FactType.RESOURCE_IDENTITY,
         predicate="resource_identity", object_reference=None):
    return SourceFact(
        source_fact_id="fact-azure-vm-1",
        observation_key="observation-azure-vm-1",
        fact_version=1,
        organization_id=organization_id,
        tenant_id=tenant_id,
        source_instance_id="azure-instance-1",
        source_type="cloud_api",
        source_system="azure",
        connector_version="1.0",
        ingestion_run_id="run-1",
        source_record_id=SOURCE_ID,
        fact_type=fact_type,
        subject_reference=SOURCE_ID,
        predicate=predicate,
        value={
            "provider": "Azure",
            "resource_id": SOURCE_ID,
            "resource_type": "Azure VM",
            "subscription_id": "sub-1",
            "region": "eastus",
            "name": "vm-1",
        },
        object_reference=object_reference,
        observed_at=NOW,
        effective_from=None,
        effective_to=None,
        source_schema_version="1",
        quality=1.0,
        freshness=Freshness.FRESH,
        evidence_reference="azure-evidence:run-1:vm-1",
        lineage={"run_id": "run-1"},
        provenance={"provider": "Azure"},
        lifecycle=LifecycleState.ACTIVE,
        fingerprint="fact-fingerprint",
    )


def projector(context=None, executor=None):
    return GovernedCanonicalProjectionService(
        context or TenantContext(ORG, TENANT),
        executor or RecordingExecutor(),
        entity_rules={RULE.rule_id: RULE},
    )


def test_projection_requires_explicit_tenant_context_and_executor():
    with pytest.raises(TypeError, match="TenantContext"):
        GovernedCanonicalProjectionService(None, RecordingExecutor())
    with pytest.raises(DataFabricValidationError, match="organization_id"):
        TenantContext("", TENANT)
    with pytest.raises(DataFabricValidationError, match="tenant_id"):
        TenantContext(ORG, "")
    with pytest.raises(ValueError, match="executor"):
        GovernedCanonicalProjectionService(TenantContext(ORG, TENANT), None)


def test_cross_tenant_fact_fails_closed():
    with pytest.raises(PermissionError, match="tenant boundary"):
        projector().project_entities((EntityProjectionCandidate(
            fact(organization_id="22222222-2222-4222-8222-222222222222",
                 tenant_id="22222222-2222-4222-8222-222222222222"), RULE.rule_id,
        ),))


def test_unapproved_or_inactive_facts_are_never_projected():
    executor = RecordingExecutor()
    with pytest.raises(ValueError, match="no registered"):
        projector(executor=executor).project_entities(
            (EntityProjectionCandidate(fact(), "unapproved"),)
        )
    with pytest.raises(ValueError, match="does not match"):
        projector(executor=executor).project_entities((EntityProjectionCandidate(
            fact(fact_type=FactType.CLOUD_COST), RULE.rule_id,
        ),))
    with pytest.raises(ValueError, match="inactive"):
        projector(executor=executor).project_entities((EntityProjectionCandidate(
            replace(fact(), lifecycle=LifecycleState.SOURCE_DISABLED), RULE.rule_id,
        ),))
    assert executor.entity_requests == []


def test_entity_projection_preserves_tenant_identity_provenance_and_is_idempotent():
    executor = RecordingExecutor()
    service = projector(executor=executor)
    candidate = EntityProjectionCandidate(fact(), RULE.rule_id)

    first = service.project_entities((candidate,))[0]
    second = service.project_entities((candidate,))[0]

    assert first.idempotency_key == second.idempotency_key
    assert first.payload_hash == second.payload_hash
    assert len(executor.entity_requests) == 2
    record = first.entity_record
    assert UUID(record.record_id)
    assert record.record_id == second.entity_record.record_id
    assert record.payload["canonical_id"].startswith("compute_resource:")
    assert record.organization_id == ORG
    assert record.tenant_id == TENANT
    assert record.metadata["source_identifier"] == SOURCE_ID
    payload = record.payload
    assert payload["source_identifier"] == SOURCE_ID
    assert payload["source_system"] == "azure"
    assert payload["metadata"]["provider"] == "Azure"
    assert payload["metadata"]["resource_type"] == "Azure VM"
    assert payload["metadata"]["subscription_id"] == "sub-1"
    assert payload["metadata"]["region"] == "eastus"
    assert payload["provenance_reference"] == "fact-azure-vm-1"
    assert payload["lineage_reference"] == "run-1"
    assert payload["provenance"]["metadata"]["evidence_reference"] == "azure-evidence:run-1:vm-1"
    assert first.tenant_context == TenantContext(ORG, TENANT)


def test_relationship_projection_requires_explicit_fact_and_registered_rule():
    executor = RecordingExecutor()
    rule = RelationshipProjectionRule(
        rule_id="azure.explicit.dependency.v1",
        version="1",
        source_system="azure",
        fact_type=FactType.DEPENDENCY,
        predicate="depends_on",
        relationship_type=RelationshipType.DEPENDS_ON.value,
    )
    service = GovernedCanonicalProjectionService(
        TenantContext(ORG, TENANT), executor,
        relationship_rules={rule.rule_id: rule},
    )
    source_fact = fact(
        fact_type=FactType.DEPENDENCY,
        predicate="depends_on",
        object_reference="target",
    )
    relationship = EnterpriseRelationship(
        id=str(uuid4()),
        relationship_type=RelationshipType.DEPENDS_ON,
        source_entity_id=str(uuid4()),
        target_entity_id=str(uuid4()),
        organization_id=ORG,
        tenant_id=TENANT,
        source_system="azure",
        source_identifier=source_fact.source_record_id,
    )
    candidate = RelationshipProjectionCandidate(source_fact, rule.rule_id, relationship)
    result = service.project_relationships((candidate,))
    repeated = service.project_relationships((candidate,))

    assert len(result) == 1
    assert result[0].idempotency_key == repeated[0].idempotency_key
    assert result[0].payload_hash == repeated[0].payload_hash
    assert UUID(result[0].relationship_record.record_id)
    assert source_fact.source_fact_id in result[0].relationship_record.payload["evidence"]
    assert result[0].relationship_record.organization_id == ORG
    assert result[0].relationship_record.tenant_id == TENANT


def test_relationship_without_explicit_object_reference_is_not_projected():
    executor = RecordingExecutor()
    rule = RelationshipProjectionRule(
        rule_id="azure.explicit.dependency.v1",
        version="1",
        source_system="azure",
        fact_type=FactType.DEPENDENCY,
        predicate="depends_on",
        relationship_type=RelationshipType.DEPENDS_ON.value,
    )
    service = GovernedCanonicalProjectionService(
        TenantContext(ORG, TENANT), executor,
        relationship_rules={rule.rule_id: rule},
    )
    source_fact = fact(fact_type=FactType.DEPENDENCY, predicate="depends_on")
    relationship = EnterpriseRelationship(
        id=str(uuid4()), relationship_type=RelationshipType.DEPENDS_ON,
        source_entity_id=str(uuid4()), target_entity_id=str(uuid4()),
        organization_id=ORG, tenant_id=TENANT, source_system="azure",
        source_identifier=source_fact.source_record_id,
    )

    with pytest.raises(ValueError, match="object reference"):
        service.project_relationships((RelationshipProjectionCandidate(
            source_fact, rule.rule_id, relationship,
        ),))
    assert executor.relationship_requests == []
