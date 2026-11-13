"""Signed synthetic-provider contract tests; no live identity, D10, or database claim."""

import hashlib
import json
from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from services.g08_owner_authorization import (
    Authorization,
    ExecutionRequest,
    OwnerAuthorizationCoordinator,
    OwnerDenied,
    OwnerDependencyUnavailable,
    OwnerReceipt,
    OwnerSnapshot,
    StatusEntry,
)
from services.g08_transaction_boundary import DurableReceipt
from services.g08_trust_contract import (
    G08TrustRequest,
    SignedD08TechnicalEvidenceVerifier,
    SignedEnvelope,
    SignedEvidenceVerifier,
    SignedG08OwnerTrust,
    SignedTransactionalFencingVerifier,
    TenantScopedReceiptProjection,
    VersionedSyntheticD10Authority,
    canonical_claims,
)

NOW = datetime(2026, 11, 11, 12, tzinfo=timezone.utc)
AUTH_ID = "authorization-1"
OPERATION_ID = "operation-1"
TENANT_A = "10000000-0000-4000-8000-000000000001"
TENANT_B = "20000000-0000-4000-8000-000000000002"
REQUESTER_UID = "requester-uid"
OPERATOR_UID = "operator-uid"
APPROVER_UID = "approver-uid"
ACTION = "reconcile"
RESOURCE = "account-set:synthetic-a"


class Fixture:
    def __init__(self, *, fence_generation=7, operator_revoked=None):
        self.app_key = Ed25519PrivateKey.generate()
        self.operator_key = Ed25519PrivateKey.generate()
        self.other_operator_key = Ed25519PrivateKey.generate()
        self.approver_key = Ed25519PrivateKey.generate()
        self.requester_approval_key = Ed25519PrivateKey.generate()
        self.policy_key = Ed25519PrivateKey.generate()
        self.fence_key = Ed25519PrivateKey.generate()
        self.d08_key = Ed25519PrivateKey.generate()
        self.operator_revocations = operator_revoked if operator_revoked is not None else set()
        self.approval_revocations = set()
        self.authorization_revocations = set()
        self.policy_store = VersionedSyntheticD10Authority()
        self.request = make_request()
        self.admission_evidence = sign_claims(
            "d08-key",
            {
                "jti": "d08-admission-jti",
                "aud": "nexora-g08-d08-technical",
                "sub": "d08-synthetic-authority",
                "iat": iso(NOW - timedelta(minutes=1)),
                "exp": iso(NOW + timedelta(minutes=3)),
                "phase": "ADMISSION",
                "authorization_id": AUTH_ID,
                "operation_id": OPERATION_ID,
                "tenant_id": TENANT_A,
                "organization_id": TENANT_A,
                "action": ACTION,
                "target_resource": RESOURCE,
                "evidence_ref": "d08-admission-evidence",
            },
            self.d08_key,
        )
        admission_hash = hashlib.sha256(
            canonical_claims(self.admission_evidence.claims)
            + self.admission_evidence.signature
        ).hexdigest()
        self.authorization = Authorization(
            AUTH_ID,
            OPERATION_ID,
            "operator-person",
            "operator-evidence",
            "c" * 64,
            NOW - timedelta(minutes=5),
            NOW + timedelta(minutes=5),
            tenant_id=TENANT_A,
            organization_id=TENANT_A,
            action=ACTION,
            target_resource=RESOURCE,
            policy_version="p1",
            requester_auth_uid=REQUESTER_UID,
            evidence_ref=f"d08-admission-evidence:{admission_hash}",
        )
        self.application_sessions = self._verifier(
            "nexora-app-session",
            {"app-key": self.app_key},
        )
        self.operator_evidence = self._verifier(
            "g08-operator-evidence",
            {
                "operator-key": self.operator_key,
                "other-operator-key": self.other_operator_key,
            },
            self.operator_revocations,
            subject_by_key={
                "operator-key": OPERATOR_UID,
                "other-operator-key": "role-is-not-authority",
            },
        )
        self.policy_verifier = self._verifier(
            "nexora-g08-d10-policy",
            {"policy-key": self.policy_key},
            subject_by_key={"policy-key": "d10-policy-authority"},
        )
        self.approval_verifier = self._verifier(
            "nexora-g08-owner-approval",
            {
                "approver-key": self.approver_key,
                "requester-approval-key": self.requester_approval_key,
            },
            self.approval_revocations,
            subject_by_key={
                "approver-key": APPROVER_UID,
                "requester-approval-key": REQUESTER_UID,
            },
            subject_claim="approver_uid",
        )
        self.fence_verifier = self._verifier(
            "nexora-g08-fence",
            {"fence-key": self.fence_key},
            subject_by_key={"fence-key": "fencing-authority"},
        )
        self._publish_policy("p1", current=True)
        self.generation_store = GenerationStore(fence_generation)
        self.fencing = SignedTransactionalFencingVerifier(
            self.fence_verifier,
            self.generation_store,
        )
        self.d08_revocations = set()
        self.technical = SignedD08TechnicalEvidenceVerifier(
            self._verifier(
                "nexora-g08-d08-technical",
                {"d08-key": self.d08_key},
                self.d08_revocations,
                subject_by_key={"d08-key": "d08-synthetic-authority"},
            )
        )
        self.trust = self.make_trust()
        self.context = self.make_context()

    @staticmethod
    def _verifier(
        audience,
        keys,
        revoked=None,
        *,
        subject_by_key=None,
        subject_claim="sub",
    ):
        revoked = revoked if revoked is not None else set()
        return SignedEvidenceVerifier(
            {key_id: private.public_key() for key_id, private in keys.items()},
            audience=audience,
            is_revoked=lambda evidence_id: evidence_id in revoked,
            subject_by_key=subject_by_key,
            subject_claim=subject_claim,
        )

    def make_trust(self):
        return SignedG08OwnerTrust(
            application_sessions=self.application_sessions,
            operator_evidence=self.operator_evidence,
            policy_authority=self.policy_store,
            policy_verifier=self.policy_verifier,
            approval_verifier=self.approval_verifier,
            fencing_verifier=self.fencing,
            technical_verifier=self.technical,
        )

    def _publish_policy(self, version, *, current):
        claims = {
            "jti": f"policy-{version}",
            "aud": "nexora-g08-d10-policy",
            "sub": "d10-policy-authority",
            "iat": iso(NOW - timedelta(minutes=1)),
            "exp": iso(NOW + timedelta(minutes=10)),
            "policy_id": "d10-g08-policy",
            "version": version,
            "authorization_id": AUTH_ID,
            "operation_id": OPERATION_ID,
            "tenant_id": TENANT_A,
            "organization_id": TENANT_A,
            "action": ACTION,
            "target_resource": RESOURCE,
            "requester_uid": REQUESTER_UID,
            "allowed_operator_uids": [OPERATOR_UID],
            "approval_threshold": 1,
            "allowed_phases": [
                "ADMISSION",
                "EXECUTION",
                "REVOCATION",
                "INVALIDATION",
                "RECONCILIATION",
            ],
            "distinct_identity_pairs": [["requester", "approver"]],
            "not_before": iso(NOW - timedelta(minutes=1)),
            "expires_at": iso(NOW + timedelta(minutes=10)),
            "request_digest": self.request.request_digest,
            "receipt_reader_uids": [REQUESTER_UID],
        }
        policy = sign_claims("policy-key", claims, self.policy_key)
        approval_claims = {
            "jti": f"approval-token-{version}",
            "aud": "nexora-g08-owner-approval",
            "iat": iso(NOW - timedelta(minutes=1)),
            "exp": iso(NOW + timedelta(minutes=5)),
            "approval_id": f"approval-{version}",
            "policy_id": "d10-g08-policy",
            "policy_version": version,
            "authorization_id": AUTH_ID,
            "operation_id": OPERATION_ID,
            "tenant_id": TENANT_A,
            "organization_id": TENANT_A,
            "action": ACTION,
            "target_resource": RESOURCE,
            "requester_uid": REQUESTER_UID,
            "approver_uid": APPROVER_UID,
        }
        approval = sign_claims("approver-key", approval_claims, self.approver_key)
        self.policy_store.publish(AUTH_ID, version, policy, (approval,), current=current)

    def make_context(self, *, tenant=TENANT_A, operator_uid=OPERATOR_UID, fence_generation=7):
        app_session = sign_claims(
            "app-key",
            {
                "jti": f"session-{tenant}",
                "aud": "nexora-app-session",
                "iat": iso(NOW - timedelta(minutes=1)),
                "exp": iso(NOW + timedelta(minutes=5)),
                "sub": REQUESTER_UID,
                "tenant_id": tenant,
                "organization_id": tenant,
                "session_id": "app-session-1",
                "db_session_user": "nexora_authenticated",
                "role": "Owner",
            },
            self.app_key,
        )
        operator_key_id, operator_key = (
            ("operator-key", self.operator_key)
            if operator_uid == OPERATOR_UID
            else ("other-operator-key", self.other_operator_key)
        )
        op = sign_claims(
            operator_key_id,
            {
                "jti": "operator-jti",
                "aud": "g08-operator-evidence",
                "iat": iso(NOW - timedelta(minutes=1)),
                "exp": iso(NOW + timedelta(minutes=3)),
                "sub": operator_uid,
                "person_ref": "operator-person",
                "evidence_ref": "operator-evidence",
                "evidence_sha256": "c" * 64,
                "session_binding_ref": "app-session-1",
            },
            operator_key,
        )
        fence = sign_claims(
            "fence-key",
            {
                "jti": "fence-jti",
                "aud": "nexora-g08-fence",
                "sub": "fencing-authority",
                "iat": iso(NOW - timedelta(minutes=1)),
                "exp": iso(NOW + timedelta(minutes=1)),
                "authorization_id": AUTH_ID,
                "operation_id": OPERATION_ID,
                "tenant_id": TENANT_A,
                "organization_id": TENANT_A,
                "action": ACTION,
                "target_resource": RESOURCE,
                "generation": fence_generation,
            },
            self.fence_key,
        )
        request = make_request()
        technical = sign_claims(
            "d08-key",
            {
                "jti": "d08-evidence-jti",
                "aud": "nexora-g08-d08-technical",
                "sub": "d08-synthetic-authority",
                "iat": iso(NOW - timedelta(minutes=1)),
                "exp": iso(NOW + timedelta(minutes=3)),
                "authorization_id": AUTH_ID,
                "operation_id": OPERATION_ID,
                "tenant_id": TENANT_A,
                "organization_id": TENANT_A,
                "action": ACTION,
                "target_resource": RESOURCE,
                "request_digest": request.request_digest,
                "event_id": "event-1",
                "evidence_ref": "d08-evidence-1",
                "verifier_ref": "d08-synthetic-verifier",
                "result": {"event_id": "event-1", "status": "reconciled"},
            },
            self.d08_key,
        )
        return G08TrustRequest(
            app_session, op, "p1", fence, technical, self.admission_evidence
        )

    def make_session(self, *, tenant=TENANT_A):
        return self.make_context(tenant=tenant).application_session


class GenerationStore:
    def __init__(self, generation):
        self.generation = generation
        self.calls = 0
        self.revoked = set()

    def is_fencing_token_revoked_in_transaction(self, transaction, scope, evidence_jti):
        assert transaction is not None
        assert scope["tenant_id"] == TENANT_A
        return evidence_jti in self.revoked

    def current_generation_in_transaction(self, transaction, scope):
        self.calls += 1
        assert transaction is not None
        assert scope["tenant_id"] == TENANT_A
        return self.generation


class Transaction:
    session_user = "nexora_authenticated"

    def __init__(self, authorization):
        self.snapshot = OwnerSnapshot(
            authorization,
            (StatusEntry("admitted", 1, None, None, "ADMITTED", NOW - timedelta(seconds=1)),),
            None,
        )
        self.staged = None
        self.effects = 0
        self.calls = []

    def begin_read_committed(self):
        self.calls.append("begin")

    def acquire_global_lock(self):
        self.calls.append("lock")

    def load(self, operation_id):
        self.calls.append("load")
        return self.snapshot if self.snapshot.authorization.operation_id == operation_id else None

    def decision_time(self):
        return NOW

    def stage_execution(self, authorization, request, operator, evidence):
        self.effects += 1
        self.calls.append("execute_and_stage_atomically")
        receipt = OwnerReceipt(
            authorization.authorization_id,
            authorization.operation_id,
            evidence.event_id,
            evidence.evidence_id,
            operator.assertion_id,
            operator.person_ref,
            operator.db_session_user,
            request.idempotency_key,
            request.canonical_bytes,
            request.request_digest,
            evidence.decision_time,
            evidence.result,
            operator.tenant_id,
            operator.organization_id,
        )
        self.staged = receipt
        self.snapshot = replace(self.snapshot, receipt=receipt)
        return receipt

    def commit(self):
        self.calls.append("commit")

    def rollback(self):
        self.calls.append("rollback")


def make_request():
    canonical = json.dumps(
        {"operation_id": OPERATION_ID, "target_resource": RESOURCE, "action": ACTION},
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    return ExecutionRequest("idempotency-1", canonical, hashlib.sha256(canonical).hexdigest())


def sign_claims(key_id, claims, key):
    return SignedEnvelope(key_id, dict(claims), key.sign(canonical_claims(claims)))


def iso(value):
    return value.isoformat()


def test_tenant_scope_and_operator_identity_come_from_separate_signed_evidence():
    fixture = Fixture()
    assertion = fixture.trust.verify_operator(
        fixture.context,
        fixture.authorization,
        "EXECUTION",
        NOW,
    )
    fixture.trust.authorize(
        fixture.authorization, assertion, "EXECUTION", NOW, fixture.context, object()
    )
    assert assertion.tenant_id == TENANT_A
    assert assertion.requester_auth_uid == REQUESTER_UID
    assert assertion.verified_auth_uid == OPERATOR_UID
    assert assertion.verified_auth_uid != assertion.requester_auth_uid
    assert assertion.d10_evidence_ref == "d10:d10-g08-policy:p1"
    with pytest.raises(OwnerDenied, match="verified D10 scope"):
        fixture.trust.authorize(
            fixture.authorization,
            replace(assertion, tenant_id=TENANT_B),
            "EXECUTION",
            NOW,
            fixture.context,
            object(),
        )


def test_d08_technical_evidence_requires_a_valid_signature_and_exact_scope():
    fixture = Fixture()
    context = fixture.context
    valid = context.technical_evidence
    assert valid is not None
    with pytest.raises(OwnerDependencyUnavailable, match="signed D08"):
        fixture.trust.verify_execution(
            fixture.authorization,
            fixture.trust.verify_operator(context, fixture.authorization, "EXECUTION", NOW),
            fixture.request,
            "admitted",
            NOW,
            replace(context, technical_evidence=None),
            object(),
        )
    forged = SignedEnvelope(valid.key_id, valid.claims, b"x" * 64)
    with pytest.raises(OwnerDenied, match="signature"):
        fixture.technical.verify_in_transaction(
            object(),
            fixture.authorization,
            fixture.trust.verify_operator(context, fixture.authorization, "EXECUTION", NOW),
            fixture.request,
            {
                "tenant_id": TENANT_A,
                "organization_id": TENANT_A,
                "action": ACTION,
                "target_resource": RESOURCE,
            },
            NOW,
            forged,
        )
    wrong_scope = dict(valid.claims, target_resource="account-set:other")
    invalid_scope = sign_claims("d08-key", wrong_scope, fixture.d08_key)
    with pytest.raises(OwnerDenied, match="authorized execution scope"):
        fixture.technical.verify_in_transaction(
            object(),
            fixture.authorization,
            fixture.trust.verify_operator(context, fixture.authorization, "EXECUTION", NOW),
            fixture.request,
            {
                "tenant_id": TENANT_A,
                "organization_id": TENANT_A,
                "action": ACTION,
                "target_resource": RESOURCE,
            },
            NOW,
            invalid_scope,
        )


def test_d08_admission_evidence_is_verified_and_bound_to_canonical_authorization():
    fixture = Fixture()
    assertion = fixture.trust.verify_operator(
        fixture.context, fixture.authorization, "ADMISSION", NOW
    )
    fixture.trust.authorize(
        fixture.authorization, assertion, "ADMISSION", NOW, fixture.context, object()
    )
    with pytest.raises(OwnerDependencyUnavailable, match="signed D08 admission"):
        fixture.trust.authorize(
            fixture.authorization,
            assertion,
            "ADMISSION",
            NOW,
            replace(fixture.context, admission_evidence=None),
            object(),
        )
    with pytest.raises(OwnerDenied, match="not bound"):
        fixture.trust.authorize(
            replace(fixture.authorization, evidence_ref="unbound"),
            assertion,
            "ADMISSION",
            NOW,
            fixture.context,
            object(),
        )


def test_operator_issuer_requires_a_trusted_key_to_subject_binding():
    fixture = Fixture()
    fixture.operator_evidence = fixture._verifier(
        "g08-operator-evidence",
        {
            "operator-key": fixture.operator_key,
            "other-operator-key": fixture.other_operator_key,
        },
    )
    fixture.trust = fixture.make_trust()
    with pytest.raises(OwnerDenied, match="no trusted subject binding"):
        fixture.trust.verify_operator(
            fixture.context,
            fixture.authorization,
            "EXECUTION",
            NOW,
        )


def test_tenant_override_and_invalid_application_signature_are_denied():
    fixture = Fixture()
    forged_scope = fixture.make_context(tenant=TENANT_B)
    with pytest.raises(OwnerDenied, match="tenant and operation"):
        fixture.trust.verify_operator(forged_scope, fixture.authorization, "EXECUTION", NOW)
    forged = replace(
        fixture.context.application_session,
        signature=b"x" * len(fixture.context.application_session.signature),
    )
    with pytest.raises(OwnerDenied, match="signature"):
        fixture.trust.verify_operator(
            replace(fixture.context, application_session=forged),
            fixture.authorization,
            "EXECUTION",
            NOW,
        )

    policy = fixture.policy_store.policy(AUTH_ID, "p1")
    approvals = fixture.policy_store.approvals(AUTH_ID, "p1")
    fixture.policy_store = VersionedSyntheticD10Authority()
    fixture.policy_store.publish(
        AUTH_ID,
        "p1",
        replace(policy, signature=b"x" * len(policy.signature)),
        approvals,
    )
    fixture.trust = fixture.make_trust()
    with pytest.raises(OwnerDenied, match="signature"):
        fixture.trust.verify_operator(fixture.context, fixture.authorization, "EXECUTION", NOW)


def test_application_owner_role_does_not_authorize_an_unlisted_operator():
    fixture = Fixture()
    context = fixture.make_context(operator_uid="role-is-not-authority")
    with pytest.raises(OwnerDenied, match="not authorized"):
        fixture.trust.verify_operator(context, fixture.authorization, "EXECUTION", NOW)


def test_revoked_or_expired_operator_and_approval_evidence_are_rejected():
    revoked = set()
    fixture = Fixture(operator_revoked=revoked)
    assertion = fixture.trust.verify_operator(
        fixture.context,
        fixture.authorization,
        "EXECUTION",
        NOW,
    )
    revoked.add("operator-jti")
    with pytest.raises(OwnerDenied, match="revoked"):
        fixture.trust.authorize(
            fixture.authorization, assertion, "EXECUTION", NOW, fixture.context, object()
        )

    expired = NOW + timedelta(minutes=4)
    with pytest.raises(OwnerDenied, match="not currently valid"):
        fixture.trust.verify_operator(fixture.context, fixture.authorization, "EXECUTION", expired)

    fixture2 = Fixture()
    fixture2.policy_store.revoke_approval("approval-p1")
    with pytest.raises(OwnerDenied, match="revoked"):
        fixture2.trust.verify_operator(
            fixture2.context,
            fixture2.authorization,
            "EXECUTION",
            NOW,
        )

    fixture3 = Fixture()
    policy = fixture3.policy_store.policy(AUTH_ID, "p1")
    approval_claims = dict(fixture3.policy_store.approvals(AUTH_ID, "p1")[0].claims)
    approval_claims["exp"] = iso(NOW + timedelta(minutes=1))
    approval = sign_claims("approver-key", approval_claims, fixture3.approver_key)
    fixture3.policy_store = VersionedSyntheticD10Authority()
    fixture3.policy_store.publish(AUTH_ID, "p1", policy, (approval,))
    fixture3.trust = fixture3.make_trust()
    with pytest.raises(OwnerDenied, match="not currently valid"):
        fixture3.trust.verify_operator(
            fixture3.context,
            fixture3.authorization,
            "EXECUTION",
            NOW + timedelta(minutes=1),
        )


def test_stale_policy_and_revoked_owner_authorization_fail_closed():
    fixture = Fixture()
    fixture._publish_policy("p2", current=False)
    fixture.policy_store.select_current(AUTH_ID, "p2")
    with pytest.raises(OwnerDenied, match="stale"):
        fixture.trust.verify_operator(
            fixture.context,
            fixture.authorization,
            "EXECUTION",
            NOW,
        )

    fixture2 = Fixture()
    assertion = fixture2.trust.verify_operator(
        fixture2.context,
        fixture2.authorization,
        "EXECUTION",
        NOW,
    )
    fixture2.policy_store.revoke_authorization(AUTH_ID)
    with pytest.raises(OwnerDenied, match="revoked"):
        fixture2.trust.authorize(
            fixture2.authorization, assertion, "EXECUTION", NOW, fixture2.context, object()
        )

    fixture3 = Fixture()
    assertion = fixture3.trust.verify_operator(
        fixture3.context,
        fixture3.authorization,
        "EXECUTION",
        NOW,
    )
    fixture3._publish_policy("p2", current=True)
    with pytest.raises(OwnerDenied, match="stale D10 policy version"):
        fixture3.trust.authorize(
            fixture3.authorization, assertion, "EXECUTION", NOW, fixture3.context, object()
        )


def test_policy_threshold_is_enforced_not_defaulted_to_allow():
    fixture = Fixture()
    policy = fixture.policy_store.policy(AUTH_ID, "p1")
    policy_claims = dict(policy.claims)
    policy_claims["jti"] = "policy-requires-two-approvers"
    policy_claims["approval_threshold"] = 2
    policy = sign_claims("policy-key", policy_claims, fixture.policy_key)
    approvals = fixture.policy_store.approvals(AUTH_ID, "p1")
    fixture.policy_store = VersionedSyntheticD10Authority()
    fixture.policy_store.publish(AUTH_ID, "p1", policy, approvals)
    fixture.trust = fixture.make_trust()
    with pytest.raises(OwnerDenied, match="threshold is not met"):
        fixture.trust.verify_operator(
            fixture.context,
            fixture.authorization,
            "EXECUTION",
            NOW,
        )


def test_requester_and_approver_must_be_distinct_natural_person_uids():
    fixture = Fixture()
    policy = fixture.policy_store.policy(AUTH_ID, "p1")
    claims = dict(policy.claims)
    claims["jti"] = "policy-with-self-approval"
    approval_claims = dict(fixture.policy_store.approvals(AUTH_ID, "p1")[0].claims)
    approval_claims["approver_uid"] = REQUESTER_UID
    approval = sign_claims(
        "requester-approval-key",
        approval_claims,
        fixture.requester_approval_key,
    )
    updated = sign_claims("policy-key", claims, fixture.policy_key)
    fixture.policy_store = VersionedSyntheticD10Authority()
    fixture.policy_store.publish(AUTH_ID, "p1", updated, (approval,))
    fixture.trust = fixture.make_trust()
    with pytest.raises(OwnerDenied, match="distinct"):
        fixture.trust.verify_operator(
            fixture.context,
            fixture.authorization,
            "EXECUTION",
            NOW,
        )


def test_fencing_token_is_signature_scope_and_current_generation_checked():
    fixture = Fixture(fence_generation=8)
    assertion = fixture.trust.verify_operator(
        fixture.context,
        fixture.authorization,
        "EXECUTION",
        NOW,
    )
    transaction = object()
    fixture.trust.authorize(
        fixture.authorization,
        assertion,
        "EXECUTION",
        NOW,
        fixture.context,
        transaction,
    )
    with pytest.raises(OwnerDenied, match="stale or invalid"):
        fixture.trust.verify_execution(
            fixture.authorization,
            assertion,
            fixture.request,
            "admitted",
            NOW,
            fixture.context,
            transaction,
        )
    assert fixture.generation_store.calls == 1


def test_revoked_fencing_token_is_rejected_inside_the_owner_transaction():
    fixture = Fixture()
    fixture.generation_store.revoked.add("fence-jti")
    scope = {
        "authorization_id": AUTH_ID,
        "operation_id": OPERATION_ID,
        "tenant_id": TENANT_A,
        "organization_id": TENANT_A,
        "action": ACTION,
        "target_resource": RESOURCE,
    }
    with pytest.raises(OwnerDenied, match="fencing token has been revoked"):
        fixture.fencing.verify_in_transaction(
            object(), fixture.context.fencing_evidence, scope, NOW
        )


def test_forged_fencing_signature_is_rejected_before_generation_lookup():
    fixture = Fixture()
    forged_fence = replace(
        fixture.context.fencing_evidence,
        signature=b"x" * len(fixture.context.fencing_evidence.signature),
    )
    context = replace(fixture.context, fencing_evidence=forged_fence)
    assertion = fixture.trust.verify_operator(
        context,
        fixture.authorization,
        "EXECUTION",
        NOW,
    )
    with pytest.raises(OwnerDenied, match="signature"):
        fixture.trust.verify_execution(
            fixture.authorization,
            assertion,
            fixture.request,
            "admitted",
            NOW,
            context,
            object(),
        )
    assert fixture.generation_store.calls == 0


def test_receipt_projection_is_current_policy_and_tenant_scoped():
    fixture = Fixture()
    receipt = OwnerReceipt(
        AUTH_ID,
        OPERATION_ID,
        "event-1",
        "e" * 64,
        "assertion-1",
        "operator-person",
        "nexora_authenticated",
        "idempotency-1",
        fixture.request.canonical_bytes,
        fixture.request.request_digest,
        NOW,
        {"event_id": "event-1"},
        TENANT_A,
        TENANT_A,
    )
    projection = TenantScopedReceiptProjection(
        application_sessions=fixture.application_sessions,
        policy_authority=fixture.policy_store,
        policy_verifier=fixture.policy_verifier,
    )
    assert (
        projection.project(
            fixture.make_session(),
            AUTH_ID,
            OPERATION_ID,
            "p1",
            receipt,
            NOW,
        )["event_id"]
        == "event-1"
    )
    with pytest.raises(OwnerDenied, match="tenant scope"):
        projection.project(
            fixture.make_session(tenant=TENANT_B),
            AUTH_ID,
            OPERATION_ID,
            "p1",
            receipt,
            NOW,
        )


def test_coordinator_executes_and_stages_once_inside_transaction():
    fixture = Fixture()
    tx = Transaction(fixture.authorization)
    coordinator = OwnerAuthorizationCoordinator(fixture.trust)
    receipt = coordinator.execute(tx, OPERATION_ID, fixture.context, fixture.request)
    assert isinstance(receipt, DurableReceipt)
    assert tx.effects == 1
    assert tx.snapshot.receipt.tenant_id == TENANT_A
    with pytest.raises(OwnerDenied, match="consumed"):
        coordinator.execute(tx, OPERATION_ID, fixture.context, fixture.request)
    assert tx.effects == 1
    assert tx.calls.count("execute_and_stage_atomically") == 1


def test_missing_trust_or_fencing_dependencies_are_controlled_unavailability():
    with pytest.raises(OwnerDependencyUnavailable, match="all G08 trust"):
        SignedG08OwnerTrust(
            application_sessions=None,
            operator_evidence=None,
            policy_authority=None,
            policy_verifier=None,
            approval_verifier=None,
            fencing_verifier=None,
            technical_verifier=None,
        )
    fixture = Fixture()
    assertion = fixture.trust.verify_operator(
        fixture.context,
        fixture.authorization,
        "EXECUTION",
        NOW,
    )
    context_without_fence = replace(fixture.context, fencing_evidence=None)
    with pytest.raises(OwnerDependencyUnavailable, match="fencing"):
        fixture.trust.verify_execution(
            fixture.authorization,
            assertion,
            fixture.request,
            "admitted",
            NOW,
            context_without_fence,
            object(),
        )

    empty_authority = VersionedSyntheticD10Authority()
    unavailable = SignedG08OwnerTrust(
        application_sessions=fixture.application_sessions,
        operator_evidence=fixture.operator_evidence,
        policy_authority=empty_authority,
        policy_verifier=fixture.policy_verifier,
        approval_verifier=fixture.approval_verifier,
        fencing_verifier=fixture.fencing,
        technical_verifier=fixture.technical,
    )
    with pytest.raises(OwnerDependencyUnavailable, match="current D10 policy"):
        unavailable.verify_operator(fixture.context, fixture.authorization, "EXECUTION", NOW)
