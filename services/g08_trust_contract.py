"""Fail-closed G08 trust ports and signed, versioned isolated-qualification authority.

The synthetic policy store is process-local test infrastructure, not a D10
production provider. Nothing in this module is connected to the HTTP route or
database adapter. Signed envelopes are issued by external authorities; the
application receives verification keys only.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, Mapping, Protocol
from uuid import UUID

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from services.g08_owner_authorization import (
    Authorization,
    ExecutionEvidence,
    ExecutionRequest,
    OperatorAssertion,
    OwnerDenied,
    OwnerDependencyUnavailable,
    OwnerReceipt,
    OwnerUnitOfWork,
)


@dataclass(frozen=True)
class SignedEnvelope:
    key_id: str
    claims: Mapping[str, Any]
    signature: bytes


def canonical_claims(claims: Mapping[str, Any]) -> bytes:
    try:
        return json.dumps(
            claims,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as error:
        raise OwnerDenied("signed evidence is not canonical JSON") from error


class SignedEvidenceVerifier:
    def __init__(
        self,
        keys: Mapping[str, Ed25519PublicKey],
        *,
        audience: str,
        is_revoked: Callable[[str], bool],
        subject_by_key: Mapping[str, str] | None = None,
        subject_claim: str = "sub",
    ) -> None:
        if not keys or not audience or not callable(is_revoked):
            raise OwnerDependencyUnavailable(
                "signed-evidence trust roots and revocation provider are required"
            )
        self._keys = dict(keys)
        self._audience = audience
        self._is_revoked = is_revoked
        self._subject_by_key = dict(subject_by_key or {})
        self._subject_claim = subject_claim
        if self._subject_by_key and any(
            key_id not in self._keys for key_id in self._subject_by_key
        ):
            raise OwnerDependencyUnavailable("identity subject mapping references an untrusted key")

    def is_revoked(self, evidence_id: str) -> bool:
        try:
            return self._is_revoked(evidence_id)
        except (ConnectionError, OSError) as error:
            raise OwnerDependencyUnavailable(
                "evidence revocation service is unavailable"
            ) from error

    def verify(self, envelope: SignedEnvelope, decision_time: datetime) -> Mapping[str, Any]:
        _aware(decision_time)
        if not isinstance(envelope, SignedEnvelope) or not envelope.key_id:
            raise OwnerDenied("signed evidence is missing")
        key = self._keys.get(envelope.key_id)
        if key is None:
            raise OwnerDenied("signed evidence issuer is not trusted")
        claims = envelope.claims
        try:
            key.verify(envelope.signature, canonical_claims(claims))
        except (InvalidSignature, TypeError, ValueError) as error:
            raise OwnerDenied("signed evidence signature is invalid") from error
        _text(claims, "jti")
        if claims.get("aud") != self._audience:
            raise OwnerDenied("signed evidence audience mismatch")
        expected_subject = self._subject_by_key.get(envelope.key_id)
        if expected_subject is not None and claims.get(self._subject_claim) != expected_subject:
            raise OwnerDenied("signed evidence subject does not match its trusted identity key")
        issued = _timestamp(claims, "iat")
        expires = _timestamp(claims, "exp")
        if issued > decision_time or expires <= decision_time or expires <= issued:
            raise OwnerDenied("signed evidence is not currently valid")
        if self.is_revoked(str(claims["jti"])):
            raise OwnerDenied("signed evidence has been revoked")
        return claims

    def verify_subject_bound(
        self, envelope: SignedEnvelope, decision_time: datetime
    ) -> Mapping[str, Any]:
        if envelope.key_id not in self._subject_by_key:
            raise OwnerDenied("signed evidence issuer has no trusted subject binding")
        return self.verify(envelope, decision_time)


class D10PolicyAuthority(Protocol):
    """Current policy/revocation reads serialized with the owner transaction."""

    def current_version(
        self, authorization_id: str, operation_id: str, tenant_id: str, organization_id: str
    ) -> str: ...
    def policy(
        self, authorization_id: str, version: str, operation_id: str,
        tenant_id: str, organization_id: str,
    ) -> SignedEnvelope: ...
    def approvals(
        self, authorization_id: str, version: str, operation_id: str,
        tenant_id: str, organization_id: str,
    ) -> tuple[SignedEnvelope, ...]: ...
    def is_approval_revoked(self, approval_id: str, authorization_id: str) -> bool: ...
    def is_authorization_revoked(self, authorization_id: str) -> bool: ...
    def assert_current_in_transaction(
        self,
        transaction: OwnerUnitOfWork,
        authorization_id: str,
        version: str,
        approval_ids: tuple[str, ...],
        decision_time: datetime,
        operator_evidence_jti: str | None = None,
        scope: Mapping[str, Any] | None = None,
    ) -> None: ...


class VersionedSyntheticD10Authority:
    """Mutable in-memory authority for isolated qualification only; never allow-by-default."""

    def __init__(self) -> None:
        self._current: dict[str, str] = {}
        self._policies: dict[tuple[str, str], SignedEnvelope] = {}
        self._approvals: dict[tuple[str, str], tuple[SignedEnvelope, ...]] = {}
        self._revoked_approvals: set[str] = set()
        self._revoked_authorizations: set[str] = set()
        self._revoked_evidence: set[str] = set()

    def publish(
        self,
        authorization_id: str,
        version: str,
        policy: SignedEnvelope,
        approvals: tuple[SignedEnvelope, ...],
        *,
        current: bool = True,
    ) -> None:
        key = (authorization_id, version)
        if key in self._policies:
            raise ValueError("published policy versions are immutable")
        self._policies[key] = policy
        self._approvals[key] = tuple(approvals)
        if current:
            self._current[authorization_id] = version

    def select_current(self, authorization_id: str, version: str) -> None:
        if (authorization_id, version) not in self._policies:
            raise KeyError("policy version is not published")
        self._current[authorization_id] = version

    def revoke_approval(self, approval_id: str) -> None:
        self._revoked_approvals.add(approval_id)

    def revoke_authorization(self, authorization_id: str) -> None:
        self._revoked_authorizations.add(authorization_id)

    def revoke_evidence(self, evidence_jti: str) -> None:
        self._revoked_evidence.add(evidence_jti)

    def current_version(
        self,
        authorization_id: str,
        operation_id: str | None = None,
        tenant_id: str | None = None,
        organization_id: str | None = None,
    ) -> str:
        try:
            version = self._current[authorization_id]
        except KeyError as error:
            raise OwnerDependencyUnavailable("current D10 policy version is unavailable") from error
        self._assert_scope(
            authorization_id, version, operation_id, tenant_id, organization_id
        )
        return version

    def policy(
        self,
        authorization_id: str,
        version: str,
        operation_id: str | None = None,
        tenant_id: str | None = None,
        organization_id: str | None = None,
    ) -> SignedEnvelope:
        try:
            envelope = self._policies[(authorization_id, version)]
        except KeyError as error:
            raise OwnerDependencyUnavailable(
                "requested D10 policy version is unavailable"
            ) from error
        self._assert_scope(
            authorization_id, version, operation_id, tenant_id, organization_id
        )
        return envelope

    def approvals(
        self,
        authorization_id: str,
        version: str,
        operation_id: str | None = None,
        tenant_id: str | None = None,
        organization_id: str | None = None,
    ) -> tuple[SignedEnvelope, ...]:
        try:
            envelopes = self._approvals[(authorization_id, version)]
        except KeyError as error:
            raise OwnerDependencyUnavailable("D10 approval evidence is unavailable") from error
        self._assert_scope(
            authorization_id, version, operation_id, tenant_id, organization_id
        )
        return envelopes

    def _assert_scope(
        self,
        authorization_id: str,
        version: str,
        operation_id: str | None,
        tenant_id: str | None,
        organization_id: str | None,
    ) -> None:
        if operation_id is None and tenant_id is None and organization_id is None:
            return
        envelope = self._policies.get((authorization_id, version))
        if envelope is None or (
            envelope.claims.get("operation_id"),
            envelope.claims.get("tenant_id"),
            envelope.claims.get("organization_id"),
        ) != (operation_id, tenant_id, organization_id):
            raise OwnerDenied("D10 authority read is outside the requested tenant scope")

    def is_approval_revoked(self, approval_id: str, authorization_id: str | None = None) -> bool:
        if authorization_id is not None and not any(
            claims.get("approval_id") == approval_id
            for envelope_set in self._approvals.values()
            for claims in (envelope.claims for envelope in envelope_set)
            if claims.get("authorization_id") == authorization_id
        ):
            raise OwnerDenied("D10 approval is outside the requested authorization")
        return approval_id in self._revoked_approvals

    def is_authorization_revoked(self, authorization_id: str) -> bool:
        return authorization_id in self._revoked_authorizations

    def is_evidence_revoked(self, evidence_jti: str) -> bool:
        return evidence_jti in self._revoked_evidence

    def assert_current_in_transaction(
        self,
        transaction: OwnerUnitOfWork,
        authorization_id: str,
        version: str,
        approval_ids: tuple[str, ...],
        decision_time: datetime,
        operator_evidence_jti: str | None = None,
        scope: Mapping[str, Any] | None = None,
    ) -> None:
        if transaction is None:
            raise OwnerDependencyUnavailable("transactional D10 revalidation is required")
        _aware(decision_time)
        if scope is None:
            if self.current_version(authorization_id) != version:
                raise OwnerDenied("D10 policy changed before transactional execution")
        elif self.current_version(
            authorization_id,
            str(scope["operation_id"]),
            str(scope["tenant_id"]),
            str(scope["organization_id"]),
        ) != version:
            raise OwnerDenied("D10 policy changed before transactional execution")
        if self.is_authorization_revoked(authorization_id):
            raise OwnerDenied("owner authorization was revoked before transactional execution")
        if any(
            self.is_approval_revoked(approval_id, authorization_id)
            for approval_id in approval_ids
        ):
            raise OwnerDenied("D10 approval was revoked before transactional execution")
        if operator_evidence_jti and self.is_evidence_revoked(operator_evidence_jti):
            raise OwnerDenied("independent operator evidence was revoked before execution")


@dataclass(frozen=True)
class G08TrustRequest:
    application_session: SignedEnvelope
    operator_evidence: SignedEnvelope
    policy_version: str
    fencing_evidence: SignedEnvelope | None = None
    technical_evidence: SignedEnvelope | None = None
    admission_evidence: SignedEnvelope | None = None


class ApplicationSessionVerifier(Protocol):
    def verify(self, envelope: SignedEnvelope, decision_time: datetime) -> Mapping[str, Any]: ...


class OperatorEvidenceVerifier(Protocol):
    def verify(self, envelope: SignedEnvelope, decision_time: datetime) -> Mapping[str, Any]: ...
    def verify_subject_bound(
        self, envelope: SignedEnvelope, decision_time: datetime
    ) -> Mapping[str, Any]: ...


@dataclass(frozen=True)
class FencingProof:
    evidence_ref: str
    generation: int


class TransactionalFencingVerifier(Protocol):
    def verify_in_transaction(
        self,
        transaction: OwnerUnitOfWork,
        evidence: SignedEnvelope,
        scope: Mapping[str, str],
        decision_time: datetime,
    ) -> FencingProof: ...


class FenceGenerationStore(Protocol):
    """Read the current generation under the owner transaction's scope lock."""

    def is_fencing_token_revoked_in_transaction(
        self, transaction: OwnerUnitOfWork, scope: Mapping[str, str], evidence_jti: str
    ) -> bool: ...

    def current_generation_in_transaction(
        self,
        transaction: OwnerUnitOfWork,
        scope: Mapping[str, str],
    ) -> int: ...


class SignedTransactionalFencingVerifier:
    def __init__(
        self,
        evidence_verifier: SignedEvidenceVerifier,
        generations: FenceGenerationStore,
    ) -> None:
        if evidence_verifier is None or generations is None:
            raise OwnerDependencyUnavailable(
                "signed fence verifier and transactional generation store are required"
            )
        self.evidence_verifier = evidence_verifier
        self.generations = generations

    def verify_in_transaction(
        self,
        transaction: OwnerUnitOfWork,
        evidence: SignedEnvelope,
        scope: Mapping[str, str],
        decision_time: datetime,
    ) -> FencingProof:
        claims = self.evidence_verifier.verify_subject_bound(evidence, decision_time)
        for field in (
            "jti",
            "authorization_id",
            "operation_id",
            "tenant_id",
            "organization_id",
            "action",
            "target_resource",
        ):
            _text(claims, field)
        if any(claims[field] != expected for field, expected in scope.items()):
            raise OwnerDenied("fencing token scope mismatch")
        if self.generations.is_fencing_token_revoked_in_transaction(
            transaction, scope, str(claims["jti"])
        ):
            raise OwnerDenied("fencing token has been revoked")
        generation = claims.get("generation")
        current_generation = self.generations.current_generation_in_transaction(transaction, scope)
        if (
            type(generation) is not int
            or generation < 1
            or type(current_generation) is not int
            or generation != current_generation
        ):
            raise OwnerDenied("stale or invalid fencing generation")
        return FencingProof(
            evidence_ref=f"fence:{claims['jti']}",
            generation=generation,
        )


@dataclass(frozen=True)
class VerifiedTechnicalExecution:
    event_id: str
    result: dict[str, Any]
    evidence_ref: str
    evidence_sha256: str
    verifier_ref: str


class TechnicalEvidenceVerifier(Protocol):
    def verify_admission_in_transaction(
        self,
        transaction: OwnerUnitOfWork,
        authorization: Authorization,
        scope: Mapping[str, str],
        decision_time: datetime,
        evidence: SignedEnvelope | None = None,
    ) -> str: ...

    def verify_in_transaction(
        self,
        transaction: OwnerUnitOfWork,
        authorization: Authorization,
        operator: OperatorAssertion,
        request: ExecutionRequest,
        scope: Mapping[str, str],
        decision_time: datetime,
        evidence: SignedEnvelope | None = None,
    ) -> VerifiedTechnicalExecution: ...


class SignedD08TechnicalEvidenceVerifier:
    """Verifies signed D08 execution evidence against explicit issuer trust roots."""

    def __init__(self, evidence_verifier: SignedEvidenceVerifier) -> None:
        if evidence_verifier is None:
            raise OwnerDependencyUnavailable("D08 technical-evidence trust roots are required")
        self.evidence_verifier = evidence_verifier

    def verify_admission_in_transaction(
        self,
        transaction: OwnerUnitOfWork,
        authorization: Authorization,
        scope: Mapping[str, str],
        decision_time: datetime,
        evidence: SignedEnvelope | None = None,
    ) -> str:
        if evidence is None:
            raise OwnerDependencyUnavailable("signed D08 admission evidence is required")
        claims = self.evidence_verifier.verify_subject_bound(evidence, decision_time)
        expected = {
            "phase": "ADMISSION",
            "authorization_id": authorization.authorization_id,
            "operation_id": authorization.operation_id,
            "tenant_id": scope.get("tenant_id"),
            "organization_id": scope.get("organization_id"),
            "action": scope.get("action"),
            "target_resource": scope.get("target_resource"),
        }
        if any(claims.get(name) != value for name, value in expected.items()):
            raise OwnerDenied("signed D08 admission evidence does not match the authorized scope")
        evidence_hash = hashlib.sha256(
            canonical_claims(claims) + evidence.signature
        ).hexdigest()
        binding = f"{_text(claims, 'evidence_ref')}:{evidence_hash}"
        if authorization.evidence_ref != binding:
            raise OwnerDenied("D08 admission evidence is not bound to the canonical authorization")
        return binding

    def verify_in_transaction(
        self,
        transaction: OwnerUnitOfWork,
        authorization: Authorization,
        operator: OperatorAssertion,
        request: ExecutionRequest,
        scope: Mapping[str, str],
        decision_time: datetime,
        evidence: SignedEnvelope | None = None,
    ) -> VerifiedTechnicalExecution:
        if evidence is None:
            raise OwnerDependencyUnavailable("signed D08 technical evidence is required")
        claims = self.evidence_verifier.verify_subject_bound(evidence, decision_time)
        expected = {
            "authorization_id": authorization.authorization_id,
            "operation_id": authorization.operation_id,
            "tenant_id": scope.get("tenant_id"),
            "organization_id": scope.get("organization_id"),
            "action": scope.get("action"),
            "target_resource": scope.get("target_resource"),
            "request_digest": request.request_digest,
        }
        if any(claims.get(name) != value for name, value in expected.items()):
            raise OwnerDenied("signed D08 evidence does not match the authorized execution scope")
        event_id = _text(claims, "event_id")
        evidence_ref = _text(claims, "evidence_ref")
        verifier_ref = _text(claims, "verifier_ref")
        result = claims.get("result")
        if not isinstance(result, dict) or result.get("event_id") != event_id:
            raise OwnerDenied("signed D08 result does not bind its canonical event")
        return VerifiedTechnicalExecution(
            event_id=event_id,
            result=dict(result),
            evidence_ref=evidence_ref,
            evidence_sha256=hashlib.sha256(
                canonical_claims(claims) + evidence.signature
            ).hexdigest(),
            verifier_ref=f"{verifier_ref}:{evidence.key_id}",
        )


class SignedG08OwnerTrust:
    """OwnerTrust adapter that verifies user, operator, D10 approvals, and execution evidence."""

    def __init__(
        self,
        *,
        application_sessions: ApplicationSessionVerifier,
        operator_evidence: OperatorEvidenceVerifier,
        policy_authority: D10PolicyAuthority,
        policy_verifier: SignedEvidenceVerifier,
        approval_verifier: SignedEvidenceVerifier,
        fencing_verifier: TransactionalFencingVerifier,
        technical_verifier: TechnicalEvidenceVerifier,
    ) -> None:
        dependencies = (
            application_sessions,
            operator_evidence,
            policy_authority,
            policy_verifier,
            approval_verifier,
            fencing_verifier,
            technical_verifier,
        )
        if any(dependency is None for dependency in dependencies):
            raise OwnerDependencyUnavailable("all G08 trust and execution providers are required")
        if not callable(getattr(operator_evidence, "is_revoked", None)):
            raise OwnerDependencyUnavailable("operator evidence revocation lookup is required")
        required_policy_methods = (
            "current_version",
            "policy",
            "approvals",
            "is_approval_revoked",
            "is_authorization_revoked",
            "assert_current_in_transaction",
        )
        if any(
            not callable(getattr(policy_authority, method, None))
            for method in required_policy_methods
        ):
            raise OwnerDependencyUnavailable(
                "complete current and transactional D10 provider is required"
            )
        if not callable(getattr(application_sessions, "verify", None)):
            raise OwnerDependencyUnavailable("application-session verifier is unavailable")
        if not callable(getattr(operator_evidence, "verify_subject_bound", None)):
            raise OwnerDependencyUnavailable("independent operator verifier is unavailable")
        if not callable(getattr(fencing_verifier, "verify_in_transaction", None)):
            raise OwnerDependencyUnavailable("transactional fencing verifier is unavailable")
        if not callable(getattr(technical_verifier, "verify_in_transaction", None)):
            raise OwnerDependencyUnavailable("technical evidence verifier is unavailable")
        if not callable(getattr(technical_verifier, "verify_admission_in_transaction", None)):
            raise OwnerDependencyUnavailable("D08 admission evidence verifier is unavailable")
        self.application_sessions = application_sessions
        self.operator_evidence = operator_evidence
        self.policy_authority = policy_authority
        self.policy_verifier = policy_verifier
        self.approval_verifier = approval_verifier
        self.fencing_verifier = fencing_verifier
        self.technical_verifier = technical_verifier

    def _bundle(
        self,
        context: Any,
        authorization: Authorization,
        purpose: str,
        decision_time: datetime,
    ) -> tuple[Mapping[str, Any], Mapping[str, Any], Mapping[str, Any], tuple[str, ...]]:
        if not isinstance(context, G08TrustRequest):
            raise OwnerDependencyUnavailable("verified application/operator context is required")
        app = self.application_sessions.verify(context.application_session, decision_time)
        operator = self.operator_evidence.verify_subject_bound(
            context.operator_evidence, decision_time
        )
        current_version = self.policy_authority.current_version(
            authorization.authorization_id,
            authorization.operation_id,
            str(authorization.tenant_id or ""),
            str(authorization.organization_id or ""),
        )
        if context.policy_version != current_version:
            raise OwnerDenied("stale D10 policy version")
        policy_envelope = self.policy_authority.policy(
            authorization.authorization_id,
            current_version,
            authorization.operation_id,
            str(authorization.tenant_id or ""),
            str(authorization.organization_id or ""),
        )
        policy = self.policy_verifier.verify_subject_bound(policy_envelope, decision_time)
        self._check_scope(app, operator, policy, authorization, purpose, decision_time)
        approvals = self._verify_approvals(policy, authorization, decision_time)
        return app, operator, policy, approvals

    def _check_scope(
        self,
        app: Mapping[str, Any],
        operator: Mapping[str, Any],
        policy: Mapping[str, Any],
        authorization: Authorization,
        purpose: str,
        decision_time: datetime,
    ) -> None:
        for field in (
            "policy_id",
            "version",
            "authorization_id",
            "operation_id",
            "tenant_id",
            "organization_id",
            "action",
            "target_resource",
            "requester_uid",
        ):
            _text(policy, field)
        start = _timestamp(policy, "not_before")
        end = _timestamp(policy, "expires_at")
        if not start <= decision_time < end:
            raise OwnerDenied("D10 policy is not currently valid")
        if (
            policy["authorization_id"] != authorization.authorization_id
            or policy["operation_id"] != authorization.operation_id
            or policy["tenant_id"] != app.get("tenant_id")
            or policy["organization_id"] != app.get("organization_id")
            or policy["organization_id"] != policy["tenant_id"]
            or policy["requester_uid"] != app.get("sub")
        ):
            raise OwnerDenied("signed policy does not bind this authenticated tenant and operation")
        if policy.get("version") != self.policy_authority.current_version(
            authorization.authorization_id,
            authorization.operation_id,
            str(policy["tenant_id"]),
            str(policy["organization_id"]),
        ):
            raise OwnerDenied("signed D10 policy version does not match the current version")
        if purpose not in _string_set(policy, "allowed_phases"):
            raise OwnerDenied("D10 policy does not permit this operation phase")
        if str(operator.get("sub")) not in _string_set(policy, "allowed_operator_uids"):
            raise OwnerDenied("independent operator is not authorized by current policy")
        for name, value in (
            ("tenant_id", policy["tenant_id"]),
            ("organization_id", policy["organization_id"]),
            ("action", policy["action"]),
            ("target_resource", policy["target_resource"]),
            ("policy_version", policy["version"]),
            ("requester_auth_uid", policy["requester_uid"]),
        ):
            supplied = getattr(authorization, name, None)
            if supplied is not None and supplied != value:
                raise OwnerDenied(f"authorization {name} conflicts with signed D10 scope")
        if authorization.operator_person_ref != operator.get("person_ref"):
            raise OwnerDenied("operator person is not independently verified as authorized")
        if authorization.authentication_evidence_ref != operator.get("evidence_ref"):
            raise OwnerDenied("operator evidence reference conflicts with authorization")
        if authorization.authentication_evidence_sha256 != operator.get("evidence_sha256"):
            raise OwnerDenied("operator evidence digest conflicts with authorization")
        _text(operator, "session_binding_ref")
        _text(app, "session_id")
        _text(app, "db_session_user")
        if operator["session_binding_ref"] != app["session_id"]:
            raise OwnerDenied(
                "operator evidence is not bound to the authenticated application session"
            )

    def _verify_approvals(
        self,
        policy: Mapping[str, Any],
        authorization: Authorization,
        decision_time: datetime,
    ) -> tuple[str, ...]:
        threshold = policy.get("approval_threshold")
        if type(threshold) is not int or threshold < 1:
            raise OwnerDenied("D10 approval threshold is missing or invalid")
        approved_uids: set[str] = set()
        approval_ids: list[str] = []
        for envelope in self.policy_authority.approvals(
            authorization.authorization_id,
            str(policy["version"]),
            authorization.operation_id,
            str(policy["tenant_id"]),
            str(policy["organization_id"]),
        ):
            approval = self.approval_verifier.verify_subject_bound(envelope, decision_time)
            for field in (
                "approval_id",
                "policy_id",
                "policy_version",
                "authorization_id",
                "operation_id",
                "tenant_id",
                "organization_id",
                "action",
                "target_resource",
                "requester_uid",
                "approver_uid",
            ):
                _text(approval, field)
            expected = (
                policy["policy_id"],
                policy["version"],
                authorization.authorization_id,
                authorization.operation_id,
                policy["tenant_id"],
                policy["organization_id"],
                policy["action"],
                policy["target_resource"],
                policy["requester_uid"],
            )
            actual = tuple(
                approval[field]
                for field in (
                    "policy_id",
                    "policy_version",
                    "authorization_id",
                    "operation_id",
                    "tenant_id",
                    "organization_id",
                    "action",
                    "target_resource",
                    "requester_uid",
                )
            )
            if actual != expected:
                raise OwnerDenied("approval is not bound to the exact D10 operation scope")
            if approval["approver_uid"] == policy["requester_uid"]:
                raise OwnerDenied("PO-D10 requires requester and approver to be distinct")
            if approval["approver_uid"] in approved_uids:
                raise OwnerDenied("duplicate approver does not satisfy the D10 threshold")
            if self.policy_authority.is_approval_revoked(
                approval["approval_id"], authorization.authorization_id
            ):
                raise OwnerDenied("D10 approval has been revoked")
            approved_uids.add(approval["approver_uid"])
            approval_ids.append(approval["approval_id"])
        if len(approval_ids) < threshold:
            raise OwnerDenied("current D10 approval threshold is not met")
        pairs = policy.get("distinct_identity_pairs", [])
        if not isinstance(pairs, list):
            raise OwnerDenied("D10 identity-separation rules are invalid")
        for pair in pairs:
            if (
                not isinstance(pair, list)
                or len(pair) != 2
                or pair[0] == pair[1]
                or any(item not in {"requester", "approver", "operator"} for item in pair)
            ):
                raise OwnerDenied("D10 identity-separation rule is invalid")
        return tuple(sorted(approval_ids))

    def verify_operator(
        self,
        context: Any,
        authorization: Authorization,
        purpose: str,
        decision_time: datetime,
    ) -> OperatorAssertion:
        app, operator, policy, approvals = self._bundle(
            context, authorization, purpose, decision_time
        )
        approved = {
            _approval_uid(self.approval_verifier.verify_subject_bound(item, decision_time))
            for item in self.policy_authority.approvals(
                authorization.authorization_id,
                str(policy["version"]),
                authorization.operation_id,
                str(policy["tenant_id"]),
                str(policy["organization_id"]),
            )
        }
        for pair in policy.get("distinct_identity_pairs", ()):
            identities = {
                "requester": str(app["sub"]),
                "operator": str(operator["sub"]),
            }
            if pair[0] == "approver":
                other = identities[pair[1]]
                if other in approved:
                    raise OwnerDenied("D10 requires approver and selected identity to be distinct")
            elif pair[1] == "approver":
                other = identities[pair[0]]
                if other in approved:
                    raise OwnerDenied("D10 requires approver and selected identity to be distinct")
            elif identities[pair[0]] == identities[pair[1]]:
                raise OwnerDenied("D10 identity-separation rule is not satisfied")
        until = min(
            _timestamp(operator, "exp"),
            _timestamp(policy, "expires_at"),
        )
        evidence_bytes = canonical_claims(context.operator_evidence.claims)
        return OperatorAssertion(
            assertion_id=_stable_uuid(
                evidence_bytes + context.operator_evidence.signature + purpose.encode("ascii")
            ),
            authorization_id=authorization.authorization_id,
            operation_id=authorization.operation_id,
            purpose=purpose,
            person_ref=str(operator["person_ref"]),
            authentication_evidence_ref=str(operator["evidence_ref"]),
            authentication_evidence_sha256=str(operator["evidence_sha256"]),
            session_binding_ref=str(operator["session_binding_ref"]),
            db_session_user=str(app["db_session_user"]),
            verified_auth_uid=str(operator["sub"]),
            verifier_ref=f"operator-issuer:{context.operator_evidence.key_id}",
            verified_at=decision_time,
            valid_until=until,
            tenant_id=str(policy["tenant_id"]),
            organization_id=str(policy["organization_id"]),
            action=str(policy["action"]),
            target_resource=str(policy["target_resource"]),
            policy_version=str(policy["version"]),
            requester_auth_uid=str(policy["requester_uid"]),
            approval_ids=approvals,
            d10_evidence_ref=f"d10:{policy['policy_id']}:{policy['version']}",
            evidence_jti=str(operator["jti"]),
            approval_manifest=self._approval_manifest(
                authorization, policy, decision_time, approvals
            ),
        )

    def _approval_manifest(
        self,
        authorization: Authorization,
        policy: Mapping[str, Any],
        decision_time: datetime,
        approval_ids: tuple[str, ...],
    ) -> tuple[dict[str, Any], ...]:
        manifest: list[dict[str, Any]] = []
        for envelope in self.policy_authority.approvals(
            authorization.authorization_id,
            str(policy["version"]),
            authorization.operation_id,
            str(policy["tenant_id"]),
            str(policy["organization_id"]),
        ):
            claims = self.approval_verifier.verify_subject_bound(envelope, decision_time)
            if claims.get("approval_id") not in approval_ids:
                continue
            manifest.append(
                {
                    "authorization_id": authorization.authorization_id,
                    "approval_ref": str(claims["approval_id"]),
                    "approver_person_ref": str(claims["approver_uid"]),
                    "attestation_sha256": hashlib.sha256(envelope.signature).hexdigest(),
                    "evidence_ref": f"d10-approval:{claims['jti']}",
                }
            )
        if tuple(sorted(item["approval_ref"] for item in manifest)) != approval_ids:
            raise OwnerDenied("verified D10 approvals do not match the canonical manifest")
        return tuple(manifest)

    def authorize(
        self,
        authorization: Authorization,
        operator: OperatorAssertion,
        purpose: str,
        decision_time: datetime,
        context: Any,
        transaction: OwnerUnitOfWork,
    ) -> None:
        _aware(decision_time)
        app, verified_operator, policy, approvals = self._bundle(
            context, authorization, purpose, decision_time
        )
        expected_assertion_id = _stable_uuid(
            canonical_claims(context.operator_evidence.claims)
            + context.operator_evidence.signature
            + purpose.encode("ascii")
        )
        if (
            operator.authorization_id != authorization.authorization_id
            or operator.operation_id != authorization.operation_id
            or operator.purpose != purpose
            or operator.assertion_id != expected_assertion_id
            or operator.verified_auth_uid != verified_operator.get("sub")
            or operator.evidence_jti != verified_operator.get("jti")
            or operator.person_ref != verified_operator.get("person_ref")
            or operator.authentication_evidence_ref != verified_operator.get("evidence_ref")
            or operator.authentication_evidence_sha256 != verified_operator.get("evidence_sha256")
            or operator.session_binding_ref != app.get("session_id")
            or operator.db_session_user != app.get("db_session_user")
            or operator.requester_auth_uid != app.get("sub")
            or operator.tenant_id != policy.get("tenant_id")
            or operator.organization_id != policy.get("organization_id")
            or operator.action != policy.get("action")
            or operator.target_resource != policy.get("target_resource")
            or operator.policy_version != policy.get("version")
            or operator.approval_ids != approvals
            or tuple(sorted(item["approval_ref"] for item in operator.approval_manifest))
            != approvals
            or not operator.tenant_id
            or not operator.policy_version
            or not operator.d10_evidence_ref
        ):
            raise OwnerDenied("verified D10 scope is required for owner authorization")
        if self.policy_authority.is_authorization_revoked(authorization.authorization_id):
            raise OwnerDenied("owner authorization has been revoked")
        if self.operator_evidence.is_revoked(str(operator.evidence_jti or "")):
            raise OwnerDenied("independent operator evidence has been revoked")
        self._check_assertion_scope(policy, authorization, operator, purpose)
        self.policy_authority.assert_current_in_transaction(
            transaction,
            authorization.authorization_id,
            operator.policy_version,
            operator.approval_ids,
            decision_time,
            operator.evidence_jti,
            {
                "operation_id": authorization.operation_id,
                "tenant_id": operator.tenant_id,
                "organization_id": operator.organization_id,
                "action": operator.action,
                "target_resource": operator.target_resource,
                "requester_uid": operator.requester_auth_uid,
                "operator_uid": operator.verified_auth_uid,
            },
        )
        if purpose == "ADMISSION":
            self.technical_verifier.verify_admission_in_transaction(
                transaction,
                authorization,
                {
                    "authorization_id": authorization.authorization_id,
                    "operation_id": authorization.operation_id,
                    "tenant_id": operator.tenant_id or "",
                    "organization_id": operator.organization_id or "",
                    "action": operator.action or "",
                    "target_resource": operator.target_resource or "",
                },
                decision_time,
                context.admission_evidence,
            )

    @staticmethod
    def _check_assertion_scope(
        policy: Mapping[str, Any],
        authorization: Authorization,
        operator: OperatorAssertion,
        purpose: str,
    ) -> None:
        if (
            policy.get("authorization_id"),
            policy.get("operation_id"),
            policy.get("tenant_id"),
            policy.get("organization_id"),
            policy.get("action"),
            policy.get("target_resource"),
            policy.get("version"),
            policy.get("requester_uid"),
        ) != (
            authorization.authorization_id,
            authorization.operation_id,
            operator.tenant_id,
            operator.organization_id,
            operator.action,
            operator.target_resource,
            operator.policy_version,
            operator.requester_auth_uid,
        ) or purpose not in _string_set(policy, "allowed_phases"):
            raise OwnerDenied("D10 scope changed or does not permit this phase")

    def verify_execution(
        self,
        authorization: Authorization,
        operator: OperatorAssertion,
        request: ExecutionRequest,
        admitted_status_id: str,
        decision_time: datetime,
        context: Any,
        transaction: OwnerUnitOfWork,
    ) -> ExecutionEvidence:
        self.authorize(authorization, operator, "EXECUTION", decision_time, context, transaction)
        app, verified_operator, policy, _ = self._bundle(
            context,
            authorization,
            "EXECUTION",
            decision_time,
        )
        if (
            str(verified_operator.get("sub")) != operator.verified_auth_uid
            or str(app.get("tenant_id")) != operator.tenant_id
            or request.request_digest != policy.get("request_digest")
        ):
            raise OwnerDenied("execution request or identity differs from approved D10 scope")
        fence_envelope = context.fencing_evidence
        if fence_envelope is None:
            raise OwnerDependencyUnavailable("transactional fencing evidence is required")
        scope = {
            "authorization_id": authorization.authorization_id,
            "operation_id": authorization.operation_id,
            "tenant_id": str(policy["tenant_id"]),
            "organization_id": str(policy["organization_id"]),
            "action": str(policy["action"]),
            "target_resource": str(policy["target_resource"]),
        }
        fence = self.fencing_verifier.verify_in_transaction(
            transaction,
            fence_envelope,
            scope,
            decision_time,
        )
        if type(fence.generation) is not int or fence.generation < 1 or not fence.evidence_ref:
            raise OwnerDenied("invalid current fencing proof")
        technical = self.technical_verifier.verify_in_transaction(
            transaction,
            authorization,
            operator,
            request,
            scope,
            decision_time,
            context.technical_evidence,
        )
        if (
            not technical.event_id
            or not isinstance(technical.result, dict)
            or technical.result.get("event_id") != technical.event_id
            or not re.fullmatch(r"[0-9a-f]{64}", technical.evidence_sha256)
            or not technical.evidence_ref
            or not technical.verifier_ref
        ):
            raise OwnerDenied("technical execution evidence is incomplete")
        self.policy_authority.assert_current_in_transaction(
            transaction,
            authorization.authorization_id,
            operator.policy_version or "",
            operator.approval_ids,
            decision_time,
            operator.evidence_jti,
            {
                **scope,
                "requester_uid": operator.requester_auth_uid,
                "operator_uid": operator.verified_auth_uid,
                "fence_jti": str(fence_envelope.claims.get("jti", "")),
                "fence_generation": fence.generation,
            },
        )
        return ExecutionEvidence(
            evidence_id=_stable_uuid(
                f"{authorization.authorization_id}:{request.request_digest}:{fence.generation}".encode()
            ),
            authorization_id=authorization.authorization_id,
            operation_id=authorization.operation_id,
            admitted_status_id=admitted_status_id,
            assertion_id=operator.assertion_id,
            event_id=technical.event_id,
            decision_time=decision_time,
            request_digest=request.request_digest,
            result=technical.result,
            technical_evidence_ref=technical.evidence_ref,
            technical_evidence_sha256=technical.evidence_sha256,
            technical_verifier_ref=technical.verifier_ref,
            authority_evidence_ref=operator.d10_evidence_ref or "",
            fencing_evidence_ref=fence.evidence_ref,
            tenant_id=operator.tenant_id,
            organization_id=operator.organization_id,
            action=operator.action,
            target_resource=operator.target_resource,
            policy_version=operator.policy_version,
            fence_generation=fence.generation,
        )


class TenantScopedReceiptProjection:
    """Authorize a minimal receipt projection using the current signed D10 read grant."""

    def __init__(
        self,
        *,
        application_sessions: ApplicationSessionVerifier,
        policy_authority: D10PolicyAuthority,
        policy_verifier: SignedEvidenceVerifier,
    ) -> None:
        if any(
            dependency is None
            for dependency in (application_sessions, policy_authority, policy_verifier)
        ):
            raise OwnerDependencyUnavailable(
                "receipt-session and current D10 projection providers are required"
            )
        self.application_sessions = application_sessions
        self.policy_authority = policy_authority
        self.policy_verifier = policy_verifier

    def project(
        self,
        session: SignedEnvelope,
        authorization_id: str,
        operation_id: str,
        policy_version: str,
        receipt: OwnerReceipt,
        decision_time: datetime,
    ) -> dict[str, Any]:
        app = self.application_sessions.verify(session, decision_time)
        if self.policy_authority.is_authorization_revoked(authorization_id):
            raise OwnerDenied("receipt projection authority has been revoked")
        if self.policy_authority.current_version(
            authorization_id,
            operation_id,
            str(app.get("tenant_id") or ""),
            str(app.get("organization_id") or ""),
        ) != policy_version:
            raise OwnerDenied("receipt projection policy is stale")
        policy = self.policy_verifier.verify_subject_bound(
            self.policy_authority.policy(
                authorization_id,
                policy_version,
                operation_id,
                str(app.get("tenant_id") or ""),
                str(app.get("organization_id") or ""),
            ),
            decision_time,
        )
        if not (
            _timestamp(policy, "not_before") <= decision_time < _timestamp(policy, "expires_at")
        ):
            raise OwnerDenied("receipt projection policy is not currently valid")
        if (
            policy.get("authorization_id") != authorization_id
            or policy.get("operation_id") != operation_id
            or policy.get("tenant_id") != app.get("tenant_id")
            or policy.get("organization_id") != app.get("organization_id")
            or policy.get("organization_id") != policy.get("tenant_id")
            or str(app.get("sub")) not in _string_set(policy, "receipt_reader_uids")
        ):
            raise OwnerDenied("receipt is outside the current authorized tenant projection")
        if (receipt.authorization_id, receipt.operation_id) != (authorization_id, operation_id):
            raise OwnerDenied("receipt does not match the authorized operation")
        if (
            not isinstance(receipt.result, dict)
            or receipt.result.get("event_id") != receipt.event_id
            or not receipt.event_id
        ):
            raise OwnerDenied("receipt is incomplete")
        if (
            receipt.tenant_id is not None
            and receipt.tenant_id != policy["tenant_id"]
            or receipt.organization_id is not None
            and receipt.organization_id != policy["organization_id"]
        ):
            raise OwnerDenied("receipt scope conflicts with signed D10 binding")
        return {
            "authorization_id": receipt.authorization_id,
            "operation_id": receipt.operation_id,
            "event_id": receipt.event_id,
            "result": dict(receipt.result),
            "decision_time": receipt.decision_time.isoformat(),
        }


def _approval_uid(approval: Mapping[str, Any]) -> str:
    return str(approval["approver_uid"])


def _string_set(claims: Mapping[str, Any], name: str) -> set[str]:
    value = claims.get(name)
    if not isinstance(value, list) or any(not isinstance(item, str) or not item for item in value):
        raise OwnerDenied(f"signed evidence {name} must be a string list")
    return set(value)


def _text(claims: Mapping[str, Any], name: str) -> str:
    value = claims.get(name)
    if not isinstance(value, str) or not value.strip():
        raise OwnerDenied(f"signed evidence {name} is required")
    return value


def _timestamp(claims: Mapping[str, Any], name: str) -> datetime:
    value = _text(claims, name)
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise OwnerDenied(f"signed evidence {name} is invalid") from error
    _aware(result)
    return result


def _aware(value: datetime) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise OwnerDenied("timezone-aware decision time is required")


def _stable_uuid(value: bytes) -> str:
    return str(UUID(bytes=hashlib.sha256(value).digest()[:16], version=5))
