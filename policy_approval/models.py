"""Immutable WP-012 policy, approval, exception, and history contracts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from types import MappingProxyType
from typing import Any, Mapping

from recommendation_decision import Actor


class PolicyEvaluationResult(StrEnum):
    ALLOW = "allow"
    DENY = "deny"
    INDETERMINATE = "indeterminate"


class EvidenceState(StrEnum):
    AVAILABLE = "available"
    STALE = "stale"
    MISSING = "missing"
    CONFLICTING = "conflicting"
    SUPERSEDED = "superseded"


class PolicyState(StrEnum):
    ACTIVE = "active"
    REVOKED = "revoked"
    SUPERSEDED = "superseded"


class ApprovalState(StrEnum):
    ACTIVE = "active"
    EXPIRED = "expired"
    REVOKED = "revoked"
    SUPERSEDED = "superseded"


class ExceptionState(StrEnum):
    REQUESTED = "requested"
    ACTIVE = "active"
    EXPIRED = "expired"
    REVOKED = "revoked"
    SUPERSEDED = "superseded"


@dataclass(frozen=True, slots=True)
class AuthorityScope:
    action: str
    resource_type: str
    resource_id: str

    def __post_init__(self) -> None:
        if not self.action or not self.resource_type or not self.resource_id:
            raise ValueError("authority scope must be exact")


@dataclass(frozen=True, slots=True)
class PolicyRule:
    rule_id: str
    input_name: str
    expected_value: Any
    failure_reason: str

    def __post_init__(self) -> None:
        if not self.rule_id or not self.input_name or not self.failure_reason:
            raise ValueError("policy rule identity, input, and reason are required")


@dataclass(frozen=True, slots=True)
class PolicyReference:
    policy_id: str
    organization_id: str
    tenant_id: str
    version: int
    evaluator_version: str
    rules: tuple[PolicyRule, ...]
    required_inputs: tuple[str, ...]
    effective_at: datetime
    expires_at: datetime | None = None
    state: PolicyState = PolicyState.ACTIVE
    lineage_refs: tuple[str, ...] = ()
    provenance_refs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "rules", tuple(sorted(self.rules, key=lambda rule: rule.rule_id)))
        object.__setattr__(self, "required_inputs", tuple(sorted(set(self.required_inputs))))
        object.__setattr__(self, "state", PolicyState(self.state))
        if not self.policy_id or not self.evaluator_version:
            raise ValueError("policy identity and evaluator version are required")
        if self.version < 1:
            raise ValueError("policy version must be positive")
        _aware(self.effective_at, "policy effective_at")
        if self.expires_at is not None:
            _aware(self.expires_at, "policy expires_at")
            if self.expires_at <= self.effective_at:
                raise ValueError("policy expiry must follow effective time")


@dataclass(frozen=True, slots=True)
class PolicyEvaluation:
    evaluation_id: str
    organization_id: str
    tenant_id: str
    decision_id: str
    decision_version: int
    evidence_package_id: str
    evidence_package_hash: str
    policy_id: str
    policy_version: int
    evaluator_version: str
    evaluated_at: datetime
    result: PolicyEvaluationResult
    reasons: tuple[str, ...]
    evidence_states: Mapping[str, EvidenceState]
    normalized_inputs: Mapping[str, Any]
    scope: AuthorityScope
    input_hash: str
    lineage_refs: tuple[str, ...] = ()
    provenance_refs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "result", PolicyEvaluationResult(self.result))
        object.__setattr__(self, "reasons", tuple(sorted(set(self.reasons))))
        object.__setattr__(
            self,
            "evidence_states",
            MappingProxyType(
                {key: EvidenceState(value) for key, value in sorted(self.evidence_states.items())}
            ),
        )
        object.__setattr__(
            self,
            "normalized_inputs",
            MappingProxyType(dict(sorted(self.normalized_inputs.items()))),
        )
        _aware(self.evaluated_at, "evaluation timestamp")
        if not self.evaluation_id or not self.input_hash or not self.reasons:
            raise ValueError("evaluation identity, hash, and reasons are required")


@dataclass(frozen=True, slots=True)
class Approval:
    approval_id: str
    organization_id: str
    tenant_id: str
    version: int
    decision_id: str
    decision_version: int
    evaluation_id: str
    requester: Actor
    approver: Actor
    scope: AuthorityScope
    issued_at: datetime
    effective_at: datetime
    expires_at: datetime | None
    state: ApprovalState
    lineage_refs: tuple[str, ...] = ()
    provenance_refs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "state", ApprovalState(self.state))
        _authority_times(self.issued_at, self.effective_at, self.expires_at)
        if not self.approval_id or self.version < 1:
            raise ValueError("approval identity and positive version are required")


@dataclass(frozen=True, slots=True)
class PolicyException:
    exception_id: str
    organization_id: str
    tenant_id: str
    version: int
    decision_id: str
    decision_version: int
    evaluation_id: str
    policy_id: str
    policy_version: int
    rule_id: str
    requester: Actor
    approver: Actor | None
    justification: str
    evidence_package_id: str
    scope: AuthorityScope
    issued_at: datetime
    effective_at: datetime
    expires_at: datetime
    state: ExceptionState
    lineage_refs: tuple[str, ...] = ()
    provenance_refs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "state", ExceptionState(self.state))
        _authority_times(self.issued_at, self.effective_at, self.expires_at)
        if not self.exception_id or self.version < 1:
            raise ValueError("exception identity and positive version are required")
        if not self.rule_id or not self.justification or not self.evidence_package_id:
            raise ValueError("exception rule, justification, and evidence are required")


@dataclass(frozen=True, slots=True)
class AuthorityEvent:
    authority_type: str
    authority_id: str
    version: int
    from_state: str | None
    to_state: str
    actor: Actor
    occurred_at: datetime
    reason: str

    def __post_init__(self) -> None:
        _aware(self.occurred_at, "event timestamp")
        if not self.reason:
            raise ValueError("history event reason is required")


@dataclass(frozen=True, slots=True)
class AuthorizationCheck:
    authorized: bool
    reason: str
    evaluation_result: PolicyEvaluationResult
    authority_type: str | None
    authority_id: str | None
    checked_at: datetime


def _aware(value: datetime, label: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{label} must be timezone-aware")


def _authority_times(
    issued_at: datetime,
    effective_at: datetime,
    expires_at: datetime | None,
) -> None:
    _aware(issued_at, "issued_at")
    _aware(effective_at, "effective_at")
    if expires_at is not None:
        _aware(expires_at, "expires_at")
        if expires_at <= effective_at:
            raise ValueError("authority expiry must follow effective time")
