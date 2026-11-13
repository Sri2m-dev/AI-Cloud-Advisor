from datetime import datetime, timezone
from uuid import UUID

import pytest

from repositories.g08_canonical_gateway import PostgresCanonicalOwnerPersistence
from services.g08_owner_authorization import (
    OperatorAssertion,
    OwnerDenied,
)

AUTHORIZATION_ID = "10000000-0000-4000-8000-000000000001"
OPERATION_ID = "10000000-0000-4000-8000-000000000002"
TENANT_ID = "20000000-0000-4000-8000-000000000001"
OPERATOR_UID = "30000000-0000-4000-8000-000000000001"
EVENT_ID = "40000000-0000-4000-8000-000000000001"
NOW = datetime(2026, 11, 11, 12, tzinfo=timezone.utc)


class Cursor:
    def __init__(self, value):
        self.value = value
        self.query = None
        self.params = None

    def execute(self, query, params):
        self.query = query
        self.params = params

    def fetchone(self):
        return (self.value,)


def operator_assertion(**overrides):
    values = {
        "assertion_id": "50000000-0000-4000-8000-000000000001",
        "authorization_id": AUTHORIZATION_ID,
        "operation_id": OPERATION_ID,
        "purpose": "RECONCILIATION",
        "person_ref": "synthetic-operator",
        "authentication_evidence_ref": "synthetic-operator-evidence",
        "authentication_evidence_sha256": "a" * 64,
        "session_binding_ref": "synthetic-session",
        "db_session_user": "nxr_g08_gateway_test",
        "verified_auth_uid": OPERATOR_UID,
        "verifier_ref": "synthetic-test-verifier",
        "verified_at": NOW,
        "valid_until": NOW.replace(hour=13),
        "tenant_id": TENANT_ID,
        "organization_id": TENANT_ID,
        "action": "grant",
        "target_resource": "synthetic-administrator",
        "policy_version": "test-v1",
        "requester_auth_uid": "60000000-0000-4000-8000-000000000001",
        "approval_ids": ("70000000-0000-4000-8000-000000000001",),
        "evidence_jti": "synthetic-operator-jti",
    }
    values.update(overrides)
    return OperatorAssertion(**values)


def test_receipt_reader_calls_tenant_scoped_sql_projection():
    receipt = {
        "authorization_id": AUTHORIZATION_ID,
        "owner_operation_id": OPERATION_ID,
        "event_id": EVENT_ID,
        "evidence_id": "80000000-0000-4000-8000-000000000001",
        "assertion_id": "50000000-0000-4000-8000-000000000001",
        "operator_person_ref": "synthetic-operator",
        "db_session_user": "nxr_g08_gateway_test",
        "idempotency_key": "idempotency-1",
        "canonical_request": {"version": "nxr-g08-owner-administration-v1"},
        "request_digest": "b" * 64,
        "occurred_at": NOW.isoformat(),
        "result": {"event_id": EVENT_ID},
        "tenant_id": TENANT_ID,
        "organization_id": TENANT_ID,
    }
    cursor = Cursor(receipt)

    result = PostgresCanonicalOwnerPersistence().read_receipt(
        cursor, AUTHORIZATION_ID, OPERATION_ID, operator_assertion()
    )

    assert result is not None
    assert result.event_id == EVENT_ID
    assert result.tenant_id == TENANT_ID
    assert result.canonical_bytes
    assert "g08_gateway_read_owner_receipt" in cursor.query
    assert cursor.params == (
        str(UUID(AUTHORIZATION_ID)),
        str(UUID(OPERATION_ID)),
        str(UUID(TENANT_ID)),
        str(UUID(TENANT_ID)),
        "test-v1",
        str(UUID(OPERATOR_UID)),
    )


def test_receipt_reader_rejects_missing_verified_scope_before_sql():
    cursor = Cursor(None)

    with pytest.raises(OwnerDenied, match="tenant-scoped"):
        PostgresCanonicalOwnerPersistence().read_receipt(
            cursor, AUTHORIZATION_ID, OPERATION_ID, operator_assertion(tenant_id=None)
        )

    assert cursor.query is None


def test_owner_operation_load_does_not_project_unscoped_receipt():
    cursor = Cursor(
        {
            "authorization": {
                "authorization_id": AUTHORIZATION_ID,
                "owner_operation_id": OPERATION_ID,
                "operator_person_ref": "synthetic-operator",
                "operator_authentication_evidence_ref": "synthetic-evidence",
                "operator_authentication_evidence_sha256": "a" * 64,
                "valid_from": NOW.isoformat(),
                "valid_to": NOW.replace(hour=13).isoformat(),
                "operation": "grant",
                "administrator_id": "90000000-0000-4000-8000-000000000001",
                "expected_revision": None,
                "mutation": {"subject_auth_uid": OPERATOR_UID},
                "scope_key": "global",
                "policy_version": "test-v1",
                "requester_person_ref": "synthetic-requester",
                "authorization_sha256": "c" * 64,
                "approval_manifest_sha256": "d" * 64,
                "intent_sha256": "e" * 64,
                "evidence_ref": "synthetic-evidence",
            },
            "policy": {
                "tenant_id": TENANT_ID,
                "organization_id": TENANT_ID,
                "target_resource": "synthetic-administrator",
                "requester_uid": "60000000-0000-4000-8000-000000000001",
                "version": "test-v1",
            },
            "history": [
                {
                    "status_id": "a0000000-0000-4000-8000-000000000001",
                    "revision": 1,
                    "predecessor_status_id": None,
                    "predecessor_revision": None,
                    "status": "ADMITTED",
                    "occurred_at": NOW.isoformat(),
                }
            ],
            "consumed": True,
            "receipt": {"private_result": "must not be projected"},
        }
    )

    snapshot = PostgresCanonicalOwnerPersistence().load(cursor, OPERATION_ID)

    assert snapshot is not None
    assert snapshot.consumed
    assert snapshot.receipt is None
