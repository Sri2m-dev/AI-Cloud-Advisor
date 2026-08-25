"""Immutable, non-authoritative semantic discovery results."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from universal_evidence.contracts import (
    ClassificationState,
    ConfirmationState,
    EvidenceRowReference,
    MappingConfidence,
    SemanticConcept,
)
from universal_evidence.profiling import StructuralRole


class SemanticRisk(str, Enum):
    LOW_RISK = "LOW_RISK"
    MODERATE_RISK = "MODERATE_RISK"
    HIGH_RISK = "HIGH_RISK"
    RESTRICTED = "RESTRICTED"


@dataclass(frozen=True, slots=True)
class SemanticSignal:
    signal_type: str
    detail: str
    contribution: float


@dataclass(frozen=True, slots=True)
class ConceptDefinition:
    concept: SemanticConcept
    expected_roles: tuple[StructuralRole, ...]
    risk: SemanticRisk
    context_tokens: tuple[str, ...] = ()
    sample_shape: str | None = None


@dataclass(frozen=True, slots=True)
class SemanticDiscoveryProvenance:
    analysis_id: str
    source_id: str
    file_id: str
    sheet_id: str
    column_id: str
    structural_profile_fingerprint: str
    sample_row_references: tuple[EvidenceRowReference, ...]
    profiler_version: str
    classifier_version: str
    ontology_version: str
    policy_version: str


@dataclass(frozen=True, slots=True)
class DiscoveryCandidate:
    semantic_concept_id: str
    semantic_concept_version: int
    dimension: str
    confidence: MappingConfidence
    risk: SemanticRisk
    supporting_signals: tuple[SemanticSignal, ...]
    contradicting_signals: tuple[SemanticSignal, ...]
    explanation: str
    confirmation_requirement: ConfirmationState


@dataclass(frozen=True, slots=True)
class ColumnDiscoveryResult:
    discovery_id: str
    source_column_reference: str
    original_header: str
    candidates: tuple[DiscoveryCandidate, ...]
    classification_state: ClassificationState
    confirmation_state: ConfirmationState
    confirmation_reasons: tuple[str, ...]
    classifier_name: str
    classifier_version: str
    ontology_version: str
    policy_version: str
    classification_timestamp: datetime
    provenance: SemanticDiscoveryProvenance

    def __post_init__(self) -> None:
        forbidden = {
            ClassificationState.USER_CONFIRMED,
            ClassificationState.REJECTED,
            ClassificationState.OVERRIDDEN,
        }
        if self.classification_state in forbidden:
            raise ValueError(
                "autonomous discovery cannot emit governed confirmation states"
            )
        if self.confirmation_state not in {
            ConfirmationState.NOT_REQUIRED,
            ConfirmationState.REQUIRED,
        }:
            raise ValueError(
                "PUE-002 may only declare whether confirmation is required"
            )


@dataclass(frozen=True, slots=True)
class FileDiscoveryResult:
    file_id: str
    structural_profile_fingerprint: str
    semantic_fingerprint: str
    classifier_version: str
    ontology_version: str
    policy_version: str
    columns: tuple[ColumnDiscoveryResult, ...]
    dimension_candidate_counts: tuple[tuple[str, int], ...]
    unclassified_column_count: int


@dataclass(frozen=True, slots=True)
class DiscoveryConfig:
    header_weight: float = 0.60
    primitive_weight: float = 0.15
    role_weight: float = 0.12
    sample_weight: float = 0.05
    context_weight: float = 0.08
    contradiction_penalty: float = 0.35
    minimum_candidate_score: float = 0.40
    auto_classification_threshold: float = 0.90
    ambiguity_gap_threshold: float = 0.12
    high_band_threshold: float = 0.90
    medium_band_threshold: float = 0.70
    low_band_threshold: float = 0.40
    low_coverage_threshold: float = 0.50
    confirm_risks: tuple[SemanticRisk, ...] = (
        SemanticRisk.HIGH_RISK,
        SemanticRisk.RESTRICTED,
    )
    classifier_name: str = "pue_transparent_column_classifier"
    classifier_version: str = "pue-002.1"
    policy_version: str = "pue-semantic-policy-1"

    def __post_init__(self) -> None:
        weights = (
            self.header_weight,
            self.primitive_weight,
            self.role_weight,
            self.sample_weight,
            self.context_weight,
        )
        if any(value < 0 for value in weights) or abs(sum(weights) - 1.0) > 1e-9:
            raise ValueError(
                "semantic signal weights must be non-negative and sum to 1.0"
            )
