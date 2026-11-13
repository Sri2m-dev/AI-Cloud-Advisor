"""Opt-in real PostgreSQL qualification against the approved isolated G08 target."""

from __future__ import annotations

import hashlib
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from threading import Barrier, Event
from time import monotonic, sleep
from uuid import uuid4

import psycopg2
import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from psycopg2.extensions import parse_dsn

from repositories.g08_canonical_gateway import PostgresCanonicalOwnerPersistence
from repositories.g08_postgres_authority import (
    PostgresFenceGenerationStore,
    PostgresG08PolicyAuthority,
    PostgresG08UnitOfWork,
)
from services.g08_owner_authorization import (
    Authorization,
    ExecutionRequest,
    OwnerAuthorizationCoordinator,
    OwnerDenied,
)
from services.g08_transaction_boundary import CommitOutcomeUnknown
from services.g08_trust_contract import (
    G08TrustRequest,
    SignedD08TechnicalEvidenceVerifier,
    SignedEnvelope,
    SignedEvidenceVerifier,
    SignedG08OwnerTrust,
    SignedTransactionalFencingVerifier,
    canonical_claims,
)

DATABASE_NAME = "nexora_m2c_g08gateway_20261111"
RUNTIME_ROLE = "nxr_g08_qual_runtime"
TENANT_ID = "10000000-0000-4000-8000-000000000001"
REQUESTER_UID = "30000000-0000-4000-8000-000000000001"
OPERATOR_UID = "30000000-0000-4000-8000-000000000002"
APPROVER_UIDS = (
    "30000000-0000-4000-8000-000000000003",
    "30000000-0000-4000-8000-000000000004",
)
SUBJECT_UID = "30000000-0000-4000-8000-000000000005"


def _connection():
    dsn = os.environ.get("NEXORA_G08_LIVE_TEST_DSN")
    if not dsn or os.environ.get("NEXORA_G08_LIVE_TEST_ALLOW") != "YES":
        pytest.skip("explicit approved isolated G08 runtime DSN is not configured")
    params = parse_dsn(dsn)
    if (
        params.get("dbname") != DATABASE_NAME
        or params.get("host") != "database"
        or params.get("user") != RUNTIME_ROLE
    ):
        pytest.fail("live G08 test refuses any database or role outside the approved target")
    connection = psycopg2.connect(dsn)
    cursor = connection.cursor()
    cursor.execute(
        "SELECT session_user, current_database(), current_setting('server_version_num'), "
        "has_table_privilege(session_user, "
        "'public.g08_d10_policy_versions', 'SELECT')"
    )
    identity = cursor.fetchone()
    connection.rollback()
    if identity != (RUNTIME_ROLE, DATABASE_NAME, "170011", False):
        connection.close()
        pytest.fail("live test database identity or least-privilege boundary differs")
    return connection


def _sign(key_id: str, claims: dict, key: Ed25519PrivateKey) -> SignedEnvelope:
    return SignedEnvelope(key_id, claims, key.sign(canonical_claims(claims)))


def _hash(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _iso(value: datetime) -> str:
    return value.isoformat()


def _verifier(
    audience: str,
    key_map: dict[str, Ed25519PrivateKey],
    subject_map: dict[str, str] | None = None,
    subject_claim: str = "sub",
    revoked=None,
) -> SignedEvidenceVerifier:
    return SignedEvidenceVerifier(
        {name: key.public_key() for name, key in key_map.items()},
        audience=audience,
        is_revoked=revoked or (lambda _jti: False),
        subject_by_key=subject_map,
        subject_claim=subject_claim,
    )


def test_real_synthetic_owner_admission_execution_receipt_and_reconciliation():
    connection = _connection()
    cursor = connection.cursor()
    with pytest.raises(psycopg2.errors.InsufficientPrivilege):
        cursor.execute("SELECT * FROM public.g08_d10_policy_versions")
    connection.rollback()
    now = datetime.now(timezone.utc)
    expires = now + timedelta(hours=1)
    auth_id, operation_id, administrator_id = (str(uuid4()) for _ in range(3))
    event_id = str(uuid4())
    status_id = str(uuid4())
    policy_id, policy_version = str(uuid4()), "synthetic-v1"
    approval_ids = tuple(sorted(str(uuid4()) for _ in range(2)))
    approval_jtis = (str(uuid4()), str(uuid4()))
    operator_jti, fence_jti = str(uuid4()), str(uuid4())
    app_session_id = str(uuid4())
    action = "grant"
    resource = f"synthetic-owner-resource:{operation_id}"
    idempotency_key = f"synthetic-{operation_id}"
    operator_person = f"synthetic-operator:{OPERATOR_UID}"
    operator_digest = _hash(b"isolated synthetic operator authentication evidence")
    mutation = {
        "subject_auth_uid": SUBJECT_UID,
        "valid_from": _iso(now - timedelta(seconds=5)),
        "valid_to": _iso(expires),
        "rationale": "isolated synthetic G08 qualification",
    }

    app_key = Ed25519PrivateKey.generate()
    operator_key = Ed25519PrivateKey.generate()
    policy_key = Ed25519PrivateKey.generate()
    approval_keys = [Ed25519PrivateKey.generate() for _ in APPROVER_UIDS]
    fence_key = Ed25519PrivateKey.generate()
    d08_key = Ed25519PrivateKey.generate()

    operator_claims = {
        "jti": operator_jti,
        "aud": "g08-operator-evidence",
        "iat": _iso(now - timedelta(seconds=2)),
        "exp": _iso(expires),
        "sub": OPERATOR_UID,
        "person_ref": operator_person,
        "evidence_ref": f"synthetic-operator-evidence:{operator_jti}",
        "evidence_sha256": operator_digest,
        "session_binding_ref": app_session_id,
    }
    operator_envelope = _sign("synthetic-operator-key", operator_claims, operator_key)
    approval_envelopes = []
    approval_manifest = []
    for approval_id, jti, approver_uid, key in zip(
        approval_ids, approval_jtis, APPROVER_UIDS, approval_keys
    ):
        claims = {
            "jti": jti,
            "aud": "nexora-g08-owner-approval",
            "iat": _iso(now - timedelta(seconds=2)),
            "exp": _iso(expires),
            "approval_id": approval_id,
            "policy_id": policy_id,
            "policy_version": policy_version,
            "authorization_id": auth_id,
            "operation_id": operation_id,
            "tenant_id": TENANT_ID,
            "organization_id": TENANT_ID,
            "action": action,
            "target_resource": resource,
            "requester_uid": REQUESTER_UID,
            "approver_uid": approver_uid,
        }
        envelope = _sign(f"synthetic-approver-{approver_uid}", claims, key)
        approval_envelopes.append(envelope)
        approval_manifest.append(
            {
                "authorization_id": auth_id,
                "approval_ref": approval_id,
                "approver_person_ref": approver_uid,
                "attestation_sha256": _hash(envelope.signature),
                "evidence_ref": f"d10-approval:{jti}",
            }
        )
    approval_manifest.sort(key=lambda item: item["approval_ref"])
    manifest_digest = _hash(canonical_claims(approval_manifest))
    intent_digest = _hash(
        canonical_claims(
            {
                "authorization_id": auth_id,
                "operation_id": operation_id,
                "action": action,
                "tenant_id": TENANT_ID,
                "resource": resource,
                "mutation": mutation,
            }
        )
    )
    authorization_digest = _hash(
        canonical_claims(
            {
                "authorization_id": auth_id,
                "operation_id": operation_id,
                "operator_person_ref": operator_person,
                "operator_evidence_sha256": operator_digest,
                "approval_manifest_sha256": manifest_digest,
                "policy_version": policy_version,
                "intent_sha256": intent_digest,
                "mutation": mutation,
            }
        )
    )

    admission_claims = {
        "jti": str(uuid4()),
        "aud": "nexora-g08-d08-technical",
        "sub": "synthetic-d08-authority",
        "iat": _iso(now - timedelta(seconds=2)),
        "exp": _iso(expires),
        "phase": "ADMISSION",
        "authorization_id": auth_id,
        "operation_id": operation_id,
        "tenant_id": TENANT_ID,
        "organization_id": TENANT_ID,
        "action": action,
        "target_resource": resource,
        "evidence_ref": "synthetic-d08-admission",
    }
    admission_envelope = _sign("synthetic-d08-key", admission_claims, d08_key)
    admission_ref = (
        f"{admission_claims['evidence_ref']}:"
        f"{_hash(canonical_claims(admission_claims) + admission_envelope.signature)}"
    )
    authorization = Authorization(
        authorization_id=auth_id,
        operation_id=operation_id,
        operator_person_ref=operator_person,
        authentication_evidence_ref=operator_claims["evidence_ref"],
        authentication_evidence_sha256=operator_digest,
        valid_from=now - timedelta(seconds=5),
        valid_to=expires,
        tenant_id=TENANT_ID,
        organization_id=TENANT_ID,
        action=action,
        target_resource=resource,
        policy_version=policy_version,
        requester_auth_uid=REQUESTER_UID,
        administrator_id=administrator_id,
        expected_revision=None,
        mutation=mutation,
        scope_key="global",
        authorization_sha256=authorization_digest,
        approval_manifest_sha256=manifest_digest,
        intent_sha256=intent_digest,
        evidence_ref=admission_ref,
        requester_person_ref=f"synthetic-requester:{REQUESTER_UID}",
    )

    canonical_request = {
        "version": "nxr-g08-owner-administration-v1",
        "owner_operation_id": operation_id,
        "operation": action,
        "scope_key": "global",
        "authorization_id": auth_id,
        "authorization_sha256": authorization_digest,
        "approval_manifest_sha256": manifest_digest,
        "policy_version": policy_version,
        "operator": {
            "person_ref": operator_person,
            "authentication_evidence_sha256": operator_digest,
            "verified_auth_uid": OPERATOR_UID,
            "db_session_user": RUNTIME_ROLE,
        },
        "procedure_identity": "nxr_g08_postgres_owner_gateway",
        "procedure_version": "candidate-v1",
        "mutation": mutation,
        "idempotency_key": idempotency_key,
    }
    canonical_bytes = canonical_claims(canonical_request)
    request = ExecutionRequest(
        idempotency_key=idempotency_key,
        canonical_bytes=canonical_bytes,
        request_digest=_hash(canonical_bytes),
    )

    policy_claims = {
        "jti": str(uuid4()),
        "aud": "nexora-g08-d10-policy",
        "sub": "synthetic-d10-authority",
        "iat": _iso(now - timedelta(seconds=2)),
        "exp": _iso(expires),
        "not_before": _iso(now - timedelta(seconds=2)),
        "expires_at": _iso(expires),
        "policy_id": policy_id,
        "version": policy_version,
        "authority_class": "SYNTHETIC_QUALIFICATION",
        "authorization_id": auth_id,
        "operation_id": operation_id,
        "tenant_id": TENANT_ID,
        "organization_id": TENANT_ID,
        "action": action,
        "target_resource": resource,
        "requester_uid": REQUESTER_UID,
        "requester_person_ref": f"synthetic-requester:{REQUESTER_UID}",
        "allowed_operator_uids": [OPERATOR_UID],
        "approval_threshold": 2,
        "allowed_phases": ["ADMISSION", "EXECUTION", "RECONCILIATION"],
        "distinct_identity_pairs": [["requester", "approver"], ["operator", "approver"]],
        "request_digest": request.request_digest,
        "receipt_reader_uids": [REQUESTER_UID, OPERATOR_UID],
    }
    policy_envelope = _sign("synthetic-d10-key", policy_claims, policy_key)

    app_claims = {
        "jti": str(uuid4()),
        "aud": "nexora-app-session",
        "iat": _iso(now - timedelta(seconds=2)),
        "exp": _iso(expires),
        "sub": REQUESTER_UID,
        "tenant_id": TENANT_ID,
        "organization_id": TENANT_ID,
        "session_id": app_session_id,
        "db_session_user": RUNTIME_ROLE,
    }
    app_envelope = _sign("synthetic-app-key", app_claims, app_key)
    fence_claims = {
        "jti": fence_jti,
        "aud": "nexora-g08-fence",
        "sub": "synthetic-fencing-authority",
        "iat": _iso(now - timedelta(seconds=2)),
        "exp": _iso(expires),
        "authorization_id": auth_id,
        "operation_id": operation_id,
        "tenant_id": TENANT_ID,
        "organization_id": TENANT_ID,
        "action": action,
        "target_resource": resource,
        "generation": 1,
    }
    fence_envelope = _sign("synthetic-fence-key", fence_claims, fence_key)
    technical_claims = {
        "jti": str(uuid4()),
        "aud": "nexora-g08-d08-technical",
        "sub": "synthetic-d08-authority",
        "iat": _iso(now - timedelta(seconds=2)),
        "exp": _iso(expires),
        "authorization_id": auth_id,
        "operation_id": operation_id,
        "tenant_id": TENANT_ID,
        "organization_id": TENANT_ID,
        "action": action,
        "target_resource": resource,
        "request_digest": request.request_digest,
        "event_id": event_id,
        "evidence_ref": "synthetic-d08-execution",
        "verifier_ref": "synthetic-d08-verifier",
        "result": {"event_id": event_id, "status": "synthetic-grant-applied"},
    }
    technical_envelope = _sign("synthetic-d08-key", technical_claims, d08_key)
    context = G08TrustRequest(
        app_envelope,
        operator_envelope,
        policy_version,
        fence_envelope,
        technical_envelope,
        admission_envelope,
    )

    authority = PostgresG08PolicyAuthority(connection)
    policy_verifier = _verifier(
        "nexora-g08-d10-policy",
        {"synthetic-d10-key": policy_key},
        {"synthetic-d10-key": "synthetic-d10-authority"},
    )
    approval_verifier = _verifier(
        "nexora-g08-owner-approval",
        {
            f"synthetic-approver-{uid}": key
            for uid, key in zip(APPROVER_UIDS, approval_keys)
        },
        {f"synthetic-approver-{uid}": uid for uid in APPROVER_UIDS},
        "approver_uid",
    )
    application_verifier = _verifier(
        "nexora-app-session",
        {"synthetic-app-key": app_key},
        {"synthetic-app-key": REQUESTER_UID},
    )
    d08_verifier = _verifier(
        "nexora-g08-d08-technical",
        {"synthetic-d08-key": d08_key},
        {"synthetic-d08-key": "synthetic-d08-authority"},
    )
    persistence = PostgresCanonicalOwnerPersistence()

    def coordinator_for(active_connection):
        scoped_authority = PostgresG08PolicyAuthority(active_connection)
        operator_verifier = _verifier(
            "g08-operator-evidence",
            {"synthetic-operator-key": operator_key},
            {"synthetic-operator-key": OPERATOR_UID},
            revoked=lambda jti: scoped_authority.is_evidence_revoked(jti, auth_id),
        )
        fence_verifier = _verifier(
            "nexora-g08-fence",
            {"synthetic-fence-key": fence_key},
            {"synthetic-fence-key": "synthetic-fencing-authority"},
            revoked=lambda jti: scoped_authority.is_fencing_token_revoked(jti, auth_id),
        )
        trust = SignedG08OwnerTrust(
            application_sessions=application_verifier,
            operator_evidence=operator_verifier,
            policy_authority=scoped_authority,
            policy_verifier=policy_verifier,
            approval_verifier=approval_verifier,
            fencing_verifier=SignedTransactionalFencingVerifier(
                fence_verifier, PostgresFenceGenerationStore()
            ),
            technical_verifier=SignedD08TechnicalEvidenceVerifier(d08_verifier),
        )
        return OwnerAuthorizationCoordinator(trust), scoped_authority, fence_verifier

    coordinator, authority, fence_verifier = coordinator_for(connection)
    try:
        tx = PostgresG08UnitOfWork(connection, persistence)
        admitted = tx.bootstrap_and_admit(
            coordinator,
            authorization,
            context,
            status_id,
            policy_envelope,
            tuple(approval_envelopes),
            policy_verifier,
            approval_verifier,
        )
        assert admitted.value == status_id

        fence_tx = PostgresG08UnitOfWork(connection, persistence)
        fence_tx.begin_read_committed()
        scope = {
            "authorization_id": auth_id,
            "operation_id": operation_id,
            "tenant_id": TENANT_ID,
            "organization_id": TENANT_ID,
            "action": action,
            "target_resource": resource,
        }
        PostgresFenceGenerationStore().advance_generation_in_transaction(
            fence_tx, scope, fence_envelope, fence_verifier, now
        )
        fence_tx.commit()

        stale_context = G08TrustRequest(
            app_envelope,
            operator_envelope,
            policy_version,
            _sign(
                "synthetic-fence-key",
                dict(fence_claims, jti=str(uuid4()), generation=2),
                fence_key,
            ),
            technical_envelope,
            admission_envelope,
        )
        stale_fence_tx = PostgresG08UnitOfWork(connection, persistence)
        with pytest.raises(OwnerDenied, match="stale or invalid fencing generation"):
            coordinator.execute(stale_fence_tx, operation_id, stale_context, request)

        revocation_key = Ed25519PrivateKey.generate()
        revocation_verifier = _verifier(
            "nexora-g08-d10-revocation",
            {"synthetic-revocation-key": revocation_key},
            {"synthetic-revocation-key": "synthetic-d10-revocation-authority"},
        )
        revocation_claims = {
            "jti": str(uuid4()),
            "aud": "nexora-g08-d10-revocation",
            "sub": "synthetic-d10-revocation-authority",
            "iat": _iso(now - timedelta(seconds=1)),
            "exp": _iso(expires),
            "authorization_id": auth_id,
            "subject_type": "FENCING_TOKEN",
            "subject_id": fence_jti,
            "revoked_at": _iso(now),
            "revocation_id": str(uuid4()),
        }
        revocation_envelope = _sign(
            "synthetic-revocation-key", revocation_claims, revocation_key
        )
        revocation_locked = Event()
        execution_ready = Event()
        release_revocation = Event()
        execution_pid = []

        def persist_revocation():
            revocation_connection = _connection()
            try:
                revocation_connection.cursor().execute("SELECT 1")
                PostgresG08PolicyAuthority(revocation_connection).append_revocation(
                    auth_id, revocation_envelope, revocation_verifier, now
                )
                revocation_locked.set()
                if not release_revocation.wait(timeout=15):
                    raise TimeoutError("execution did not reach the revocation lock")
                revocation_connection.commit()
            finally:
                revocation_connection.rollback()
                revocation_connection.close()

        def execute_during_revocation():
            race_connection = _connection()
            try:
                cursor = race_connection.cursor()
                cursor.execute("SELECT pg_backend_pid()")
                execution_pid.append(cursor.fetchone()[0])
                race_connection.commit()
                race_coordinator, _, _ = coordinator_for(race_connection)
                race_tx = PostgresG08UnitOfWork(race_connection, persistence)
                execution_ready.set()
                try:
                    race_coordinator.execute(
                        race_tx, operation_id, context, request
                    )
                except OwnerDenied as error:
                    return str(error)
                return "executed"
            finally:
                race_connection.rollback()
                race_connection.close()

        with ThreadPoolExecutor(max_workers=2) as workers:
            revocation_future = workers.submit(persist_revocation)
            assert revocation_locked.wait(timeout=10)
            execution_future = workers.submit(execute_during_revocation)
            assert execution_ready.wait(timeout=10)

            monitor_connection = _connection()
            try:
                deadline = monotonic() + 10
                blocked = False
                while monotonic() < deadline:
                    monitor_cursor = monitor_connection.cursor()
                    monitor_cursor.execute(
                        "SELECT cardinality(pg_blocking_pids(%s)) > 0",
                        (execution_pid[0],),
                    )
                    blocked = bool(monitor_cursor.fetchone()[0])
                    monitor_connection.rollback()
                    if blocked:
                        break
                    sleep(0.01)
                assert blocked, "execution did not block on the held D10 revocation lock"
            finally:
                monitor_connection.close()
                release_revocation.set()
            revocation_future.result(timeout=15)
            assert "revoked" in execution_future.result(timeout=15)
        assert PostgresG08PolicyAuthority(connection).is_fencing_token_revoked(
            fence_jti, auth_id
        )
        connection.rollback()
        connection.close()
        connection = _connection()
        coordinator, authority, fence_verifier = coordinator_for(connection)

        current_fence_jti = str(uuid4())
        current_fence_claims = dict(
            fence_claims, jti=current_fence_jti, generation=2
        )
        current_fence_envelope = _sign(
            "synthetic-fence-key", current_fence_claims, fence_key
        )
        current_fence_tx = PostgresG08UnitOfWork(connection, persistence)
        current_fence_tx.begin_read_committed()
        PostgresFenceGenerationStore().advance_generation_in_transaction(
            current_fence_tx, scope, current_fence_envelope, fence_verifier, now
        )
        current_fence_tx.commit()
        context = G08TrustRequest(
            app_envelope,
            operator_envelope,
            policy_version,
            current_fence_envelope,
            technical_envelope,
            admission_envelope,
        )

        expired_app_claims = dict(
            app_claims,
            jti=str(uuid4()),
            iat=_iso(now - timedelta(minutes=2)),
            exp=_iso(now - timedelta(minutes=1)),
        )
        expired_context = G08TrustRequest(
            _sign("synthetic-app-key", expired_app_claims, app_key),
            operator_envelope,
            policy_version,
            current_fence_envelope,
            technical_envelope,
            admission_envelope,
        )
        expired_session_tx = PostgresG08UnitOfWork(connection, persistence)
        with pytest.raises(OwnerDenied, match="currently valid"):
            coordinator.execute(
                expired_session_tx, operation_id, expired_context, request
            )

        expired_policy_tx = PostgresG08UnitOfWork(connection, persistence)
        expired_policy_tx.begin_read_committed()
        with pytest.raises(OwnerDenied, match="transactional D10 authority"):
            authority.assert_current_in_transaction(
                expired_policy_tx,
                auth_id,
                policy_version,
                tuple(approval_ids),
                expires + timedelta(seconds=1),
                operator_jti,
                {
                    **scope,
                    "requester_uid": REQUESTER_UID,
                    "operator_uid": OPERATOR_UID,
                    "fence_jti": current_fence_jti,
                    "fence_generation": 2,
                },
            )
        expired_policy_tx.rollback()

        stale_policy_tx = PostgresG08UnitOfWork(connection, persistence)
        stale_policy_tx.begin_read_committed()
        with pytest.raises(OwnerDenied) as stale_policy_error:
            authority.assert_current_in_transaction(
                stale_policy_tx,
                auth_id,
                "stale-policy-version",
                tuple(approval_ids),
                now,
                operator_jti,
                {
                    **scope,
                    "requester_uid": REQUESTER_UID,
                    "operator_uid": OPERATOR_UID,
                    "fence_jti": current_fence_jti,
                    "fence_generation": 2,
                },
            )
        assert (
            stale_policy_error.value.__cause__.diag.message_primary
            == "D10 policy changed before owner execution"
        )
        stale_policy_tx.rollback()

        forged_approval = SignedEnvelope(
            approval_envelopes[0].key_id,
            approval_envelopes[0].claims,
            b"x" * 64,
        )
        with pytest.raises(OwnerDenied, match="signature"):
            approval_verifier.verify_subject_bound(forged_approval, now)

        barrier = Barrier(2)

        def execute_concurrently():
            worker_connection = _connection()
            try:
                worker_coordinator, _, _ = coordinator_for(worker_connection)
                worker_tx = PostgresG08UnitOfWork(worker_connection, persistence)
                commit = worker_tx.commit

                def commit_but_drop_acknowledgment():
                    commit()
                    raise psycopg2.OperationalError(
                        "synthetic lost acknowledgment after server commit"
                    )

                worker_tx.commit = commit_but_drop_acknowledgment
                barrier.wait(timeout=15)
                try:
                    worker_coordinator.execute(worker_tx, operation_id, context, request)
                except CommitOutcomeUnknown:
                    return "lost-ack"
                except OwnerDenied:
                    return None
                return "unexpected-success"
            finally:
                worker_connection.rollback()
                worker_connection.close()

        with ThreadPoolExecutor(max_workers=2) as workers:
            results = list(workers.map(lambda _: execute_concurrently(), range(2)))
        assert results.count("lost-ack") == 1
        assert results.count(None) == 1

        reconciliation_connection = _connection()
        try:
            reconciliation_coordinator, _, _ = coordinator_for(
                reconciliation_connection
            )
            reader_tx = PostgresG08UnitOfWork(
                reconciliation_connection, persistence
            )
            reconciled = reconciliation_coordinator.reconcile(
                reader_tx, operation_id, context, request
            )
            receipt = reconciled.value
            assert receipt.event_id == event_id
            assert receipt.result["event_id"] == event_id
        finally:
            reconciliation_connection.rollback()
            reconciliation_connection.close()

        duplicate_tx = PostgresG08UnitOfWork(connection, persistence)
        with pytest.raises(OwnerDenied, match="consumed"):
            coordinator.execute(duplicate_tx, operation_id, context, request)

        cross_tenant_claims = dict(
            app_claims,
            jti=str(uuid4()),
            tenant_id="20000000-0000-4000-8000-000000000002",
            organization_id="20000000-0000-4000-8000-000000000002",
        )
        cross_tenant_context = G08TrustRequest(
            _sign("synthetic-app-key", cross_tenant_claims, app_key),
            operator_envelope,
            policy_version,
            fence_envelope,
            technical_envelope,
            admission_envelope,
        )
        cross_tx = PostgresG08UnitOfWork(connection, persistence)
        with pytest.raises(OwnerDenied, match="authenticated tenant and operation"):
            coordinator.reconcile(cross_tx, operation_id, cross_tenant_context, request)

        cross_organization_claims = dict(
            app_claims,
            jti=str(uuid4()),
            organization_id="20000000-0000-4000-8000-000000000002",
        )
        cross_organization_context = G08TrustRequest(
            _sign("synthetic-app-key", cross_organization_claims, app_key),
            operator_envelope,
            policy_version,
            current_fence_envelope,
            technical_envelope,
            admission_envelope,
        )
        cross_organization_tx = PostgresG08UnitOfWork(connection, persistence)
        with pytest.raises(OwnerDenied):
            coordinator.reconcile(
                cross_organization_tx,
                operation_id,
                cross_organization_context,
                request,
            )

        audit = PostgresG08UnitOfWork(connection, persistence)
        audit.begin_read_committed()
        audit.cursor.execute(
            "SELECT public.g08_gateway_load_owner_operation(%s::uuid)",
            (operation_id,),
        )
        operation_projection = audit.cursor.fetchone()[0]
        assert operation_projection["consumed"] is True
        audit.rollback()
    finally:
        connection.rollback()
        connection.close()
