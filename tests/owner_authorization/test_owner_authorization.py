"""Actual coordinator tests over synthetic in-memory transaction/assurance ports.

No database, identity provider or real policy authority is simulated as qualified.
Thread tests cover coordinator ordering against the fake lock, NOT PostgreSQL.
"""

from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import hashlib
import json
import threading

import pytest

from services.g08_owner_authorization import (
    Authorization,
    ExecutionEvidence,
    ExecutionRequest,
    OperatorAssertion,
    OwnerAuthorizationCoordinator,
    OwnerDenied,
    OwnerDependencyUnavailable,
    OwnerHistoryInvalid,
    OwnerReceipt,
    OwnerSnapshot,
    StatusEntry,
    validate_history,
)
from services.g08_transaction_boundary import CommitOutcomeUnknown, DurableReceipt

NOW = datetime(2026, 11, 7, 12, tzinfo=timezone.utc)
AUTH = Authorization(
    "authorization",
    "operation",
    "operator",
    "authentication",
    "a" * 64,
    NOW - timedelta(hours=1),
    NOW + timedelta(hours=1),
)
ADMITTED = StatusEntry("admitted", 1, None, None, "ADMITTED", NOW - timedelta(minutes=1))


def request(key="same"):
    # Synthetic bytes only. No assertion that this fixture is the approved D08 serializer.
    data = json.dumps({"operation": AUTH.operation_id, "key": key}).encode()
    return ExecutionRequest(key, data, hashlib.sha256(data).hexdigest())


class SyntheticTrust:
    """TEST ONLY; deliberately not exported by production modules."""

    def __init__(self, identity_changes=None, proof_changes=None, deny=False, missing_proof=False):
        self.identity_changes = identity_changes or {}
        self.proof_changes = proof_changes or {}
        self.deny = deny
        self.missing_proof = missing_proof
        self.calls = []

    def verify_operator(self, context, a, purpose, decision_time):
        self.calls.append(("identity", purpose))
        identity = OperatorAssertion(
            "assertion-" + purpose,
            a.authorization_id,
            a.operation_id,
            purpose,
            a.operator_person_ref,
            a.authentication_evidence_ref,
            a.authentication_evidence_sha256,
            "fixture-session-binding",
            "fixture-session",
            None,
            "fixture-verifier",
            decision_time - timedelta(seconds=1),
            decision_time + timedelta(minutes=1),
        )
        return replace(identity, **self.identity_changes)

    def authorize(self, a, identity, purpose, decision_time, context, transaction):
        self.calls.append(("authority", purpose))
        if self.deny:
            raise OwnerDenied("synthetic policy denial")

    def verify_execution(
        self, a, identity, req, admitted_status_id, decision_time, context, transaction
    ):
        self.calls.append(("evidence", "EXECUTION"))
        if self.missing_proof:
            return None
        proof = ExecutionEvidence(
            "proof",
            a.authorization_id,
            a.operation_id,
            admitted_status_id,
            identity.assertion_id,
            "event",
            decision_time,
            req.request_digest,
            {"event_id": "event"},
            "fixture-technical",
            "b" * 64,
            "fixture-control-verifier",
            "fixture-authority",
            "fixture-fence",
        )
        return replace(proof, **self.proof_changes)


class SharedFixture:
    def __init__(self, initial=None):
        self.lock = threading.Lock()
        self.state = {} if initial is None else {AUTH.operation_id: initial}
        self.audit = []


class MemoryTransaction:
    session_user = "fixture-session"

    def __init__(self, shared, now=NOW, commit_outcome="ack"):
        self.shared = shared
        self.now = now
        self.commit_outcome = commit_outcome
        self.calls = []
        self.held = False
        self.pending = None
        self.audit = []

    def begin_read_committed(self):
        self.calls.append("begin_read_committed")

    def acquire_global_lock(self):
        self.calls.append("lock")
        self.shared.lock.acquire(timeout=5) or pytest.fail("fake transaction lock timeout")
        self.held = True
        # Fresh snapshot is taken after waiting, never in begin_read_committed.
        self.pending = deepcopy(self.shared.state)

    def load(self, operation_id):
        assert self.held
        self.calls.append("fresh_load")
        return self.pending.get(operation_id)

    def read_receipt(self, authorization_id, operation_id, operator):
        assert self.held
        snapshot = self.pending.get(operation_id)
        if snapshot is None or snapshot.authorization.authorization_id != authorization_id:
            return None
        self.calls.append("read_receipt")
        return snapshot.receipt

    def decision_time(self):
        assert self.calls[-1] == "fresh_load"
        self.calls.append("clock")
        return self.now

    def stage_admission(self, a, entry, operator):
        self.calls.append("stage_admission")
        assert a.operation_id not in self.pending
        self.pending[a.operation_id] = OwnerSnapshot(a, (entry,), None)
        self.audit.append((entry.status, operator.assertion_id))
        return entry.status_id

    def stage_status(self, a, entry, operator):
        self.calls.append("stage_status")
        prior = self.pending[a.operation_id]
        self.pending[a.operation_id] = replace(prior, history=(*prior.history, entry))
        self.audit.append((entry.status, operator.assertion_id))
        return entry.status_id

    def stage_execution(self, a, req, identity, proof):
        self.calls.append("stage_execution")
        prior = self.pending[a.operation_id]
        assert prior.receipt is None
        receipt = OwnerReceipt(
            a.authorization_id,
            a.operation_id,
            proof.event_id,
            proof.evidence_id,
            identity.assertion_id,
            identity.person_ref,
            identity.db_session_user,
            req.idempotency_key,
            req.canonical_bytes,
            req.request_digest,
            proof.decision_time,
            proof.result,
        )
        self.pending[a.operation_id] = replace(prior, receipt=receipt)
        self.audit.append(("CONSUMED", identity.assertion_id))
        return receipt

    def _release(self):
        if self.held:
            self.shared.lock.release()
            self.held = False

    def commit(self):
        self.calls.append("commit")
        if self.commit_outcome != "lost_before_commit":
            self.shared.state = deepcopy(self.pending)
            self.shared.audit.extend(self.audit)
        self._release()
        if self.commit_outcome != "ack":
            raise TimeoutError("synthetic lost acknowledgement")

    def rollback(self):
        self.calls.append("rollback")
        self._release()


def fixture(history=(ADMITTED,), now=NOW, trust=None):
    shared = SharedFixture(OwnerSnapshot(AUTH, history, None))
    return (
        shared,
        MemoryTransaction(shared, now),
        OwnerAuthorizationCoordinator(trust or SyntheticTrust()),
    )


@pytest.mark.parametrize("status", ["REVOKED", "INVALIDATED"])
def test_admit_then_terminal_audit_and_no_reactivation(status):
    shared = SharedFixture()
    coordinator = OwnerAuthorizationCoordinator(SyntheticTrust())
    assert coordinator.admit(MemoryTransaction(shared), AUTH, {}, "admitted").value == "admitted"
    coordinator.transition(
        MemoryTransaction(shared, NOW + timedelta(seconds=1)),
        AUTH.operation_id,
        {},
        status,
        "admitted",
        "terminal",
    )
    assert [item[0] for item in shared.audit] == ["ADMITTED", status]
    with pytest.raises(OwnerHistoryInvalid):
        coordinator.transition(
            MemoryTransaction(shared, NOW + timedelta(seconds=2)),
            AUTH.operation_id,
            {},
            "REVOKED",
            "terminal",
            "again",
        )
    assert len(shared.state[AUTH.operation_id].history) == 2


def test_duplicate_admission_does_not_replace_immutable_intent():
    shared, tx, coordinator = fixture()
    with pytest.raises(OwnerDenied):
        coordinator.admit(tx, replace(AUTH, operator_person_ref="other"), {}, "new")
    assert shared.state[AUTH.operation_id].authorization == AUTH


@pytest.mark.parametrize(
    "history",
    [
        (),
        (replace(ADMITTED, status="REVOKED"),),
        (replace(ADMITTED, predecessor_status_id="ghost"),),
        (replace(ADMITTED, revision=2),),
        (ADMITTED, StatusEntry("second", 3, "admitted", 1, "REVOKED", NOW)),
        (ADMITTED, StatusEntry("second", 2, "wrong", 1, "REVOKED", NOW)),
        (ADMITTED, StatusEntry("second", 2, "admitted", 9, "REVOKED", NOW)),
        (ADMITTED, StatusEntry("second", 2, "admitted", 1, "ADMITTED", NOW)),
        (ADMITTED, StatusEntry("admitted", 2, "admitted", 1, "REVOKED", NOW)),
        (ADMITTED, StatusEntry("second", 2, "admitted", 1, "REVOKED", NOW - timedelta(days=1))),
        (replace(ADMITTED, occurred_at=NOW.replace(tzinfo=None)),),
    ],
)
def test_invalid_lifecycle_history_rejected(history):
    with pytest.raises(OwnerHistoryInvalid):
        validate_history(history)


def test_stale_transition_predecessor_denied():
    shared, tx, coordinator = fixture()
    with pytest.raises(OwnerDenied):
        coordinator.transition(tx, AUTH.operation_id, {}, "REVOKED", "old", "terminal")
    assert shared.audit == []


@pytest.mark.parametrize("status", ["REVOKED", "INVALIDATED"])
def test_terminal_authority_cannot_execute(status):
    history = (ADMITTED, StatusEntry("terminal", 2, "admitted", 1, status, NOW))
    shared, tx, coordinator = fixture(history)
    with pytest.raises(OwnerDenied):
        coordinator.execute(tx, AUTH.operation_id, {}, request())
    assert shared.audit == []


@pytest.mark.parametrize("now", [AUTH.valid_to, AUTH.valid_from - timedelta(seconds=1)])
def test_authorization_interval_is_half_open(now):
    _, tx, coordinator = fixture(now=now)
    with pytest.raises(OwnerDenied):
        coordinator.execute(tx, AUTH.operation_id, {}, request())


@pytest.mark.parametrize(
    "changes",
    [
        {"person_ref": "approver-is-not-executor"},
        {"authorization_id": "other"},
        {"operation_id": "other"},
        {"purpose": "ADMISSION"},
        {"db_session_user": "shared-wrong-session"},
        {"session_binding_ref": ""},
        {"verifier_ref": ""},
        {"authentication_evidence_ref": "different"},
        {"authentication_evidence_sha256": "b" * 64},
        {"valid_until": NOW},
        {"verified_at": NOW + timedelta(seconds=1)},
    ],
)
def test_operator_mismatch_never_stages_execution(changes):
    shared, tx, coordinator = fixture(trust=SyntheticTrust(identity_changes=changes))
    with pytest.raises(OwnerDenied):
        coordinator.execute(
            tx, AUTH.operation_id, {"trusted": True, "actor": "operator"}, request()
        )
    assert "stage_execution" not in tx.calls and not shared.audit


@pytest.mark.parametrize("action", ["admit", "transition", "execute", "reconcile"])
def test_unconfigured_identity_assurance_fails_closed_for_every_interface(action):
    shared, tx, _ = fixture()
    coordinator = OwnerAuthorizationCoordinator()
    if action == "admit":
        tx = MemoryTransaction(SharedFixture())
        call = lambda: coordinator.admit(tx, AUTH, {"verified": True}, "admitted")
    elif action == "transition":
        call = lambda: coordinator.transition(
            tx, AUTH.operation_id, {}, "REVOKED", "admitted", "terminal"
        )
    else:
        call = lambda: getattr(coordinator, action)(
            tx, AUTH.operation_id, {"verified": True}, request()
        )
    with pytest.raises(OwnerDependencyUnavailable):
        call()
    assert not any(name.startswith("stage_") for name in tx.calls)
    assert tx.calls[-1] == "rollback"


def test_identity_authentication_does_not_supply_owner_permission():
    _, tx, coordinator = fixture(trust=SyntheticTrust(deny=True))
    with pytest.raises(OwnerDenied):
        coordinator.execute(tx, AUTH.operation_id, {}, request())
    assert "stage_execution" not in tx.calls


@pytest.mark.parametrize(
    "changes",
    [
        {"authorization_id": "other"},
        {"operation_id": "other"},
        {"admitted_status_id": "stale"},
        {"assertion_id": "other"},
        {"decision_time": NOW - timedelta(seconds=1)},
        {"request_digest": "d" * 64},
        {"technical_evidence_ref": ""},
        {"technical_evidence_sha256": "invalid"},
        {"technical_verifier_ref": ""},
        {"authority_evidence_ref": ""},
        {"fencing_evidence_ref": ""},
        {"result": {}},
    ],
)
def test_missing_or_inconsistent_execution_evidence_rolls_back(changes):
    shared, tx, coordinator = fixture(trust=SyntheticTrust(proof_changes=changes))
    with pytest.raises(OwnerDenied):
        coordinator.execute(tx, AUTH.operation_id, {}, request())
    assert shared.state[AUTH.operation_id].receipt is None


def test_identity_and_approval_cannot_replace_technical_evidence():
    _, tx, coordinator = fixture(trust=SyntheticTrust(missing_proof=True))
    with pytest.raises(OwnerDependencyUnavailable):
        coordinator.execute(tx, AUTH.operation_id, {}, request())
    assert "stage_execution" not in tx.calls


def test_fresh_state_and_clock_after_lock_then_commit_ack():
    shared, tx, coordinator = fixture()
    result = coordinator.execute(tx, AUTH.operation_id, {}, request())
    assert isinstance(result, DurableReceipt)
    assert tx.calls == [
        "begin_read_committed",
        "lock",
        "fresh_load",
        "clock",
        "stage_execution",
        "commit",
    ]
    assert shared.audit == [("CONSUMED", "assertion-EXECUTION")]


@pytest.mark.parametrize("key", ["same", "fresh-key"])
def test_consumed_operation_rejects_replay_even_under_fresh_key(key):
    shared, tx, coordinator = fixture()
    coordinator.execute(tx, AUTH.operation_id, {}, request())
    with pytest.raises(OwnerDenied):
        coordinator.execute(MemoryTransaction(shared), AUTH.operation_id, {}, request(key))
    assert len(shared.audit) == 1


@pytest.mark.parametrize("outcome", ["lost_before_commit", "lost_after_commit"])
def test_unknown_commit_never_claims_durable_completion(outcome):
    shared, _, coordinator = fixture()
    tx = MemoryTransaction(shared, commit_outcome=outcome)
    with pytest.raises(CommitOutcomeUnknown):
        coordinator.execute(tx, AUTH.operation_id, {}, request())
    assert tx.calls.count("stage_execution") == 1 and "rollback" not in tx.calls
    if outcome == "lost_after_commit":
        original = coordinator.reconcile(
            MemoryTransaction(shared), AUTH.operation_id, {}, request()
        )
        assert original.value == shared.state[AUTH.operation_id].receipt
    else:
        with pytest.raises(CommitOutcomeUnknown):
            coordinator.reconcile(MemoryTransaction(shared), AUTH.operation_id, {}, request())


def test_receipt_reconciliation_needs_current_read_permission_after_revocation():
    shared, tx, coordinator = fixture()
    original = coordinator.execute(tx, AUTH.operation_id, {}, request())
    coordinator.transition(
        MemoryTransaction(shared, NOW + timedelta(seconds=1)),
        AUTH.operation_id,
        {},
        "REVOKED",
        "admitted",
        "terminal",
    )
    assert (
        coordinator.reconcile(
            MemoryTransaction(shared, NOW + timedelta(seconds=2)), AUTH.operation_id, {}, request()
        )
        == original
    )
    with pytest.raises(OwnerDependencyUnavailable):
        OwnerAuthorizationCoordinator().reconcile(
            MemoryTransaction(shared, NOW + timedelta(seconds=2)), AUTH.operation_id, {}, request()
        )
    with pytest.raises(OwnerDenied):
        OwnerAuthorizationCoordinator(SyntheticTrust(deny=True)).reconcile(
            MemoryTransaction(shared, NOW + timedelta(seconds=2)), AUTH.operation_id, {}, request()
        )


def test_conflicting_reconciliation_does_not_consume_again():
    shared, tx, coordinator = fixture()
    coordinator.execute(tx, AUTH.operation_id, {}, request())
    with pytest.raises(CommitOutcomeUnknown):
        coordinator.reconcile(MemoryTransaction(shared), AUTH.operation_id, {}, request("changed"))
    assert len(shared.audit) == 1


@pytest.mark.parametrize("flag", [True, False, {"authorized": True}])
def test_boolean_or_caller_json_trust_flags_are_not_authority(flag):
    class BadAuthorityAdapter(SyntheticTrust):
        def authorize(self, *args):
            return flag

    _, tx, coordinator = fixture(trust=BadAuthorityAdapter())
    with pytest.raises(OwnerDependencyUnavailable):
        coordinator.execute(tx, AUTH.operation_id, {}, request())
    assert "stage_execution" not in tx.calls


def test_two_competing_operations_observe_one_consumption_in_fake_transaction_model():
    shared, _, coordinator = fixture()
    barrier = threading.Barrier(2)
    results = []

    def run(key):
        barrier.wait(timeout=5)
        try:
            results.append(
                coordinator.execute(MemoryTransaction(shared), AUTH.operation_id, {}, request(key))
            )
        except OwnerDenied:
            results.append("denied")

    workers = [threading.Thread(target=run, args=(key,)) for key in ["one", "two"]]
    for worker in workers:
        worker.start()
    for worker in workers:
        worker.join(timeout=10)
        assert not worker.is_alive()
    assert sum(isinstance(r, DurableReceipt) for r in results) == 1
    assert results.count("denied") == 1
    assert len(shared.audit) == 1


@pytest.mark.parametrize("status", ["REVOKED", "INVALIDATED"])
def test_unknown_status_commit_reconciles_original_id_without_new_transition(status):
    shared, _, coordinator = fixture()
    with pytest.raises(CommitOutcomeUnknown):
        coordinator.transition(
            MemoryTransaction(shared, commit_outcome="lost_after_commit"),
            AUTH.operation_id,
            {},
            status,
            "admitted",
            "original-terminal",
        )
    original = coordinator.reconcile_status(
        MemoryTransaction(shared), AUTH.operation_id, {}, "original-terminal", status, "admitted"
    )
    assert original.value.status_id == "original-terminal"
    assert len(shared.state[AUTH.operation_id].history) == 2
    for status_id, expected_status, predecessor in [
        ("fresh-id", status, "admitted"),
        ("original-terminal", "ADMITTED", "admitted"),
        ("original-terminal", status, "wrong"),
    ]:
        with pytest.raises(CommitOutcomeUnknown):
            coordinator.reconcile_status(
                MemoryTransaction(shared),
                AUTH.operation_id,
                {},
                status_id,
                expected_status,
                predecessor,
            )
    assert len(shared.audit) == 1


def test_unknown_admission_commit_reconciles_original_admission():
    shared = SharedFixture()
    coordinator = OwnerAuthorizationCoordinator(SyntheticTrust())
    with pytest.raises(CommitOutcomeUnknown):
        coordinator.admit(
            MemoryTransaction(shared, commit_outcome="lost_after_commit"),
            AUTH,
            {},
            "original-admission",
        )
    assert (
        coordinator.reconcile_status(
            MemoryTransaction(shared), AUTH.operation_id, {}, "original-admission", "ADMITTED", None
        ).value.status
        == "ADMITTED"
    )
    with pytest.raises(OwnerDependencyUnavailable):
        OwnerAuthorizationCoordinator().reconcile_status(
            MemoryTransaction(shared), AUTH.operation_id, {}, "original-admission", "ADMITTED", None
        )


def test_inconsistent_persistence_result_rolls_back_all_staged_changes():
    class InconsistentWriter(MemoryTransaction):
        def stage_execution(self, *args):
            receipt = super().stage_execution(*args)
            return replace(receipt, evidence_id="other-proof")

    shared, _, coordinator = fixture()
    tx = InconsistentWriter(shared)
    with pytest.raises(OwnerHistoryInvalid):
        coordinator.execute(tx, AUTH.operation_id, {}, request())
    assert shared.state[AUTH.operation_id].receipt is None and not shared.audit
    assert tx.calls[-1] == "rollback"


def test_lost_admission_without_commit_keeps_missing_status_quarantined():
    shared = SharedFixture()
    coordinator = OwnerAuthorizationCoordinator(SyntheticTrust())
    with pytest.raises(CommitOutcomeUnknown):
        coordinator.admit(
            MemoryTransaction(shared, commit_outcome="lost_before_commit"), AUTH, {}, "original-id"
        )
    tx = MemoryTransaction(shared)
    with pytest.raises(CommitOutcomeUnknown):
        coordinator.reconcile_status(tx, AUTH.operation_id, {}, "original-id", "ADMITTED", None)
    assert not shared.state and not shared.audit
    assert "stage_admission" not in tx.calls
