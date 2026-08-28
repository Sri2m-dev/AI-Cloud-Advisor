"""Non-analytical ACT-004 plan and quality presentation contracts."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ObservationQuality(str, Enum):
    VALID = "VALID"
    INVALID = "INVALID"
    MISSING = "MISSING"
    BLOCKED = "BLOCKED"
    UNSUPPORTED = "UNSUPPORTED"


@dataclass(frozen=True, slots=True)
class NormalizationPlanItem:
    column_reference: str
    source_column_name: str
    effective_concept_id: str | None
    proposed_type: str | None
    eligible: bool
    quality: ObservationQuality
    validation_rule: str
    reason: str


@dataclass(frozen=True, slots=True)
class NormalizationPlan:
    analysis_id: str
    evidence_fingerprint: str
    governance_fingerprint: str
    items: tuple[NormalizationPlanItem, ...]
    fingerprint: str


@dataclass(frozen=True, slots=True)
class NormalizationQualitySummary:
    valid: int
    invalid: int
    missing: int
    blocked: int
    unsupported: int


@dataclass(frozen=True, slots=True)
class GovernedNormalizationViewModel:
    plan: NormalizationPlan
    executed: bool
    observation_count: int
    quality: NormalizationQualitySummary
    normalization_run_ids: tuple[str, ...]
    total_cost_state: str
    total_cost_reason: str
    currency_partitions: tuple[str, ...]
    fingerprint: str
