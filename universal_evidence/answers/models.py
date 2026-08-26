"""Immutable PUE-009 governed analytical answer contracts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum

from universal_evidence.capability import CapabilityScope


class AnswerState(str, Enum):
    ANSWERED = "ANSWERED"
    PARTIAL = "PARTIAL"
    BLOCKED = "BLOCKED"
    UNSUPPORTED = "UNSUPPORTED"
    AMBIGUOUS = "AMBIGUOUS"
    FAILED = "FAILED"


class AnswerReason(str, Enum):
    GOVERNED_RESULT_RENDERED = "GOVERNED_RESULT_RENDERED"
    PARTIAL_RESULT_DISCLOSED = "PARTIAL_RESULT_DISCLOSED"
    CURRENCY_EVIDENCE_REQUIRED = "CURRENCY_EVIDENCE_REQUIRED"
    UPSTREAM_BLOCKED = "UPSTREAM_BLOCKED"
    QUESTION_UNSUPPORTED = "QUESTION_UNSUPPORTED"
    QUESTION_AMBIGUOUS = "QUESTION_AMBIGUOUS"
    UPSTREAM_FAILED = "UPSTREAM_FAILED"
    SCOPE_MISMATCH = "SCOPE_MISMATCH"
    PLAN_NOT_CURRENT = "PLAN_NOT_CURRENT"
    RESULT_NOT_CURRENT = "RESULT_NOT_CURRENT"
    RESULT_PLAN_MISMATCH = "RESULT_PLAN_MISMATCH"
    AUTHORIZATION_NOT_CURRENT = "AUTHORIZATION_NOT_CURRENT"
    RESULT_MISSING = "RESULT_MISSING"
    GROUPS_TRUNCATED = "GROUPS_TRUNCATED"


@dataclass(frozen=True, slots=True)
class AnswerScalar:
    value: Decimal | int
    unit: str | None


@dataclass(frozen=True, slots=True)
class AnswerGroup:
    dimension_values: tuple[tuple[str, object], ...]
    value: Decimal | int
    unit: str | None
    record_count: int
    source_group_id: str


@dataclass(frozen=True, slots=True)
class AnswerStructuredValues:
    scalar: AnswerScalar | None
    groups: tuple[AnswerGroup, ...]
    total_group_count: int
    displayed_group_count: int


@dataclass(frozen=True, slots=True)
class AnswerProvenance:
    interpretation_id: str
    interpretation_fingerprint: str
    analytical_plan_id: str | None
    analytical_plan_fingerprint: str | None
    aggregation_result_id: str | None
    aggregation_result_fingerprint: str | None
    capability_assessment_id: str | None
    capability_id: str | None
    execution_authorization_id: str | None
    normalization_run_ids: tuple[str, ...]
    source_row_fingerprints: tuple[str, ...]
    included_record_count: int | None
    composer_version: str
    policy_version: str


@dataclass(frozen=True, slots=True)
class GovernedAnalyticalAnswer:
    answer_id: str
    original_question: str
    scope: CapabilityScope
    answer_state: AnswerState
    primary_text: str
    structured_values: AnswerStructuredValues
    limitations: tuple[str, ...]
    reason_codes: tuple[AnswerReason, ...]
    provenance: AnswerProvenance
    composer_version: str
    policy_version: str
    fingerprint: str
    composed_at: datetime
