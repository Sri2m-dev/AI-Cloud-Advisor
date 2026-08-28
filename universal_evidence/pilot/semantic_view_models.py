"""Bounded ACT-003 projections over PUE-002 discovery and PUE-003 governance."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class SemanticMappingStatus(str, Enum):
    OBSERVED = "OBSERVED"
    CANDIDATE = "CANDIDATE"
    CONFIRMATION_REQUIRED = "CONFIRMATION_REQUIRED"
    CONFIRMED = "CONFIRMED"
    REJECTED = "REJECTED"
    OVERRIDDEN = "OVERRIDDEN"
    BLOCKED = "BLOCKED"
    EXPIRED = "EXPIRED"


@dataclass(frozen=True, slots=True)
class SemanticCandidateViewModel:
    concept_id: str
    display_name: str
    confidence_percent: int
    confidence_band: str
    explanation: str
    risk: str


@dataclass(frozen=True, slots=True)
class SemanticDecisionViewModel:
    decision_id: str
    state: str
    concept_id: str
    actor_id: str
    actor_role: str
    reason: str | None
    timestamp: str


@dataclass(frozen=True, slots=True)
class SemanticMappingViewModel:
    column_reference: str
    source_column_name: str
    status: SemanticMappingStatus
    candidates: tuple[SemanticCandidateViewModel, ...]
    effective_concept_id: str | None
    effective_display_name: str | None
    status_reason: str
    ambiguous: bool
    stale: bool
    allowed_actions: tuple[str, ...]
    approved_override_concepts: tuple[tuple[str, str], ...]
    history: tuple[SemanticDecisionViewModel, ...]


@dataclass(frozen=True, slots=True)
class SemanticGovernanceViewModel:
    analysis_id: str
    discovery_fingerprint: str
    mappings: tuple[SemanticMappingViewModel, ...]
    candidate_count: int
    confirmation_required_count: int
    ambiguous_count: int
    effective_mapping_count: int
