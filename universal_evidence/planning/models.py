"""Immutable PUE-007 structured analytical planning contracts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from universal_evidence.aggregation.models import (
    AggregationFilter,
    AggregationRequest,
    FilterOperator,
    TimeBucket,
)
from universal_evidence.capability import AuthorizedOperation, CapabilityScope


class AnalyticalIntentType(str, Enum):
    COUNT_RECORDS = "COUNT_RECORDS"
    TOTAL_MEASURE = "TOTAL_MEASURE"
    GROUP_MEASURE_BY_DIMENSION = "GROUP_MEASURE_BY_DIMENSION"
    TIME_SERIES_MEASURE = "TIME_SERIES_MEASURE"


class PlanningStatus(str, Enum):
    READY = "READY"
    REJECTED = "REJECTED"
    AMBIGUOUS = "AMBIGUOUS"
    BLOCKED = "BLOCKED"
    STALE = "STALE"


class PlanningReason(str, Enum):
    INTENT_VALID = "INTENT_VALID"
    INTENT_UNSUPPORTED = "INTENT_UNSUPPORTED"
    MEASURE_NOT_GOVERNED = "MEASURE_NOT_GOVERNED"
    DIMENSION_NOT_GOVERNED = "DIMENSION_NOT_GOVERNED"
    TIME_DIMENSION_NOT_GOVERNED = "TIME_DIMENSION_NOT_GOVERNED"
    CAPABILITY_NOT_FOUND = "CAPABILITY_NOT_FOUND"
    CAPABILITY_BLOCKED = "CAPABILITY_BLOCKED"
    CAPABILITY_STALE = "CAPABILITY_STALE"
    AUTHORIZATION_NOT_FOUND = "AUTHORIZATION_NOT_FOUND"
    AUTHORIZATION_STALE = "AUTHORIZATION_STALE"
    OPERATION_NOT_AUTHORIZED = "OPERATION_NOT_AUTHORIZED"
    ALIGNMENT_NOT_AUTHORIZED = "ALIGNMENT_NOT_AUTHORIZED"
    TIME_BUCKET_NOT_AUTHORIZED = "TIME_BUCKET_NOT_AUTHORIZED"
    FILTER_NOT_AUTHORIZED = "FILTER_NOT_AUTHORIZED"
    FILTER_OPERATOR_NOT_ALLOWED = "FILTER_OPERATOR_NOT_ALLOWED"
    FILTER_VALUE_TYPE_MISMATCH = "FILTER_VALUE_TYPE_MISMATCH"
    FILTER_LIST_MEMBER_TYPE_MISMATCH = "FILTER_LIST_MEMBER_TYPE_MISMATCH"
    SCOPE_MISMATCH = "SCOPE_MISMATCH"
    AMBIGUOUS_MEASURE = "AMBIGUOUS_MEASURE"
    AMBIGUOUS_DIMENSION = "AMBIGUOUS_DIMENSION"
    PLAN_READY = "PLAN_READY"


@dataclass(frozen=True, slots=True)
class IntentFilter:
    dimension_concept_id: str
    operator: FilterOperator
    value: object


@dataclass(frozen=True, slots=True)
class AnalyticalIntent:
    intent_id: str
    scope: CapabilityScope
    intent_type: AnalyticalIntentType
    measure_concept_id: str | None
    dimension_concept_ids: tuple[str, ...]
    time_dimension_concept_id: str | None
    filters: tuple[IntentFilter, ...]
    time_bucket: TimeBucket | None
    requested_currency_behavior: str | None
    caller_id: str | None
    caller_type: str | None
    capability_assessment_id: str | None
    execution_authorization_id: str | None
    intent_version: str
    created_at: datetime


@dataclass(frozen=True, slots=True)
class AnalyticalPlanProvenance:
    capability_assessment_id: str | None
    capability_id: str | None
    execution_authorization_id: str | None
    measure_id: str | None
    dimension_ids: tuple[str, ...]
    time_dimension_id: str | None
    alignment_id: str | None
    record_basis_id: str | None
    normalization_run_ids: tuple[str, ...]
    coverage_ids: tuple[str, ...]
    capability_policy_version: str | None
    execution_authorization_policy_version: str | None


@dataclass(frozen=True, slots=True)
class AnalyticalPlan:
    plan_id: str
    intent_id: str
    scope: CapabilityScope
    intent_type: AnalyticalIntentType | None
    capability_assessment_id: str | None
    capability_id: str | None
    execution_authorization_id: str | None
    operation: AuthorizedOperation | None
    measure_id: str | None
    dimension_ids: tuple[str, ...]
    time_dimension_id: str | None
    filters: tuple[AggregationFilter, ...]
    time_bucket: TimeBucket | None
    currency_requirement: str | None
    unit_requirement: str | None
    alignment_id: str | None
    record_basis_id: str | None
    normalization_run_ids: tuple[str, ...]
    planning_status: PlanningStatus
    reason_codes: tuple[PlanningReason, ...]
    provenance: AnalyticalPlanProvenance
    planning_policy_version: str
    plan_fingerprint: str
    planned_at: datetime


@dataclass(frozen=True, slots=True)
class PlanningResult:
    plan: AnalyticalPlan
    aggregation_request: AggregationRequest | None
