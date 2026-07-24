"""Immutable WP-013 bounded execution, compensation, and outcome contracts."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from types import MappingProxyType
from typing import Any, Mapping

from policy_approval import AuthorityScope
from recommendation_decision import Actor


class ExecutionState(StrEnum):
    PLANNED = "planned"
    COMMAND_SUCCEEDED = "command_succeeded"
    COMMAND_FAILED = "command_failed"
    AWAITING_VERIFICATION = "awaiting_verification"
    OUTCOME_VERIFIED = "outcome_verified"
    OUTCOME_NOT_ACHIEVED = "outcome_not_achieved"
    COMPENSATED = "compensated"
    COMPENSATION_FAILED = "compensation_failed"


class OutcomeState(StrEnum):
    VERIFIED = "verified"
    NOT_VERIFIED = "not_verified"
    INDETERMINATE = "indeterminate"


@dataclass(frozen=True, slots=True)
class OutcomeCriterion:
    criterion_id: str
    metric: str
    operator: str
    target: float

    def __post_init__(self) -> None:
        if not self.criterion_id or not self.metric:
            raise ValueError("outcome criterion identity and metric are required")
        if self.operator not in {">=", "<=", "=="}:
            raise ValueError("unsupported deterministic outcome operator")


@dataclass(frozen=True, slots=True)
class OutcomePlan:
    baseline: Mapping[str, float]
    criteria: tuple[OutcomeCriterion, ...]
    required_evidence: tuple[str, ...]
    verification_window_ends_at: datetime

    def __post_init__(self) -> None:
        object.__setattr__(self, "baseline", MappingProxyType(dict(sorted(self.baseline.items()))))
        object.__setattr__(
            self,
            "criteria",
            tuple(sorted(self.criteria, key=lambda item: item.criterion_id)),
        )
        object.__setattr__(self, "required_evidence", tuple(sorted(set(self.required_evidence))))
        _aware(self.verification_window_ends_at, "verification window")
        if not self.criteria or not self.required_evidence:
            raise ValueError("outcome criteria and evidence requirements are mandatory")


@dataclass(frozen=True, slots=True)
class CompensationPlan:
    reason_triggers: tuple[str, ...]
    rollback_steps: tuple[str, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "reason_triggers", tuple(sorted(set(self.reason_triggers))))
        if not self.reason_triggers or not self.rollback_steps:
            raise ValueError("compensation triggers and rollback steps are mandatory")


@dataclass(frozen=True, slots=True)
class ExecutionPlan:
    plan_id: str
    organization_id: str
    tenant_id: str
    decision_id: str
    decision_version: int
    evaluation_id: str
    authority_type: str
    authority_id: str
    scope: AuthorityScope
    connector_id: str
    connector_action: str
    requested_by: Actor
    executor: Actor
    parameters: Mapping[str, Any]
    outcome_plan: OutcomePlan
    compensation_plan: CompensationPlan
    created_at: datetime
    plan_hash: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "parameters", MappingProxyType(dict(sorted(self.parameters.items())))
        )
        _aware(self.created_at, "plan creation")
        required = (
            self.plan_id,
            self.decision_id,
            self.evaluation_id,
            self.authority_type,
            self.authority_id,
            self.connector_id,
            self.connector_action,
            self.plan_hash,
        )
        if any(not value for value in required):
            raise ValueError("execution plan identity and authority binding are required")
        if self.authority_type not in {"approval", "exception"}:
            raise ValueError("execution requires explicit Approval or Exception authority")


@dataclass(frozen=True, slots=True)
class OutcomeObservation:
    metric: str
    value: float
    evidence_id: str
    evidence_hash: str
    source_connector_id: str
    observed_at: datetime
    lineage_ref: str | None = None
    provenance_ref: str | None = None

    def __post_init__(self) -> None:
        _aware(self.observed_at, "outcome observation")
        if not all(
            (
                self.metric,
                self.evidence_id,
                self.evidence_hash,
                self.source_connector_id,
            )
        ):
            raise ValueError("outcome observation requires governed connector evidence")


@dataclass(frozen=True, slots=True)
class ExecutionRecord:
    execution_id: str
    organization_id: str
    tenant_id: str
    plan_id: str
    plan_hash: str
    state: ExecutionState
    command_status: str
    adapter: str
    executor: Actor
    started_at: datetime
    finished_at: datetime
    result_details: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "state", ExecutionState(self.state))
        object.__setattr__(
            self,
            "result_details",
            MappingProxyType(dict(sorted(self.result_details.items()))),
        )
        _aware(self.started_at, "execution start")
        _aware(self.finished_at, "execution finish")
        if self.finished_at < self.started_at:
            raise ValueError("execution finish precedes start")


@dataclass(frozen=True, slots=True)
class OutcomeVerification:
    verification_id: str
    organization_id: str
    tenant_id: str
    execution_id: str
    verifier: Actor
    verified_at: datetime
    state: OutcomeState
    reasons: tuple[str, ...]
    observations: tuple[OutcomeObservation, ...]
    verification_hash: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "state", OutcomeState(self.state))
        object.__setattr__(self, "reasons", tuple(sorted(set(self.reasons))))
        object.__setattr__(
            self,
            "observations",
            tuple(
                sorted(
                    self.observations,
                    key=lambda item: (item.metric, item.evidence_id),
                )
            ),
        )
        _aware(self.verified_at, "outcome verification")
        if not self.reasons or not self.verification_hash:
            raise ValueError("outcome verification reasons and hash are required")


@dataclass(frozen=True, slots=True)
class ExecutionEvent:
    plan_id: str
    execution_id: str | None
    event_type: str
    actor: Actor
    occurred_at: datetime
    details: Mapping[str, Any]

    def __post_init__(self) -> None:
        object.__setattr__(self, "details", MappingProxyType(dict(sorted(self.details.items()))))
        _aware(self.occurred_at, "execution event")


def _aware(value: datetime, label: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{label} must be timezone-aware")
