"""Immutable PUE-003 decision, history, scope, and audit contracts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from universal_evidence.contracts import ConfirmationState


class ActorType(str, Enum):
    HUMAN = "HUMAN"
    POLICY_ENGINE = "POLICY_ENGINE"
    SYSTEM = "SYSTEM"


class MappingDecisionState(str, Enum):
    UNDECIDED = "UNDECIDED"
    AUTO_ACCEPTED = "AUTO_ACCEPTED"
    CONFIRMED = "CONFIRMED"
    REJECTED = "REJECTED"
    OVERRIDDEN = "OVERRIDDEN"
    SUPERSEDED = "SUPERSEDED"
    EXPIRED = "EXPIRED"


@dataclass(frozen=True, slots=True)
class DecisionScope:
    analysis_id: str
    prospect_id: str
    organization_id: str | None
    tenant_id: str | None
    source_id: str
    file_id: str
    sheet_id: str
    column_id: str

    @property
    def key(self) -> tuple[str | None, ...]:
        return (
            self.analysis_id,
            self.prospect_id,
            self.organization_id,
            self.tenant_id,
            self.source_id,
            self.file_id,
            self.sheet_id,
            self.column_id,
        )


@dataclass(frozen=True, slots=True)
class ConfirmationActor:
    actor_id: str
    principal: str
    actor_role: str
    actor_type: ActorType


@dataclass(frozen=True, slots=True)
class ConfirmationRequirement:
    state: ConfirmationState
    reasons: tuple[str, ...]
    policy_version: str


@dataclass(frozen=True, slots=True)
class ConfirmationRequest:
    request_id: str
    request_fingerprint: str
    discovery_id: str
    scope: DecisionScope
    semantic_concept_id: str
    confirmation_state: ConfirmationState
    created_by: ConfirmationActor
    created_at: datetime
    classifier_version: str
    ontology_version: str
    policy_version: str


@dataclass(frozen=True, slots=True)
class GovernanceDecisionProvenance:
    discovery_id: str
    semantic_fingerprint: str
    structural_profile_fingerprint: str
    classifier_version: str
    ontology_version: str
    discovery_policy_version: str
    governance_policy_version: str


@dataclass(frozen=True, slots=True)
class MappingDecision:
    decision_id: str
    decision_fingerprint: str
    scope: DecisionScope
    semantic_concept_id: str
    decision_state: MappingDecisionState
    confirmation_state: ConfirmationState
    actor: ConfirmationActor
    decision_timestamp: datetime
    reason: str | None
    original_candidate_ranking: tuple[tuple[str, float], ...]
    provenance: GovernanceDecisionProvenance
    supersedes_decision_id: str | None = None
    effective_from: datetime | None = None
    effective_to: datetime | None = None


@dataclass(frozen=True, slots=True)
class MappingDecisionHistory:
    scope: DecisionScope
    decisions: tuple[MappingDecision, ...]


@dataclass(frozen=True, slots=True)
class EffectiveSemanticMapping:
    scope: DecisionScope
    semantic_concept_id: str
    decision_state: MappingDecisionState
    decision_id: str
    confidence: float | None
    actor: ConfirmationActor
    provenance: GovernanceDecisionProvenance


@dataclass(frozen=True, slots=True)
class DriftResult:
    discovery_changed: bool
    classifier_changed: bool
    ontology_changed: bool
    policy_changed: bool

    @property
    def requires_reevaluation(self) -> bool:
        return any(
            (
                self.discovery_changed,
                self.classifier_changed,
                self.ontology_changed,
                self.policy_changed,
            )
        )


@dataclass(frozen=True, slots=True)
class AuditEvent:
    event_type: str
    decision_id: str | None
    request_id: str | None
    scope: DecisionScope
    semantic_concept_id: str
    actor: ConfirmationActor
    timestamp: datetime
    previous_decision_id: str | None
    reason: str | None
    classifier_version: str
    ontology_version: str
    policy_version: str
