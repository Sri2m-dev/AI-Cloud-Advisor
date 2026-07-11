from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import datetime, timezone

import pytest

from data_fabric.adapters.supabase import (
    AtomicEntityWriteRequest,
    AtomicRelationshipWriteRequest,
    AtomicWriteStatus,
    DataFabricDatabaseConfig,
    SupabaseAtomicWriteExecutor,
    SupabaseDataFabricClient,
)
from data_fabric.foundation import (
    DataFabricConflictError,
    DataFabricIdempotencyError,
    DataFabricTenantBoundaryError,
    DataFabricTransactionError,
    DataFabricValidationError,
    TenantContext,
)
from data_fabric.persistence.models import AppendOnlyRecord, MutableRecord
from tests.data_fabric.supabase_fake import FakeRawSupabaseClient


NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)
ENTITY_ID = "11111111-1111-4111-8111-111111111111"
RELATIONSHIP_ID = "22222222-2222-4222-8222-222222222222"
SOURCE_ID = "33333333-3333-4333-8333-333333333333"
TARGET_ID = "44444444-4444-4444-8444-444444444444"


def tc() -> TenantContext:
    return TenantContext("org-1", "tenant-1")


def client(raw: FakeRawSupabaseClient) -> SupabaseDataFabricClient:
    return SupabaseDataFabricClient(
        DataFabricDatabaseConfig("https://example.supabase.co", "server-side-secret", max_retries=0),
        raw_client=raw,
    )


def executor(raw: FakeRawSupabaseClient) -> SupabaseAtomicWriteExecutor:
    return SupabaseAtomicWriteExecutor(client(raw))


def entity_record(record_id: str = ENTITY_ID) -> MutableRecord:
    return MutableRecord(
        record_id=record_id,
        organization_id="org-1",
        tenant_id="tenant-1",
        created_at=NOW,
        updated_at=NOW,
        payload={
            "canonical_id": "canonical-1",
            "entity_type": "application",
            "name": "Application",
            "source_system": "cmdb",
            "source_identifier": "app-1",
            "version": 1,
            "metadata": {"tier": "gold"},
        },
    )


def relationship_record(record_id: str = RELATIONSHIP_ID) -> MutableRecord:
    return MutableRecord(
        record_id=record_id,
        organization_id="org-1",
        tenant_id="tenant-1",
        created_at=NOW,
        updated_at=NOW,
        payload={
            "source_entity_id": SOURCE_ID,
            "target_entity_id": TARGET_ID,
            "relationship_type": "depends_on",
            "source_system": "cmdb",
            "source_identifier": "rel-1",
            "version": 1,
        },
    )


def version_record() -> AppendOnlyRecord:
    return AppendOnlyRecord(
        record_id="55555555-5555-4555-8555-555555555555",
        organization_id="org-1",
        tenant_id="tenant-1",
        created_at=NOW,
        updated_at=NOW,
        payload={"entity_id": ENTITY_ID, "canonical_id": "canonical-1", "version": 1, "payload": {"name": "Application"}},
        payload_hash="version-hash",
    )


def lineage_record(subject_id: str = ENTITY_ID, subject_type: str = "entity") -> AppendOnlyRecord:
    payload = {
        "event_type": "canonical_write",
        "source_system": "cmdb",
        "source_identifier": "lineage-1",
        "occurred_at": NOW,
    }
    payload["entity_id" if subject_type == "entity" else "relationship_id"] = subject_id
    return AppendOnlyRecord(
        record_id="66666666-6666-4666-8666-666666666666",
        organization_id="org-1",
        tenant_id="tenant-1",
        created_at=NOW,
        updated_at=NOW,
        payload=payload,
        payload_hash="lineage-hash",
    )


def provenance_record(subject_id: str = ENTITY_ID, subject_type: str = "entity") -> AppendOnlyRecord:
    payload = {
        "source_system": "cmdb",
        "source_identifier": "prov-1",
        "captured_at": NOW,
        "evidence": {"source": "test"},
    }
    payload["entity_id" if subject_type == "entity" else "relationship_id"] = subject_id
    return AppendOnlyRecord(
        record_id="77777777-7777-4777-8777-777777777777",
        organization_id="org-1",
        tenant_id="tenant-1",
        created_at=NOW,
        updated_at=NOW,
        payload=payload,
        payload_hash="prov-hash",
    )


def quality_record(subject_id: str = ENTITY_ID, subject_type: str = "entity") -> AppendOnlyRecord:
    return AppendOnlyRecord(
        record_id="88888888-8888-4888-8888-888888888888",
        organization_id="org-1",
        tenant_id="tenant-1",
        created_at=NOW,
        updated_at=NOW,
        metadata={"subject_type": subject_type, "subject_id": subject_id},
        payload={
            "subject_type": subject_type,
            "subject_id": subject_id,
            "overall_score": 95,
            "dimensions": {"completeness": 95},
            "issues": [],
            "blocking_issues": [],
            "assessed_at": NOW,
        },
        payload_hash="quality-hash",
    )


def entity_request(operation: str = "create", expected_revision: int | None = None) -> AtomicEntityWriteRequest:
    return AtomicEntityWriteRequest(
        tenant_context=tc(),
        operation=operation,
        entity_record=entity_record(),
        expected_revision=expected_revision,
        entity_version=version_record(),
        lineage_events=(lineage_record(),),
        provenance_records=(provenance_record(),),
        quality_assessment=quality_record(),
        idempotency_key=f"entity-{operation}",
        payload_hash=f"hash-{operation}",
        correlation_id=f"corr-{operation}",
        actor="tester",
        metadata={"nested": {"b": [2, 1]}},
    )


def relationship_request(operation: str = "create", expected_revision: int | None = None) -> AtomicRelationshipWriteRequest:
    return AtomicRelationshipWriteRequest(
        tenant_context=tc(),
        operation=operation,
        relationship_record=relationship_record(),
        expected_revision=expected_revision,
        lineage_events=(lineage_record(RELATIONSHIP_ID, "relationship"),),
        provenance_records=(provenance_record(RELATIONSHIP_ID, "relationship"),),
        quality_assessment=quality_record(RELATIONSHIP_ID, "relationship"),
        idempotency_key=f"relationship-{operation}",
        payload_hash=f"hash-{operation}",
        correlation_id=f"corr-{operation}",
        actor="tester",
    )


def only_rpc(raw: FakeRawSupabaseClient) -> tuple[str, dict]:
    assert len(raw.rpc_calls) == 1
    assert raw.executed_filters == []
    return raw.rpc_calls[0]


def test_entity_create_serialization_and_success_mapping():
    raw = FakeRawSupabaseClient()
    result = executor(raw).execute_entity_write(entity_request())
    name, params = only_rpc(raw)
    assert name == "data_fabric_atomic_entity_write"
    request = params["p_request"]
    assert request["operation"] == "create"
    assert request["tenant_context"] == {"organization_id": "org-1", "tenant_id": "tenant-1"}
    assert request["entity_record"]["record_id"] == ENTITY_ID
    assert request["entity_version"]["record_id"] == "55555555-5555-4555-8555-555555555555"
    assert request["lineage_events"][0]["record_id"] == "66666666-6666-4666-8666-666666666666"
    assert result.status is AtomicWriteStatus.COMMITTED
    assert result.version_created is True
    assert result.quality_assessment_id == "88888888-8888-4888-8888-888888888888"


@pytest.mark.parametrize("operation,expected", [("update", 1), ("deactivate", 2), ("no_change", None)])
def test_entity_update_deactivate_and_no_change_serialization(operation: str, expected: int | None):
    raw = FakeRawSupabaseClient()
    result = executor(raw).execute_entity_write(entity_request(operation, expected))
    _, params = only_rpc(raw)
    assert params["p_request"]["operation"] == operation
    assert params["p_request"]["expected_revision"] == expected
    if operation == "no_change":
        assert result.status is AtomicWriteStatus.NO_CHANGE
    else:
        assert result.status is AtomicWriteStatus.COMMITTED


@pytest.mark.parametrize("operation,expected", [("create", None), ("update", 1), ("deactivate", 2)])
def test_relationship_create_update_deactivate_serialization(operation: str, expected: int | None):
    raw = FakeRawSupabaseClient()
    result = executor(raw).execute_relationship_write(relationship_request(operation, expected))
    name, params = only_rpc(raw)
    assert name == "data_fabric_atomic_relationship_write"
    assert params["p_request"]["relationship_record"]["record_id"] == RELATIONSHIP_ID
    assert params["p_request"]["expected_revision"] == expected
    assert result.subject_type == "relationship"


@pytest.mark.parametrize(
    "status,replayed",
    [("replayed", True), ("no_change", False), ("in_progress", False)],
)
def test_result_status_mapping(status: str, replayed: bool):
    raw = FakeRawSupabaseClient()
    raw.rpc_results["data_fabric_atomic_entity_write"] = {
        "status": status,
        "subject_type": "entity",
        "subject_id": ENTITY_ID,
        "operation": "create",
        "idempotency_status": "completed" if status != "in_progress" else "in_progress",
        "replayed": replayed,
        "records": [{"record_type": "entity", "record_id": ENTITY_ID, "created": status != "replayed"}],
    }
    result = executor(raw).execute_entity_write(entity_request())
    assert result.status is AtomicWriteStatus(status)
    assert result.replayed is replayed
    assert result.records[0].record_id == ENTITY_ID


@pytest.mark.parametrize(
    "code,exc_type",
    [
        ("P3_REVISION_CONFLICT", DataFabricConflictError),
        ("P3_TENANT_BOUNDARY", DataFabricTenantBoundaryError),
        ("P3_IDEMPOTENCY_CONFLICT", DataFabricIdempotencyError),
        ("P3_TRANSACTION_FAILED", DataFabricTransactionError),
    ],
)
def test_rpc_error_mapping(code: str, exc_type: type[Exception]):
    raw = FakeRawSupabaseClient()
    raw.rpc_errors["data_fabric_atomic_entity_write"] = f"{code}: service_role secret payload should not leak"
    with pytest.raises(exc_type) as error:
        executor(raw).execute_entity_write(entity_request())
    message = str(error.value)
    assert code in message
    assert "service_role" not in message
    assert "secret" not in message
    assert "payload should not leak" not in message


def test_validation_failure_result_mapping():
    raw = FakeRawSupabaseClient()
    raw.rpc_results["data_fabric_atomic_entity_write"] = {
        "status": "rejected",
        "subject_type": "entity",
        "subject_id": ENTITY_ID,
        "operation": "create",
        "failure": {"code": "P3_VALIDATION_ERROR", "reason": "invalid request"},
    }
    with pytest.raises(DataFabricValidationError):
        executor(raw).execute_entity_write(entity_request())


def test_request_and_nested_metadata_are_immutable_and_input_is_not_mutated():
    raw = FakeRawSupabaseClient()
    metadata = {"outer": {"items": [2, 1]}}
    request = AtomicEntityWriteRequest(
        tenant_context=tc(),
        operation="create",
        entity_record=entity_record(),
        idempotency_key="immutable",
        payload_hash="hash",
        metadata=metadata,
    )
    metadata["outer"]["items"].append(3)
    assert request.metadata["outer"]["items"] == (2, 1)
    executor(raw).execute_entity_write(request)
    assert request.metadata["outer"]["items"] == (2, 1)


def test_result_records_are_immutable():
    raw = FakeRawSupabaseClient()
    raw.rpc_results["data_fabric_atomic_entity_write"] = {
        "status": "committed",
        "subject_type": "entity",
        "subject_id": ENTITY_ID,
        "operation": "create",
        "records": [{"record_type": "entity", "record_id": ENTITY_ID, "metadata": {"a": 1}}],
    }
    result = executor(raw).execute_entity_write(entity_request())
    with pytest.raises(FrozenInstanceError):
        result.records[0].record_id = "other"
    with pytest.raises(TypeError):
        result.records[0].metadata["a"] = 2


def test_exactly_one_rpc_and_no_repository_calls_for_relationship_executor():
    raw = FakeRawSupabaseClient()
    executor(raw).execute_relationship_write(relationship_request())
    name, _ = only_rpc(raw)
    assert name == "data_fabric_atomic_relationship_write"
    assert all(not rows for rows in raw.tables.values())


def test_deterministic_serialization_and_repeat_result_mapping():
    raw_a = FakeRawSupabaseClient()
    raw_b = FakeRawSupabaseClient()
    request = entity_request()
    result_a = executor(raw_a).execute_entity_write(request)
    result_b = executor(raw_b).execute_entity_write(request)
    assert raw_a.rpc_calls[0] == raw_b.rpc_calls[0]
    assert result_a == result_b


def test_cross_tenant_request_rejected_before_rpc():
    raw = FakeRawSupabaseClient()
    bad = MutableRecord(record_id=ENTITY_ID, organization_id="org-2", tenant_id="tenant-1", created_at=NOW, updated_at=NOW)
    with pytest.raises(DataFabricTenantBoundaryError):
        AtomicEntityWriteRequest(tenant_context=tc(), operation="create", entity_record=bad, idempotency_key="k", payload_hash="h")
    assert raw.rpc_calls == []
