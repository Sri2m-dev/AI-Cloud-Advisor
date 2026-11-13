"""Owner lifecycle and transaction coordination; no database or identity SDK.

All persistence/assurance ports are unconfigured by default. Dataclasses describe
verified evidence returned by a future approved provider; constructing one is NOT
authentication. No route accepts these records or caller-supplied trust flags.
"""

import hashlib
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol

from services.g08_transaction_boundary import CommitOutcomeUnknown, DurableReceipt, execute_once


class OwnerDenied(RuntimeError):
    pass


class OwnerDependencyUnavailable(OwnerDenied):
    pass


class OwnerHistoryInvalid(OwnerDenied):
    pass


@dataclass(frozen=True)
class Authorization:
    authorization_id: str
    operation_id: str
    operator_person_ref: str
    authentication_evidence_ref: str
    authentication_evidence_sha256: str
    valid_from: datetime
    valid_to: datetime
    tenant_id: str | None = None
    organization_id: str | None = None
    action: str | None = None
    target_resource: str | None = None
    policy_version: str | None = None
    requester_auth_uid: str | None = None
    administrator_id: str | None = None
    expected_revision: int | None = None
    mutation: dict[str, Any] | None = None
    scope_key: str | None = None
    authorization_sha256: str | None = None
    approval_manifest_sha256: str | None = None
    intent_sha256: str | None = None
    evidence_ref: str | None = None
    requester_person_ref: str | None = None


@dataclass(frozen=True)
class StatusEntry:
    status_id: str
    revision: int
    predecessor_status_id: str | None
    predecessor_revision: int | None
    status: str
    occurred_at: datetime


@dataclass(frozen=True)
class OperatorAssertion:
    assertion_id: str
    authorization_id: str
    operation_id: str
    purpose: str
    person_ref: str
    authentication_evidence_ref: str
    authentication_evidence_sha256: str
    session_binding_ref: str
    db_session_user: str
    verified_auth_uid: str | None
    verifier_ref: str
    verified_at: datetime
    valid_until: datetime
    tenant_id: str | None = None
    organization_id: str | None = None
    action: str | None = None
    target_resource: str | None = None
    policy_version: str | None = None
    requester_auth_uid: str | None = None
    approval_ids: tuple[str, ...] = ()
    d10_evidence_ref: str | None = None
    evidence_jti: str | None = None
    approval_manifest: tuple[dict[str, Any], ...] = ()


@dataclass(frozen=True)
class ExecutionRequest:
    idempotency_key: str
    canonical_bytes: bytes
    request_digest: str


@dataclass(frozen=True)
class ExecutionEvidence:
    evidence_id: str
    authorization_id: str
    operation_id: str
    admitted_status_id: str
    assertion_id: str
    event_id: str
    decision_time: datetime
    request_digest: str
    result: dict[str, Any]
    technical_evidence_ref: str
    technical_evidence_sha256: str
    technical_verifier_ref: str
    authority_evidence_ref: str
    fencing_evidence_ref: str
    tenant_id: str | None = None
    organization_id: str | None = None
    action: str | None = None
    target_resource: str | None = None
    policy_version: str | None = None
    fence_generation: int | None = None


@dataclass(frozen=True)
class OwnerReceipt:
    authorization_id: str
    operation_id: str
    event_id: str
    evidence_id: str
    assertion_id: str
    person_ref: str
    db_session_user: str
    idempotency_key: str
    canonical_bytes: bytes
    request_digest: str
    decision_time: datetime
    result: dict[str, Any]
    tenant_id: str | None = None
    organization_id: str | None = None


@dataclass(frozen=True)
class OwnerSnapshot:
    authorization: Authorization
    history: tuple[StatusEntry, ...]
    receipt: OwnerReceipt | None
    consumed: bool = False


class OwnerTrust(Protocol):
    """Verify existing authenticated evidence; never perform remote mutations.

    authorize must raise on denial and return None on verified permission. It must
    not equate identity verification or human approval with a technical-control PASS.
    """

    def verify_operator(
        self, context: Any, authorization: Authorization, purpose: str, decision_time: datetime
    ) -> OperatorAssertion: ...
    def authorize(
        self,
        authorization: Authorization,
        operator: OperatorAssertion,
        purpose: str,
        decision_time: datetime,
        context: Any,
        transaction: "OwnerUnitOfWork",
    ) -> None: ...
    def verify_execution(
        self,
        authorization: Authorization,
        operator: OperatorAssertion,
        request: ExecutionRequest,
        admitted_status_id: str,
        decision_time: datetime,
        context: Any,
        transaction: "OwnerUnitOfWork",
    ) -> ExecutionEvidence: ...


class UnavailableOwnerTrust:
    def verify_operator(self, *args, **kwargs):
        raise OwnerDependencyUnavailable(
            "independently authenticated, session-bound operator verifier unavailable"
        )

    def authorize(self, *args, **kwargs):
        raise OwnerDependencyUnavailable(
            "owner admission/current policy/D10 authority verifier unavailable"
        )

    def verify_execution(self, *args, **kwargs):
        raise OwnerDependencyUnavailable(
            "D08, technical evidence and cross-system fencing verifier unavailable"
        )


class OwnerUnitOfWork(Protocol):
    """One real database transaction; no detached store or external side-effect writer.

    Adapter must apply SQL checks and narrow privileges, use one global lock,
    capture DB time, invoke the canonical operation, and stage its event,
    version, receipt, proof, and consumption atomically. Tenant scope must be
    checked against the signed D10 binding in the same transaction.
    There is deliberately no concrete network/database adapter in M2-B.
    """

    session_user: str

    def begin_read_committed(self) -> None: ...
    def acquire_global_lock(self) -> None: ...
    def load(self, operation_id: str) -> OwnerSnapshot | None: ...
    def decision_time(self) -> datetime: ...
    def stage_admission(
        self, authorization: Authorization, entry: StatusEntry, operator: OperatorAssertion
    ) -> str: ...
    def stage_status(
        self, authorization: Authorization, entry: StatusEntry, operator: OperatorAssertion
    ) -> str: ...
    def stage_execution(
        self,
        authorization: Authorization,
        request: ExecutionRequest,
        operator: OperatorAssertion,
        evidence: ExecutionEvidence,
    ) -> OwnerReceipt: ...
    def read_receipt(
        self, authorization_id: str, operation_id: str, operator: OperatorAssertion
    ) -> OwnerReceipt | None: ...
    def commit(self) -> None: ...
    def rollback(self) -> None: ...


def _time(value: datetime) -> None:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise OwnerHistoryInvalid("timezone-aware protected database time required")


def _refs(*values: str) -> None:
    if any(
        not isinstance(v, str) or not v.strip() or len(v.encode("utf-8")) > 2048 for v in values
    ):
        raise OwnerHistoryInvalid("missing or invalid evidence binding")


def validate_history(history: tuple[StatusEntry, ...]) -> None:
    if not history:
        raise OwnerHistoryInvalid("admission history missing")
    ids = set()
    previous = None
    for revision, entry in enumerate(history, 1):
        _refs(entry.status_id)
        _time(entry.occurred_at)
        if entry.status_id in ids or type(entry.revision) is not int or entry.revision != revision:
            raise OwnerHistoryInvalid("duplicate status or revision gap")
        ids.add(entry.status_id)
        if previous is None:
            if (
                entry.status != "ADMITTED"
                or entry.predecessor_status_id is not None
                or entry.predecessor_revision is not None
            ):
                raise OwnerHistoryInvalid("invalid initial admission")
        elif (
            previous.status != "ADMITTED"
            or entry.status not in {"REVOKED", "INVALIDATED"}
            or entry.predecessor_status_id != previous.status_id
            or type(entry.predecessor_revision) is not int
            or entry.predecessor_revision != previous.revision
            or entry.occurred_at < previous.occurred_at
        ):
            raise OwnerHistoryInvalid("terminal transition or predecessor mismatch")
        previous = entry


def _authorization(authorization: Authorization) -> None:
    _refs(
        authorization.authorization_id,
        authorization.operation_id,
        authorization.operator_person_ref,
        authorization.authentication_evidence_ref,
    )
    _time(authorization.valid_from)
    _time(authorization.valid_to)
    if authorization.valid_to <= authorization.valid_from or not re.fullmatch(
        r"[0-9a-f]{64}", authorization.authentication_evidence_sha256
    ):
        raise OwnerHistoryInvalid("invalid authorization validity or authentication digest")


def _request(request: ExecutionRequest) -> None:
    if (
        not re.fullmatch(r"[A-Za-z0-9._:-]{1,128}", request.idempotency_key)
        or not isinstance(request.canonical_bytes, bytes)
        or not request.canonical_bytes
        or len(request.canonical_bytes) > 131072
        or hashlib.sha256(request.canonical_bytes).hexdigest() != request.request_digest
    ):
        raise OwnerDenied("canonical bytes/key/digest inconsistent; D08 verifier still required")


def _operator(
    identity: OperatorAssertion,
    authorization: Authorization,
    purpose: str,
    decision_time: datetime,
    session_user: str,
) -> None:
    if not isinstance(identity, OperatorAssertion):
        raise OwnerDependencyUnavailable("verifier did not supply an operator assertion")
    _refs(
        identity.assertion_id,
        identity.person_ref,
        identity.authentication_evidence_ref,
        identity.session_binding_ref,
        identity.verifier_ref,
        identity.db_session_user,
    )
    _time(identity.verified_at)
    _time(identity.valid_until)
    if (
        identity.authorization_id != authorization.authorization_id
        or identity.operation_id != authorization.operation_id
        or identity.purpose != purpose
        or identity.db_session_user != session_user
        or not identity.verified_at <= decision_time < identity.valid_until
        or not re.fullmatch(r"[0-9a-f]{64}", identity.authentication_evidence_sha256)
    ):
        raise OwnerDenied("operator assertion operation/session/purpose/validity mismatch")
    if purpose == "EXECUTION" and (
        identity.person_ref != authorization.operator_person_ref
        or identity.authentication_evidence_ref != authorization.authentication_evidence_ref
        or identity.authentication_evidence_sha256 != authorization.authentication_evidence_sha256
    ):
        raise OwnerDenied("executing operator differs from authorized operator")
    scoped = (
        identity.tenant_id,
        identity.organization_id,
        identity.action,
        identity.target_resource,
        identity.policy_version,
        identity.requester_auth_uid,
        identity.d10_evidence_ref,
    )
    if any(value is not None for value in scoped):
        if any(not isinstance(value, str) or not value.strip() for value in scoped):
            raise OwnerDenied("verified D10 tenant, operator, and policy bindings are incomplete")
        _refs(*scoped)
        if not identity.verified_auth_uid or not identity.approval_ids or not identity.evidence_jti:
            raise OwnerDenied(
                "verified operator, D10 approval, and revocation bindings are required"
            )
        for field in (
            "tenant_id",
            "organization_id",
            "action",
            "target_resource",
            "policy_version",
        ):
            expected = getattr(authorization, field, None)
            actual = getattr(identity, field)
            if expected is not None and expected != actual:
                raise OwnerDenied(f"authorization {field} conflicts with verified D10 scope")


class OwnerAuthorizationCoordinator:
    def __init__(self, trust: OwnerTrust | None = None):
        self.trust = trust if trust is not None else UnavailableOwnerTrust()

    def _verify(self, tx, authorization, context, purpose, decision_time):
        identity = self.trust.verify_operator(context, authorization, purpose, decision_time)
        _operator(identity, authorization, purpose, decision_time, tx.session_user)
        if (
            self.trust.authorize(authorization, identity, purpose, decision_time, context, tx)
            is not None
        ):
            raise OwnerDependencyUnavailable(
                "authority verifier must fail by exception; boolean trust flags rejected"
            )
        return identity

    def admit(
        self, tx: OwnerUnitOfWork, authorization: Authorization, context: Any, status_id: str
    ) -> DurableReceipt:
        return execute_once(
            tx,
            lambda: self.admit_in_transaction(tx, authorization, context, status_id),
        )

    def admit_in_transaction(
        self,
        tx: OwnerUnitOfWork,
        authorization: Authorization,
        context: Any,
        status_id: str,
        *,
        history_locked: bool = False,
    ):
        """Admit a new authorization or finish its same-transaction D10 bootstrap."""
        if not history_locked:
            tx.acquire_global_lock()
        snapshot = tx.load(authorization.operation_id)
        if snapshot is not None and (
            snapshot.authorization != authorization
            or snapshot.history
            or snapshot.receipt is not None
            or snapshot.consumed
        ):
            raise OwnerDenied("owner operation already admitted or bootstrap conflicts")
        _authorization(authorization)
        decision_time = tx.decision_time()
        _time(decision_time)
        identity = self._verify(tx, authorization, context, "ADMISSION", decision_time)
        entry = StatusEntry(status_id, 1, None, None, "ADMITTED", decision_time)
        validate_history((entry,))
        return tx.stage_admission(authorization, entry, identity)

    def transition(
        self,
        tx: OwnerUnitOfWork,
        operation_id: str,
        context: Any,
        status: str,
        expected_predecessor: str,
        status_id: str,
    ) -> DurableReceipt:
        def operation():
            tx.acquire_global_lock()
            snapshot = self._load(tx, operation_id)
            previous = snapshot.history[-1]
            if (
                status not in {"REVOKED", "INVALIDATED"}
                or expected_predecessor != previous.status_id
            ):
                raise OwnerDenied("invalid transition or stale predecessor")
            decision_time = tx.decision_time()
            _time(decision_time)
            entry = StatusEntry(
                status_id,
                previous.revision + 1,
                previous.status_id,
                previous.revision,
                status,
                decision_time,
            )
            validate_history((*snapshot.history, entry))
            purpose = "REVOCATION" if status == "REVOKED" else "INVALIDATION"
            identity = self._verify(tx, snapshot.authorization, context, purpose, decision_time)
            return tx.stage_status(snapshot.authorization, entry, identity)

        return execute_once(tx, operation)

    @staticmethod
    def _load(tx, operation_id, unknown_if_absent=False):
        snapshot = tx.load(operation_id)
        if snapshot is None:
            if unknown_if_absent:
                raise CommitOutcomeUnknown(
                    "authorization absent; keep original operation quarantined"
                )
            raise OwnerDenied("authorization missing")
        _authorization(snapshot.authorization)
        if snapshot.authorization.operation_id != operation_id:
            raise OwnerHistoryInvalid("store returned a different operation")
        validate_history(snapshot.history)
        return snapshot

    def execute(
        self, tx: OwnerUnitOfWork, operation_id: str, context: Any, request: ExecutionRequest
    ) -> DurableReceipt:
        def operation():
            tx.acquire_global_lock()
            snapshot = self._load(tx, operation_id)
            decision_time = tx.decision_time()
            _time(decision_time)
            a = snapshot.authorization
            if (
                snapshot.history[-1].status != "ADMITTED"
                or snapshot.history[-1].occurred_at > decision_time
                or not a.valid_from <= decision_time < a.valid_to
                or snapshot.consumed
                or snapshot.receipt is not None
            ):
                raise OwnerDenied(
                    "authorization ineffective or operation consumed; "
                    "authorized reconciliation required"
                )
            _request(request)
            identity = self._verify(tx, a, context, "EXECUTION", decision_time)
            proof = self.trust.verify_execution(
                a,
                identity,
                request,
                snapshot.history[0].status_id,
                decision_time,
                context,
                tx,
            )
            self._proof(proof, snapshot, identity, request, decision_time)
            receipt = tx.stage_execution(a, request, identity, proof)
            self._receipt(receipt, a, request)
            if (
                receipt.assertion_id,
                receipt.evidence_id,
                receipt.event_id,
                receipt.decision_time,
                receipt.person_ref,
                receipt.db_session_user,
                receipt.result,
            ) != (
                identity.assertion_id,
                proof.evidence_id,
                proof.event_id,
                decision_time,
                identity.person_ref,
                identity.db_session_user,
                proof.result,
            ):
                raise OwnerHistoryInvalid("staged receipt/evidence mismatch")
            if identity.tenant_id is not None and (
                receipt.tenant_id != identity.tenant_id
                or receipt.organization_id != identity.organization_id
            ):
                raise OwnerHistoryInvalid("staged receipt tenant binding mismatch")
            return receipt

        return execute_once(tx, operation)

    @staticmethod
    def _proof(proof, snapshot, identity, request, decision_time):
        if not isinstance(proof, ExecutionEvidence):
            raise OwnerDependencyUnavailable("verified technical/fencing evidence unavailable")
        _refs(
            proof.evidence_id,
            proof.event_id,
            proof.technical_evidence_ref,
            proof.technical_verifier_ref,
            proof.authority_evidence_ref,
            proof.fencing_evidence_ref,
        )
        if (
            proof.authorization_id,
            proof.operation_id,
            proof.admitted_status_id,
            proof.assertion_id,
            proof.decision_time,
            proof.request_digest,
        ) != (
            snapshot.authorization.authorization_id,
            snapshot.authorization.operation_id,
            snapshot.history[0].status_id,
            identity.assertion_id,
            decision_time,
            request.request_digest,
        ):
            raise OwnerDenied("execution evidence binding mismatch")
        scoped_binding = (
            identity.tenant_id,
            identity.organization_id,
            identity.action,
            identity.target_resource,
            identity.policy_version,
        )
        proof_binding = (
            proof.tenant_id,
            proof.organization_id,
            proof.action,
            proof.target_resource,
            proof.policy_version,
        )
        if any(value is not None for value in scoped_binding) and proof_binding != scoped_binding:
            raise OwnerDenied("execution evidence tenant, policy, or resource binding mismatch")
        if proof.fence_generation is not None and (
            type(proof.fence_generation) is not int or proof.fence_generation < 1
        ):
            raise OwnerDenied("invalid fencing generation")
        if (
            not re.fullmatch(r"[0-9a-f]{64}", proof.technical_evidence_sha256)
            or not isinstance(proof.result, dict)
            or proof.result.get("event_id") != proof.event_id
        ):
            raise OwnerDenied("execution result or technical evidence incomplete")

    @staticmethod
    def _receipt(receipt, authorization, request):
        if not isinstance(receipt, OwnerReceipt):
            raise CommitOutcomeUnknown("owner receipt missing or incomplete")
        if (
            receipt.authorization_id,
            receipt.operation_id,
            receipt.person_ref,
            receipt.idempotency_key,
            receipt.canonical_bytes,
            receipt.request_digest,
        ) != (
            authorization.authorization_id,
            authorization.operation_id,
            authorization.operator_person_ref,
            request.idempotency_key,
            request.canonical_bytes,
            request.request_digest,
        ):
            raise CommitOutcomeUnknown("owner receipt conflict; keep operation quarantined")
        if (
            not isinstance(receipt.result, dict)
            or receipt.result.get("event_id") != receipt.event_id
        ):
            raise CommitOutcomeUnknown("owner receipt/result mismatch")
        _refs(receipt.event_id, receipt.assertion_id, receipt.evidence_id, receipt.db_session_user)

    def reconcile(
        self, tx: OwnerUnitOfWork, operation_id: str, context: Any, request: ExecutionRequest
    ) -> DurableReceipt:
        def operation():
            tx.acquire_global_lock()
            snapshot = self._load(tx, operation_id, unknown_if_absent=True)
            decision_time = tx.decision_time()
            _time(decision_time)
            _request(request)
            if snapshot.history[-1].occurred_at > decision_time:
                raise OwnerHistoryInvalid("receipt history lies after protected decision time")
            # D10 current read permission is separate from new mutation permission.
            identity = self._verify(
                tx, snapshot.authorization, context, "RECONCILIATION", decision_time
            )
            receipt = tx.read_receipt(
                snapshot.authorization.authorization_id,
                snapshot.authorization.operation_id,
                identity,
            )
            self._receipt(receipt, snapshot.authorization, request)
            return receipt

        return execute_once(tx, operation)

    def reconcile_status(
        self,
        tx: OwnerUnitOfWork,
        operation_id: str,
        context: Any,
        expected_status_id: str,
        expected_status: str,
        expected_predecessor_status_id: str | None,
    ) -> DurableReceipt:
        """Resolve a lost admission/revocation/invalidation COMMIT acknowledgement.

        Read the originally preallocated status ID under CURRENT read permission.
        Absence/conflict never permits a fresh status ID or an automatic mutation.
        """

        def operation():
            tx.acquire_global_lock()
            snapshot = self._load(tx, operation_id, unknown_if_absent=True)
            decision_time = tx.decision_time()
            _time(decision_time)
            if snapshot.history[-1].occurred_at > decision_time:
                raise OwnerHistoryInvalid("status history lies after protected decision time")
            self._verify(tx, snapshot.authorization, context, "RECONCILIATION", decision_time)
            matches = [entry for entry in snapshot.history if entry.status_id == expected_status_id]
            if (
                len(matches) != 1
                or matches[0].status != expected_status
                or matches[0].predecessor_status_id != expected_predecessor_status_id
            ):
                raise CommitOutcomeUnknown(
                    "original status absent/conflicting; keep operation quarantined"
                )
            return matches[0]

        return execute_once(tx, operation)
