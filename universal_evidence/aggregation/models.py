"""Immutable PUE-006 governed aggregation contracts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum

from universal_evidence.capability import AuthorizedOperation, CapabilityScope


class FilterOperator(str, Enum):
    EQUALS = "EQUALS"
    NOT_EQUALS = "NOT_EQUALS"
    IN = "IN"
    DATE_FROM = "DATE_FROM"
    DATE_TO = "DATE_TO"


class TimeBucket(str, Enum):
    DAY = "DAY"
    MONTH = "MONTH"
    QUARTER = "QUARTER"
    YEAR = "YEAR"


class AggregationResultStatus(str, Enum):
    COMPLETED = "COMPLETED"
    PARTIAL = "PARTIAL"
    BLOCKED = "BLOCKED"
    REJECTED = "REJECTED"


class AggregationWarning(str, Enum):
    UPSTREAM_CAPABILITY_NOT_SUPPORTED = "UPSTREAM_CAPABILITY_NOT_SUPPORTED"
    STALE_CAPABILITY = "STALE_CAPABILITY"
    AUTHORIZATION_MISMATCH = "AUTHORIZATION_MISMATCH"
    SCOPE_MISMATCH = "SCOPE_MISMATCH"
    NORMALIZATION_RUN_MISMATCH = "NORMALIZATION_RUN_MISMATCH"
    UNSUPPORTED_OPERATION = "UNSUPPORTED_OPERATION"
    UNSUPPORTED_FILTER = "UNSUPPORTED_FILTER"
    MEASURE_MISMATCH = "MEASURE_MISMATCH"
    DIMENSION_MISMATCH = "DIMENSION_MISMATCH"
    TIME_DIMENSION_MISMATCH = "TIME_DIMENSION_MISMATCH"
    TIME_BUCKET_NOT_AUTHORIZED = "TIME_BUCKET_NOT_AUTHORIZED"
    ALIGNMENT_MISMATCH = "ALIGNMENT_MISMATCH"
    CURRENCY_CONFLICT = "CURRENCY_CONFLICT"
    INVALID_RECORDS_EXCLUDED = "INVALID_RECORDS_EXCLUDED"
    NULL_RECORDS_EXCLUDED = "NULL_RECORDS_EXCLUDED"
    PARTIAL_RECORDS_EXCLUDED = "PARTIAL_RECORDS_EXCLUDED"


@dataclass(frozen=True, slots=True)
class AggregationFilter:
    dimension_id: str
    operator: FilterOperator
    value: object


@dataclass(frozen=True, slots=True)
class AggregationRequest:
    request_id: str
    scope: CapabilityScope
    capability_assessment_id: str
    authorization_id: str
    operation: AuthorizedOperation
    measure_id: str | None
    dimension_ids: tuple[str, ...]
    time_dimension_id: str | None
    filters: tuple[AggregationFilter, ...]
    time_bucket: TimeBucket | None
    execution_policy_version: str
    requested_at: datetime


@dataclass(frozen=True, slots=True)
class GovernedAggregationPlan:
    plan_id: str
    request_id: str
    scope: CapabilityScope
    capability_assessment_id: str
    capability_id: str
    authorization_id: str
    operation: AuthorizedOperation
    measure_id: str | None
    dimension_ids: tuple[str, ...]
    time_dimension_id: str | None
    filters: tuple[AggregationFilter, ...]
    time_bucket: TimeBucket | None
    normalization_run_ids: tuple[str, ...]
    alignment_id: str | None
    record_basis_id: str | None
    currency_requirement: str | None
    unit_requirement: str | None
    capability_policy_version: str
    execution_policy_version: str
    plan_fingerprint: str


@dataclass(frozen=True, slots=True)
class AggregationExecutionStatistics:
    eligible_records: int
    included_records: int
    excluded_null_records: int
    excluded_invalid_records: int
    excluded_partial_records: int
    excluded_unsupported_records: int
    excluded_filter_records: int


@dataclass(frozen=True, slots=True)
class AggregationProvenance:
    capability_assessment_id: str
    capability_id: str
    authorization_id: str
    measure_id: str | None
    dimension_ids: tuple[str, ...]
    alignment_id: str | None
    record_basis_id: str | None
    normalization_run_ids: tuple[str, ...]
    normalized_field_ids: tuple[str, ...]
    normalized_fingerprints: tuple[str, ...]
    mapping_decision_ids: tuple[str, ...]
    source_row_fingerprints: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class AggregationGroup:
    group_id: str
    dimension_values: tuple[tuple[str, object], ...]
    value: Decimal | int
    unit: str | None
    record_count: int
    normalized_field_ids: tuple[str, ...]
    fingerprint: str


@dataclass(frozen=True, slots=True)
class GovernedAggregationResult:
    result_id: str
    request_id: str
    plan_id: str | None
    scope: CapabilityScope
    operation: AuthorizedOperation | None
    status: AggregationResultStatus
    measure_id: str | None
    dimension_ids: tuple[str, ...]
    currency_or_unit: str | None
    scalar_value: Decimal | int | None
    groups: tuple[AggregationGroup, ...]
    statistics: AggregationExecutionStatistics
    warnings: tuple[AggregationWarning, ...]
    provenance: AggregationProvenance | None
    capability_policy_version: str | None
    execution_policy_version: str
    result_fingerprint: str
    executed_at: datetime
