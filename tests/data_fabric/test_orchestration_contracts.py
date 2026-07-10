from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from data_fabric.contracts import EnterpriseEntity
from data_fabric.foundation import TenantContext
from data_fabric.lineage import LineageEvent, ProvenanceRecord
from data_fabric.orchestration import (
    BatchIngestionRequest,
    DefaultCanonicalizationPipeline,
    EntityWriteAction,
    IdempotencyKey,
    InMemoryIdempotencyStore,
    InMemoryIngestionCoordinator,
    InMemoryTransactionBoundary,
    InMemoryUnitOfWork,
    IngestionRequest,
    QualityGateOutcome,
    RelationshipWriteAction,
    RelationshipWritePlan,
    TransactionStatus,
    VersionDecisionAction,
)
from data_fabric.orchestration.exceptions import OrchestrationIdempotencyError
from data_fabric.orchestration.models import EntityWritePlan


def request(
    request_id: str = "req-1",
    key: str = "idem-1",
    payload: dict | None = None,
    tenant: TenantContext | None = None,
) -> IngestionRequest:
    tenant_context = tenant or TenantContext("org-1", "tenant-a")
    data = {"id": "entity-1", "name": "Compute Service", "trust_score": 95.0}
    if payload:
        data.update(payload)
    return IngestionRequest(
        request_id=request_id,
        tenant_context=tenant_context,
        source_system="aws",
        source_identifier="i-123",
        source_type="instance",
        provider="aws",
        payload=data,
        received_at=datetime(2026, 7, 10, 12, 0, tzinfo=timezone.utc),
        idempotency_key=IdempotencyKey(tenant_context, key),
        correlation_id="corr-1",
    )


def test_valid_ingestion_creates_explainable_write_plan():
    coordinator = InMemoryIngestionCoordinator()

    result = coordinator.ingest(request())

    assert result.entity_plan.action is EntityWriteAction.CREATE
    assert result.entity_plan.entity.canonical_id == "entity-1"
    assert result.quality_decision.outcome is QualityGateOutcome.ALLOW
    assert result.transaction_result.status is TransactionStatus.COMMITTED
    assert "validate tenant context" in result.explanation


def test_repeated_identical_request_returns_previous_idempotent_result():
    coordinator = InMemoryIngestionCoordinator()
    first = coordinator.ingest(request())
    second = coordinator.ingest(request())

    assert first.idempotent_replay is False
    assert second.idempotent_replay is True
    assert second.request_id == first.request_id


def test_repeated_key_with_different_payload_raises_conflict():
    coordinator = InMemoryIngestionCoordinator()
    coordinator.ingest(request())

    with pytest.raises(OrchestrationIdempotencyError):
        coordinator.ingest(request(payload={"name": "Changed"}))


def test_blocking_quality_issue_causes_rejection():
    coordinator = InMemoryIngestionCoordinator()
    result = coordinator.ingest(
        request(
            payload={
                "quality_issues": [
                    {
                        "rule_id": "required_field",
                        "dimension": "validity",
                        "message": "required field missing",
                        "severity": "blocking",
                    }
                ]
            }
        )
    )

    assert result.quality_decision.outcome is QualityGateOutcome.REJECT
    assert result.transaction_result is None
    assert result.succeeded is False


def test_low_quality_causes_quarantine():
    result = InMemoryIngestionCoordinator().ingest(request(payload={"trust_score": 50.0}))

    assert result.quality_decision.outcome is QualityGateOutcome.QUARANTINE
    assert result.transaction_result is None


def test_warning_quality_causes_allow_with_warning():
    result = InMemoryIngestionCoordinator().ingest(request(payload={"trust_score": 70.0}))

    assert result.quality_decision.outcome is QualityGateOutcome.ALLOW_WITH_WARNING
    assert result.transaction_result.status is TransactionStatus.COMMITTED


def test_unchanged_payload_skips_version_creation_with_new_idempotency_key():
    coordinator = InMemoryIngestionCoordinator()
    coordinator.ingest(request(key="first"))
    second = coordinator.ingest(request(request_id="req-2", key="second"))

    assert second.version_decision.action is VersionDecisionAction.SKIP_UNCHANGED


def test_changed_payload_creates_version_decision():
    coordinator = InMemoryIngestionCoordinator()
    coordinator.ingest(request(key="first"))
    second = coordinator.ingest(
        request(request_id="req-2", key="second", payload={"name": "Changed Service"})
    )

    assert second.version_decision.action is VersionDecisionAction.CREATE_CHANGED_VERSION


def test_lineage_plan_contains_required_events():
    result = InMemoryIngestionCoordinator().ingest(request())

    assert result.lineage_plan.emit_source_event is True
    assert result.lineage_plan.emit_normalization_event is True
    assert result.lineage_plan.emit_canonicalization_event is True
    assert result.lineage_plan.emit_quality_assessment_event is True
    assert result.lineage_plan.emit_version_event is True
    assert {event.event_type for event in result.lineage_plan.events} == {
        "source",
        "normalization",
        "canonicalization",
    }
    assert result.lineage_plan.provenance_records[0].tenant_id == "tenant-a"


def test_transaction_commit_applies_all_staged_operations_atomically():
    tenant = TenantContext("org-1", "tenant-a")
    unit = InMemoryUnitOfWork()
    unit.begin(tenant)
    entity = EnterpriseEntity(
        id="entity-1",
        canonical_id="entity-1",
        entity_type="cloud_resource",
        name="Entity",
        source_system="aws",
        source_identifier="i-123",
        organization_id="org-1",
        tenant_id="tenant-a",
    )
    event = LineageEvent("lineage-1", "source", "aws", "i-123", "org-1", tenant_id="tenant-a", entity_id="entity-1")
    provenance = ProvenanceRecord("prov-1", "aws", "i-123", "org-1", "manual", tenant_id="tenant-a", entity_id="entity-1")

    unit.stage_entity_write(EntityWritePlan(EntityWriteAction.CREATE, entity=entity))
    unit.stage_lineage_event(event)
    unit.stage_provenance_record(provenance)
    result = unit.commit()

    assert result.status is TransactionStatus.COMMITTED
    assert len(unit.committed_entities) == 1
    assert len(unit.committed_lineage_events) == 1
    assert len(unit.committed_provenance_records) == 1


def test_transaction_failure_rolls_back_all_staged_operations():
    tenant = TenantContext("org-1", "tenant-a")
    unit = InMemoryUnitOfWork(fail_commit=True)
    unit.begin(tenant)
    entity = EnterpriseEntity(
        id="entity-1",
        canonical_id="entity-1",
        entity_type="cloud_resource",
        name="Entity",
        source_system="aws",
        source_identifier="i-123",
        organization_id="org-1",
        tenant_id="tenant-a",
    )

    unit.stage_entity_write(EntityWritePlan(EntityWriteAction.CREATE, entity=entity))
    result = unit.commit()

    assert result.status is TransactionStatus.ROLLED_BACK
    assert unit.committed_entities == []


def test_idempotency_completion_occurs_after_commit():
    store = InMemoryIdempotencyStore()
    pipeline = DefaultCanonicalizationPipeline(idempotency_store=store)
    item = request()

    result = pipeline.process(item)
    record = store.get(item.idempotency_key)

    assert result.transaction_result.status is TransactionStatus.COMMITTED
    assert record.state.value == "completed"
    assert record.result == result


def test_tenant_mismatch_is_rejected():
    tenant = TenantContext("org-1", "tenant-a")
    other = TenantContext("org-1", "tenant-b")

    with pytest.raises(Exception):
        BatchIngestionRequest("batch-1", tenant, (request(tenant=other),))


def test_batch_rejects_mixed_tenant_contexts():
    tenant = TenantContext("org-1", "tenant-a")
    other = TenantContext("org-2", "tenant-a")

    with pytest.raises(Exception):
        BatchIngestionRequest("batch-1", tenant, (request(tenant=tenant), request(tenant=other),))


def test_continue_on_error_preserves_per_record_results():
    coordinator = InMemoryIngestionCoordinator()
    batch = BatchIngestionRequest(
        "batch-1",
        TenantContext("org-1", "tenant-a"),
        (
            request("req-1", "key-1"),
            request("req-2", "key-2", {"trust_score": 40.0}),
            request("req-3", "key-3"),
        ),
        fail_fast=False,
    )

    result = coordinator.ingest_batch(batch)

    assert [record.index for record in result.records] == [0, 1, 2]
    assert result.success_count == 2
    assert result.failure_count == 1


def test_fail_fast_stops_after_first_failure():
    coordinator = InMemoryIngestionCoordinator()
    batch = BatchIngestionRequest(
        "batch-1",
        TenantContext("org-1", "tenant-a"),
        (
            request("req-1", "key-1", {"trust_score": 40.0}),
            request("req-2", "key-2"),
        ),
        fail_fast=True,
    )

    result = coordinator.ingest_batch(batch)

    assert len(result.records) == 1
    assert result.records[0].success is False


def test_result_order_matches_input_order():
    result = InMemoryIngestionCoordinator().ingest_batch(
        BatchIngestionRequest(
            "batch-1",
            TenantContext("org-1", "tenant-a"),
            (request("req-1", "key-1"), request("req-2", "key-2"), request("req-3", "key-3")),
        )
    )

    assert [record.request_id for record in result.records] == ["req-1", "req-2", "req-3"]


def test_repeated_processing_is_deterministic():
    left = InMemoryIngestionCoordinator().ingest(request())
    right = InMemoryIngestionCoordinator().ingest(request())

    assert left.entity_plan.entity.canonical_id == right.entity_plan.entity.canonical_id
    assert left.version_decision.new_hash == right.version_decision.new_hash
    assert left.quality_decision.outcome == right.quality_decision.outcome


def test_orchestration_does_not_mutate_supplied_source_payload():
    payload = {"id": "entity-1", "name": "Compute", "tags": ["prod"]}
    original = {"id": "entity-1", "name": "Compute", "tags": ["prod"]}

    InMemoryIngestionCoordinator().ingest(request(payload=payload))

    assert payload == original


def test_no_direct_database_or_runtime_dependency_exists():
    package = Path("data_fabric/orchestration")
    content = "\n".join(path.read_text() for path in package.glob("*.py"))

    forbidden = ("supabase", "sqlite", "sqlalchemy", "streamlit", "connector_runtime", "scheduler")
    assert all(term not in content for term in forbidden)


def test_relationship_write_plan_actions_are_explicit():
    plan = RelationshipWritePlan(RelationshipWriteAction.NO_CHANGE, reason="no relationship derived")

    assert plan.action is RelationshipWriteAction.NO_CHANGE
