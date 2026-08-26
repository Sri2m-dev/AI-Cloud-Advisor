"""Immutable PUE-008 natural-language interpretation contracts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from universal_evidence.capability import CapabilityScope, DimensionValueType
from universal_evidence.planning import AnalyticalIntent, AnalyticalIntentType


class InterpretationStatus(str, Enum):
    INTERPRETED = "INTERPRETED"
    AMBIGUOUS = "AMBIGUOUS"
    UNSUPPORTED = "UNSUPPORTED"
    INSUFFICIENT_CONTEXT = "INSUFFICIENT_CONTEXT"
    REJECTED = "REJECTED"


class ConfidenceBand(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    INSUFFICIENT = "INSUFFICIENT"


class InterpretationReason(str, Enum):
    QUESTION_INTERPRETED = "QUESTION_INTERPRETED"
    QUESTION_AMBIGUOUS = "QUESTION_AMBIGUOUS"
    QUESTION_UNSUPPORTED = "QUESTION_UNSUPPORTED"
    QUESTION_EMPTY = "QUESTION_EMPTY"
    QUESTION_TOO_LONG = "QUESTION_TOO_LONG"
    QUESTION_UNSAFE = "QUESTION_UNSAFE"
    MEASURE_TERM_MATCHED = "MEASURE_TERM_MATCHED"
    DIMENSION_TERM_MATCHED = "DIMENSION_TERM_MATCHED"
    TIME_TERM_MATCHED = "TIME_TERM_MATCHED"
    FILTER_TERM_MATCHED = "FILTER_TERM_MATCHED"
    FILTER_VALUE_TYPED = "FILTER_VALUE_TYPED"
    FILTER_VALUE_INVALID = "FILTER_VALUE_INVALID"
    MULTIPLE_MEASURES_PLAUSIBLE = "MULTIPLE_MEASURES_PLAUSIBLE"
    MULTIPLE_DIMENSIONS_PLAUSIBLE = "MULTIPLE_DIMENSIONS_PLAUSIBLE"
    UNSUPPORTED_OPERATION = "UNSUPPORTED_OPERATION"
    UNSUPPORTED_INTENT_SHAPE = "UNSUPPORTED_INTENT_SHAPE"
    GOVERNED_CONCEPT_NOT_AVAILABLE = "GOVERNED_CONCEPT_NOT_AVAILABLE"
    NO_SUPPORTED_INTENT_PATTERN = "NO_SUPPORTED_INTENT_PATTERN"


@dataclass(frozen=True, slots=True)
class NaturalLanguageQuestion:
    question_id: str
    question: str
    scope: CapabilityScope
    caller_id: str | None
    caller_type: str | None
    question_version: str
    created_at: datetime


@dataclass(frozen=True, slots=True)
class CatalogMeasure:
    measure_id: str
    semantic_concept_id: str


@dataclass(frozen=True, slots=True)
class CatalogDimension:
    dimension_id: str
    semantic_concept_id: str
    normalized_value_type: DimensionValueType
    allowed_filter_operators: tuple[str, ...]
    filterable: bool
    is_time_dimension: bool


@dataclass(frozen=True, slots=True)
class AnalyticalConceptCatalog:
    scope: CapabilityScope
    capability_assessment_id: str
    measures: tuple[CatalogMeasure, ...]
    dimensions: tuple[CatalogDimension, ...]
    catalog_version: str
    source_assessment_fingerprint: str
    fingerprint: str


@dataclass(frozen=True, slots=True)
class IntentCandidate:
    intent_type: AnalyticalIntentType
    measure_concept_id: str | None
    dimension_concept_ids: tuple[str, ...]
    time_dimension_concept_id: str | None
    time_bucket: str | None
    score: float
    supporting_signals: tuple[str, ...]
    contradicting_signals: tuple[str, ...]
    fingerprint: str


@dataclass(frozen=True, slots=True)
class InterpretationProvenance:
    question_id: str
    capability_assessment_id: str
    catalog_fingerprint: str
    scope: CapabilityScope
    interpreter_name: str
    interpreter_version: str
    alias_registry_version: str
    pattern_registry_version: str
    literal_policy_version: str
    interpretation_policy_version: str


@dataclass(frozen=True, slots=True)
class NaturalLanguageInterpretationResult:
    interpretation_id: str
    original_question: str
    canonical_question: str
    scope: CapabilityScope
    status: InterpretationStatus
    primary_intent: AnalyticalIntent | None
    candidates: tuple[IntentCandidate, ...]
    confidence_score: float
    confidence_band: ConfidenceBand
    reason_codes: tuple[InterpretationReason, ...]
    explanation: tuple[str, ...]
    provenance: InterpretationProvenance
    fingerprint: str
    interpreted_at: datetime
