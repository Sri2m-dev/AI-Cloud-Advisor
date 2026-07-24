"""Immutable Recommendation, Decision, actor, and history contracts."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from types import MappingProxyType
from typing import Any, Mapping


class ActorType(StrEnum):
    HUMAN = "human"
    AI = "ai"
    GOVERNED_SERVICE = "governed_service"


class RecommendationState(StrEnum):
    DRAFT = "draft"
    PROPOSED = "proposed"
    UNDER_REVIEW = "under_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    REVISION_REQUIRED = "revision_required"
    WITHDRAWN = "withdrawn"
    SUPERSEDED = "superseded"


class DecisionDisposition(StrEnum):
    APPROVE = "approve"
    REJECT = "reject"
    REQUEST_REVISION = "request_revision"


@dataclass(frozen=True, slots=True)
class Actor:
    actor_id: str
    actor_type: ActorType

    def __post_init__(self) -> None:
        object.__setattr__(self, "actor_type", ActorType(self.actor_type))
        if not self.actor_id:
            raise ValueError("actor_id is required")


@dataclass(frozen=True, slots=True)
class Alternative:
    alternative_id: str
    description: str
    expected_outcome: str
    risks: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.alternative_id or not self.description or not self.expected_outcome:
            raise ValueError("alternative identity, description, and outcome are required")


@dataclass(frozen=True, slots=True)
class Recommendation:
    recommendation_id: str
    organization_id: str
    tenant_id: str
    version: int
    finding: str
    proposed_action: str
    expected_outcome: str
    alternatives: tuple[Alternative, ...]
    evidence_package_id: str
    evidence_package_hash: str
    proposer: Actor
    state: RecommendationState
    created_at: datetime
    assumptions: tuple[str, ...] = ()
    risks: tuple[str, ...] = ()
    confidence: float | None = None
    lineage_refs: tuple[str, ...] = ()
    provenance_refs: tuple[str, ...] = ()
    supersedes_recommendation_id: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "state", RecommendationState(self.state))
        object.__setattr__(
            self, "alternatives", tuple(sorted(self.alternatives, key=lambda item: item.alternative_id))
        )
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))
        if self.version < 1:
            raise ValueError("recommendation version must be positive")
        if self.created_at.tzinfo is None:
            raise ValueError("created_at must be timezone-aware")
        required = (
            self.recommendation_id,
            self.organization_id,
            self.tenant_id,
            self.finding,
            self.proposed_action,
            self.expected_outcome,
            self.evidence_package_id,
            self.evidence_package_hash,
        )
        if any(not str(value).strip() for value in required):
            raise ValueError("recommendation required content is missing")
        if not self.alternatives:
            raise ValueError("recommendation requires explicit alternatives")
        if self.confidence is not None and not 0 <= self.confidence <= 1:
            raise ValueError("confidence must be between 0 and 1")

    @property
    def ai_proposed(self) -> bool:
        return self.proposer.actor_type is ActorType.AI


@dataclass(frozen=True, slots=True)
class Decision:
    decision_id: str
    organization_id: str
    tenant_id: str
    recommendation_id: str
    recommendation_version: int
    disposition: DecisionDisposition
    approver: Actor
    authority_result: str
    evidence_result: str
    rationale: str
    created_at: datetime
    correction_of_decision_id: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "disposition", DecisionDisposition(self.disposition))
        if self.created_at.tzinfo is None:
            raise ValueError("decision created_at must be timezone-aware")


@dataclass(frozen=True, slots=True)
class LifecycleEvent:
    recommendation_id: str
    version: int
    from_state: RecommendationState | None
    to_state: RecommendationState
    actor: Actor
    occurred_at: datetime
    reason: str
