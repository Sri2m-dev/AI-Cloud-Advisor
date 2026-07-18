"""Opt-in live validation for P3 atomic Supabase RPCs (migrations 0017/0018)."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from postgrest.exceptions import APIError
from supabase import create_client

from tests.data_fabric.supabase_integration_safety import (
    create_test_identifier,
    resolve_config,
)


def _db():
    config = resolve_config()
    return create_client(config.url, config.service_role_key).schema("data_fabric")


def _scope() -> tuple[str, str, str]:
    token = uuid4().hex
    return create_test_identifier(f"org-{token}"), create_test_identifier(f"tenant-{token}"), token


def _record(record_id: str, organization_id: str, tenant_id: str, payload: dict, *, payload_hash: str | None = None) -> dict:
    now = datetime.now(timezone.utc).isoformat()
    value = {"record_id": record_id, "organization_id": organization_id, "tenant_id": tenant_id, "created_at": now, "updated_at": now, "schema_version": 1, "metadata": {}, "payload": payload}
    if payload_hash is not None:
        value["payload_hash"] = payload_hash
    return value


def _rpc_error(db, name: str, request: dict) -> str:
    with pytest.raises(APIError) as exc_info:
        db.rpc(name, {"p_request": request}).execute()
    return str(exc_info.value)


def _entity_request(org: str, tenant: str, token: str, entity_id: str, *, operation: str = "create", expected_revision: int | None = None, version: int = 1) -> dict:
    request = {
        "tenant_context": {"organization_id": org, "tenant_id": tenant},
        "operation": operation,
        "expected_revision": expected_revision,
        "idempotency_key": create_test_identifier(f"entity-{operation}-{token}-{version}"),
        "payload_hash": create_test_identifier(f"entity-hash-{token}-{version}"),
        "correlation_id": create_test_identifier(f"entity-correlation-{token}-{version}"),
        "actor": "p3test-validator",
        "entity_record": _record(entity_id, org, tenant, {"canonical_id": create_test_identifier(f"canonical-{token}"), "entity_type": "application", "name": f"P3 atomic entity v{version}", "source_system": "p3test-live-validation", "source_identifier": create_test_identifier(f"source-{token}"), "version": version}),
        "lineage_events": [],
        "provenance_records": [],
    }
    if operation in {"create", "update"}:
        request["entity_version"] = _record(str(uuid4()), org, tenant, {"entity_id": entity_id, "canonical_id": create_test_identifier(f"canonical-{token}"), "version": version, "payload": {"name": f"P3 atomic entity v{version}"}}, payload_hash=create_test_identifier(f"version-hash-{token}-{version}"))
    return request


def test_atomic_entity_create_replay_update_and_rollbacks() -> None:
    db = _db()
    org, tenant, token = _scope()
    entity_id = str(uuid4())
    create = _entity_request(org, tenant, token, entity_id)
    lineage_id, provenance_id, quality_id = str(uuid4()), str(uuid4()), str(uuid4())
    now = datetime.now(timezone.utc).isoformat()
    create["lineage_events"] = [_record(lineage_id, org, tenant, {"entity_id": entity_id, "event_type": "entity_created", "occurred_at": now})]
    create["provenance_records"] = [_record(provenance_id, org, tenant, {"entity_id": entity_id, "source_system": "p3test-live-validation", "source_identifier": create_test_identifier(f"provenance-{token}"), "captured_at": now}, payload_hash=create_test_identifier(f"provenance-hash-{token}"))]
    create["quality_assessment"] = _record(quality_id, org, tenant, {"subject_type": "entity", "subject_id": entity_id, "overall_score": 95, "trust_score": 90, "decision": "accepted", "dimensions": {}, "issues": [], "blocking_issues": [], "assessed_at": now}, payload_hash=create_test_identifier(f"quality-hash-{token}"))

    committed = db.rpc("data_fabric_atomic_entity_write", {"p_request": create}).execute().data
    replayed = db.rpc("data_fabric_atomic_entity_write", {"p_request": create}).execute().data
    assert committed["status"] == "committed" and committed["version_created"] is True
    assert committed["lineage_ids"] == [lineage_id] and committed["provenance_ids"] == [provenance_id]
    assert committed["quality_assessment_id"] == quality_id
    assert replayed["status"] == "replayed" and replayed["replayed"] is True
    evidence = (
        ("enterprise_entities", "id", entity_id),
        ("entity_versions", "snapshot_id", create["entity_version"]["record_id"]),
        ("lineage_events", "event_id", lineage_id),
        ("provenance_records", "provenance_id", provenance_id),
        ("quality_assessments", "assessment_id", quality_id),
        ("idempotency_records", "idempotency_key", create["idempotency_key"]),
    )
    for table, column, value in evidence:
        rows = db.table(table).select("*").eq(column, value).eq("organization_id", org).eq("tenant_id", tenant).execute().data or []
        assert len(rows) == 1

    update = _entity_request(org, tenant, token, entity_id, operation="update", expected_revision=1, version=2)
    updated = db.rpc("data_fabric_atomic_entity_write", {"p_request": update}).execute().data
    assert updated["resulting_revision"] == 2 and updated["resulting_version"] == 2

    stale = _entity_request(org, tenant, f"stale-{token}", entity_id, operation="update", expected_revision=1, version=3)
    assert "P3_REVISION_CONFLICT" in _rpc_error(db, "data_fabric_atomic_entity_write", stale)

    invalid_id, invalid_lineage, wrong_id = str(uuid4()), str(uuid4()), str(uuid4())
    invalid = _entity_request(org, tenant, f"invalid-{token}", invalid_id)
    invalid.pop("entity_version")
    invalid["lineage_events"] = [_record(invalid_lineage, org, tenant, {"entity_id": wrong_id, "event_type": "invalid", "occurred_at": now})]
    assert "P3_TENANT_BOUNDARY" in _rpc_error(db, "data_fabric_atomic_entity_write", invalid)

    assert len(db.table("enterprise_entities").select("id").eq("id", invalid_id).eq("organization_id", org).eq("tenant_id", tenant).execute().data or []) == 0
    assert len(db.table("idempotency_records").select("record_id").eq("idempotency_key", invalid["idempotency_key"]).eq("organization_id", org).eq("tenant_id", tenant).execute().data or []) == 0
    deleted = db.table("enterprise_entities").delete().eq("id", entity_id).eq("organization_id", org).eq("tenant_id", tenant).execute().data or []
    assert len(deleted) == 1
    print("P3_ENTITY_COUNTS rpc=5 reads=8 committed_writes=9 rejected=2 rollbacks=2 cleanup=1")


def test_atomic_relationship_create_replay_update_and_rollbacks() -> None:
    db = _db()
    org, tenant, token = _scope()
    source_id, target_id = str(uuid4()), str(uuid4())
    for label, entity_id in (("source", source_id), ("target", target_id)):
        request = _entity_request(org, tenant, f"{label}-{token}", entity_id)
        request.pop("entity_version")
        assert db.rpc("data_fabric_atomic_entity_write", {"p_request": request}).execute().data["status"] == "committed"

    relationship_id, lineage_id, provenance_id = str(uuid4()), str(uuid4()), str(uuid4())
    now = datetime.now(timezone.utc).isoformat()
    create = {
        "tenant_context": {"organization_id": org, "tenant_id": tenant}, "operation": "create",
        "idempotency_key": create_test_identifier(f"relationship-create-{token}"), "payload_hash": create_test_identifier(f"relationship-hash-{token}"),
        "correlation_id": create_test_identifier(f"relationship-correlation-{token}"),
        "relationship_record": _record(relationship_id, org, tenant, {"source_entity_id": source_id, "target_entity_id": target_id, "relationship_type": "depends_on", "source_system": "p3test-live-validation", "source_identifier": create_test_identifier(f"relationship-source-{token}"), "version": 1}),
        "lineage_events": [_record(lineage_id, org, tenant, {"relationship_id": relationship_id, "event_type": "relationship_created", "occurred_at": now})],
        "provenance_records": [_record(provenance_id, org, tenant, {"relationship_id": relationship_id, "source_system": "p3test-live-validation", "source_identifier": create_test_identifier(f"relationship-provenance-{token}"), "captured_at": now}, payload_hash=create_test_identifier(f"relationship-provenance-hash-{token}"))],
    }
    committed = db.rpc("data_fabric_atomic_relationship_write", {"p_request": create}).execute().data
    replayed = db.rpc("data_fabric_atomic_relationship_write", {"p_request": create}).execute().data
    assert committed["status"] == "committed" and committed["version_created"] is False
    assert committed["lineage_ids"] == [lineage_id] and committed["provenance_ids"] == [provenance_id]
    assert replayed["status"] == "replayed"
    row = db.table("enterprise_relationships").select("*").eq("id", relationship_id).eq("organization_id", org).eq("tenant_id", tenant).execute().data
    assert len(row) == 1 and row[0]["source_entity_id"] == source_id and row[0]["target_entity_id"] == target_id

    update = {**create, "operation": "update", "expected_revision": 1, "idempotency_key": create_test_identifier(f"relationship-update-{token}"), "payload_hash": create_test_identifier(f"relationship-update-hash-{token}"), "lineage_events": [], "provenance_records": []}
    updated = db.rpc("data_fabric_atomic_relationship_write", {"p_request": update}).execute().data
    assert updated["resulting_revision"] == 2 and updated["resulting_version"] == 2
    stale = {**update, "expected_revision": 1, "idempotency_key": create_test_identifier(f"relationship-stale-{token}"), "payload_hash": create_test_identifier(f"relationship-stale-hash-{token}")}
    assert "P3_REVISION_CONFLICT" in _rpc_error(db, "data_fabric_atomic_relationship_write", stale)

    invalid = {**create, "idempotency_key": create_test_identifier(f"relationship-invalid-{token}"), "payload_hash": create_test_identifier(f"relationship-invalid-hash-{token}")}
    invalid["relationship_record"] = _record(str(uuid4()), org, tenant, {"source_entity_id": source_id, "target_entity_id": target_id, "relationship_type": "uses", "source_system": "p3test-live-validation", "source_identifier": create_test_identifier(f"invalid-source-{token}"), "version": 1})
    invalid["lineage_events"] = [_record(str(uuid4()), org, tenant, {"relationship_id": str(uuid4()), "event_type": "invalid", "occurred_at": now})]
    assert "P3_TENANT_BOUNDARY" in _rpc_error(db, "data_fabric_atomic_relationship_write", invalid)

    deactivate = {**update, "operation": "deactivate", "expected_revision": 2, "idempotency_key": create_test_identifier(f"relationship-cleanup-{token}"), "payload_hash": create_test_identifier(f"relationship-cleanup-hash-{token}")}
    deactivated = db.rpc("data_fabric_atomic_relationship_write", {"p_request": deactivate}).execute().data
    assert deactivated["resulting_revision"] == 3
    for entity_id in (source_id, target_id):
        assert len(db.table("enterprise_entities").delete().eq("id", entity_id).eq("organization_id", org).eq("tenant_id", tenant).execute().data or []) == 1
    print("P3_RELATIONSHIP_COUNTS rpc=8 reads=1 committed_writes=12 rejected=2 rollbacks=2 cleanup=3 history=deferred")
