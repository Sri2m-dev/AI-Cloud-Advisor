"""Layer 2 semantic interpretation contracts; no classifier is implemented here."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from universal_evidence.contracts.enums import (
    ClassificationState,
    ConfidenceBand,
    ConfirmationState,
    EvidenceDimension,
    MappingAuthority,
)
from universal_evidence.contracts.scope import EvidenceAnalysisContext


@dataclass(frozen=True, slots=True)
class SemanticConcept:
    concept_id: str
    version: int
    dimension: EvidenceDimension
    definition: str
    expected_primitive_types: tuple[str, ...]
    allowed_units: tuple[str, ...] = ()
    cardinality_expectation: str | None = None
    aliases: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class MappingConfidence:
    score: float
    band: ConfidenceBand
    method: str
    evidence_inputs: tuple[str, ...]
    classifier_version: str
    threshold_policy: str
    decided_at: datetime

    def __post_init__(self) -> None:
        if not 0.0 <= float(self.score) <= 1.0:
            raise ValueError("confidence score must be between 0.0 and 1.0")


@dataclass(frozen=True, slots=True)
class SemanticCandidate:
    semantic_concept_id: str
    semantic_concept_version: int
    confidence: MappingConfidence
    reasons: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ConfirmationRecord:
    state: ConfirmationState
    actor_id: str | None = None
    actor_role: str | None = None
    confirmed_at: datetime | None = None
    reason: str | None = None
    previous_mapping_id: str | None = None
    new_mapping_id: str | None = None
    audit_reference: str | None = None

    def __post_init__(self) -> None:
        if self.state in {ConfirmationState.CONFIRMED, ConfirmationState.OVERRIDDEN}:
            if not self.actor_id or not self.confirmed_at:
                raise ValueError("confirmed and overridden states require actor and timestamp")


@dataclass(frozen=True, slots=True)
class SemanticClassificationResult:
    classification_id: str
    context: EvidenceAnalysisContext
    source_column_id: str
    candidates: tuple[SemanticCandidate, ...]
    state: ClassificationState
    confirmation: ConfirmationRecord
    classified_at: datetime

    def __post_init__(self) -> None:
        if self.state is ClassificationState.USER_CONFIRMED:
            if self.confirmation.state is not ConfirmationState.CONFIRMED:
                raise ValueError("USER_CONFIRMED requires confirmed provenance")
        if self.state is ClassificationState.CONFIRMATION_REQUIRED and not self.candidates:
            raise ValueError("confirmation requires at least one candidate")


@dataclass(frozen=True, slots=True)
class SemanticMapping:
    mapping_id: str
    mapping_version: int
    context: EvidenceAnalysisContext
    source_column_id: str
    semantic_concept_id: str
    semantic_concept_version: int
    confidence: MappingConfidence
    confirmation: ConfirmationRecord
    authority: MappingAuthority
    effective_at: datetime

    def __post_init__(self) -> None:
        if self.authority is MappingAuthority.USER_CONFIRMED:
            if self.confirmation.state is not ConfirmationState.CONFIRMED:
                raise ValueError("user-confirmed authority requires confirmation provenance")
