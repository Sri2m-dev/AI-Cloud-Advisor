"""PUE-006 deterministic execution of current certified authorizations."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable
from datetime import date, datetime, timezone
from decimal import Decimal, localcontext

from universal_evidence.aggregation.fingerprint import fingerprint
from universal_evidence.aggregation.models import (
    AggregationExecutionStatistics,
    AggregationGroup,
    AggregationProvenance,
    AggregationRequest,
    AggregationResultStatus,
    AggregationWarning,
    FilterOperator,
    GovernedAggregationResult,
    TimeBucket,
)
from universal_evidence.aggregation.planner import AggregationPlanner, PlanRejection
from universal_evidence.aggregation.policy import AggregationExecutionPolicy
from universal_evidence.aggregation.repository import InMemoryAggregationRepository
from universal_evidence.capability import (
    AuthorizedOperation,
    CapabilityAssessment,
    InMemoryCapabilityRepository,
)
from universal_evidence.normalization import NormalizationRun, NormalizationStatus

VALID = {NormalizationStatus.NORMALIZED, NormalizationStatus.UNCHANGED}


def _row_key(record) -> tuple[object, ...]:
    reference = record.row_reference
    return (
        record.analysis_id,
        record.prospect_id,
        record.organization_id,
        record.tenant_id,
        record.source_id,
        record.file_id,
        record.sheet_id,
        reference.row_numbers,
        reference.row_range,
        reference.lineage_expression,
    )


def _row_fingerprint(record) -> str:
    return fingerprint("SOURCE_ROW", _row_key(record))


class AggregationExecutor:
    def __init__(
        self,
        *,
        capability_repository: InMemoryCapabilityRepository,
        repository: InMemoryAggregationRepository | None = None,
        policy: AggregationExecutionPolicy | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.capability_repository = capability_repository
        self.repository = repository or InMemoryAggregationRepository()
        self.policy = policy or AggregationExecutionPolicy()
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.planner = AggregationPlanner(capability_repository, self.policy)

    def execute(
        self,
        request: AggregationRequest,
        assessment: CapabilityAssessment,
        runs: tuple[NormalizationRun, ...],
    ) -> GovernedAggregationResult:
        try:
            plan = self.planner.plan(request, assessment, runs)
        except PlanRejection as rejection:
            status = (
                AggregationResultStatus.BLOCKED
                if rejection.warning
                is AggregationWarning.UPSTREAM_CAPABILITY_NOT_SUPPORTED
                else AggregationResultStatus.REJECTED
            )
            return self._governance_result(request, status, rejection.warning)
        records = tuple(record for run in runs for record in run.records)
        if plan.operation is AuthorizedOperation.COUNT:
            return self._execute_count(request, plan, assessment, records)
        return self._execute_measure(request, plan, assessment, records)

    def _execute_count(self, request, plan, assessment, records):
        basis = assessment.record_count_basis
        if basis.record_basis_id != plan.record_basis_id:
            return self._governance_result(
                request,
                AggregationResultStatus.REJECTED,
                AggregationWarning.AUTHORIZATION_MISMATCH,
            )
        row_ids = tuple(sorted({_row_fingerprint(record) for record in records}))
        if len(row_ids) != basis.distinct_source_row_count:
            return self._governance_result(
                request,
                AggregationResultStatus.REJECTED,
                AggregationWarning.NORMALIZATION_RUN_MISMATCH,
            )
        statistics = AggregationExecutionStatistics(len(row_ids), len(row_ids), 0, 0, 0, 0, 0)
        provenance = self._provenance(plan, records, row_ids)
        return self._completed_result(
            request, plan, int(len(row_ids)), (), None, statistics, (), provenance
        )

    def _execute_measure(self, request, plan, assessment, records):
        measure = next(item for item in assessment.measures if item.measure_id == plan.measure_id)
        measure_records = tuple(
            record
            for record in records
            if record.semantic_concept_id == measure.semantic_concept_id
        )
        valid_records = tuple(
            record for record in measure_records if record.normalization_status in VALID
        )
        nulls = sum(
            record.normalization_status is NormalizationStatus.SKIPPED
            for record in measure_records
        )
        invalid = sum(
            record.normalization_status is NormalizationStatus.INVALID
            for record in measure_records
        )
        partial = sum(
            record.normalization_status is NormalizationStatus.PARTIAL
            for record in measure_records
        )
        unsupported = sum(
            record.normalization_status is NormalizationStatus.UNSUPPORTED
            for record in measure_records
        )
        dimension_maps = self._dimension_maps(assessment, records)
        filtered = tuple(
            record
            for record in valid_records
            if self._passes_filters(record, request.filters, dimension_maps)
        )
        excluded_filter = len(valid_records) - len(filtered)
        currency_map = self._concept_map(records, "financial.currency")
        included_currencies = {
            currency_map[_row_key(record)]
            for record in filtered
            if _row_key(record) in currency_map
        }
        warnings = []
        if invalid:
            warnings.append(AggregationWarning.INVALID_RECORDS_EXCLUDED)
        if nulls:
            warnings.append(AggregationWarning.NULL_RECORDS_EXCLUDED)
        if partial or unsupported:
            warnings.append(AggregationWarning.PARTIAL_RECORDS_EXCLUDED)
        if plan.operation in {AuthorizedOperation.SUM, AuthorizedOperation.GROUPED_SUM}:
            certified_currencies = set(measure.detected_currencies)
            currency_grouped = any(
                dimension.semantic_concept_id == "financial.currency"
                for dimension in assessment.dimensions
                if dimension.dimension_id in plan.dimension_ids
            )
            if (
                not included_currencies
                or not included_currencies <= certified_currencies
                or (not currency_grouped and len(certified_currencies) != 1)
            ):
                return self._governance_result(
                    request,
                    AggregationResultStatus.REJECTED,
                    AggregationWarning.CURRENCY_CONFLICT,
                )
        statistics = AggregationExecutionStatistics(
            len(measure_records),
            len(filtered),
            nulls,
            invalid,
            partial,
            unsupported,
            excluded_filter,
        )
        row_ids = tuple(sorted(_row_fingerprint(record) for record in filtered))
        provenance = self._provenance(plan, filtered, row_ids)
        if plan.operation is AuthorizedOperation.SUM:
            value = self._sum(filtered)
            unit = measure.detected_currencies[0]
            return self._completed_result(
                request, plan, value, (), unit, statistics, tuple(warnings), provenance
            )
        groups = self._grouped(plan, assessment, filtered, dimension_maps, currency_map)
        return self._completed_result(
            request, plan, None, groups, None, statistics, tuple(warnings), provenance
        )

    def _grouped(self, plan, assessment, records, dimension_maps, currency_map):
        dimension_ids = plan.dimension_ids
        if plan.time_dimension_id:
            dimension_ids = (plan.time_dimension_id,)
        dimension_by_id = {item.dimension_id: item for item in assessment.dimensions}
        grouped = defaultdict(list)
        for record in records:
            row = _row_key(record)
            values = []
            for dimension_id in dimension_ids:
                concept = dimension_by_id[dimension_id].semantic_concept_id
                value = dimension_maps[dimension_id].get(row)
                if plan.time_dimension_id:
                    value = self._bucket(value, plan.time_bucket)
                values.append((concept, value))
            if any(value is None for _, value in values):
                continue
            grouped[tuple(values)].append(record)
        results = []
        for values in sorted(grouped, key=repr):
            rows = tuple(grouped[values])
            currencies = {currency_map.get(_row_key(record)) for record in rows}
            currencies.discard(None)
            unit = next(iter(currencies)) if len(currencies) == 1 else None
            value = self._sum(rows)
            identity = fingerprint(
                plan.plan_fingerprint,
                values,
                value,
                unit,
                tuple(record.fingerprint for record in rows),
            )
            results.append(
                AggregationGroup(
                    "aggregation-group-" + identity[:24],
                    values,
                    value,
                    unit,
                    len(rows),
                    tuple(record.normalized_field_id for record in rows),
                    identity,
                )
            )
        return tuple(results)

    def _sum(self, records):
        with localcontext() as context:
            context.prec = self.policy.decimal_precision
            value = sum((Decimal(record.normalized_value) for record in records), Decimal(0))
        if self.policy.output_scale is not None:
            quantum = Decimal(1).scaleb(-self.policy.output_scale)
            value = value.quantize(quantum, rounding=self.policy.rounding_mode)
        return value

    @staticmethod
    def _concept_map(records, concept_id):
        return {
            _row_key(record): record.normalized_value
            for record in records
            if record.semantic_concept_id == concept_id
            and record.normalization_status in VALID
        }

    def _dimension_maps(self, assessment, records):
        return {
            dimension.dimension_id: self._concept_map(records, dimension.semantic_concept_id)
            for dimension in assessment.dimensions
        }

    @staticmethod
    def _passes_filters(record, filters, maps):
        row = _row_key(record)
        for item in filters:
            actual = maps[item.dimension_id].get(row)
            if item.operator is FilterOperator.EQUALS and actual != item.value:
                return False
            if item.operator is FilterOperator.NOT_EQUALS and actual == item.value:
                return False
            if item.operator is FilterOperator.IN and actual not in tuple(item.value):
                return False
            if item.operator is FilterOperator.DATE_FROM and (
                actual is None or actual < item.value
            ):
                return False
            if item.operator is FilterOperator.DATE_TO and (
                actual is None or actual > item.value
            ):
                return False
        return True

    @staticmethod
    def _bucket(value, bucket):
        if not isinstance(value, (date, datetime)):
            return None
        if bucket is TimeBucket.DAY:
            return value.date() if isinstance(value, datetime) else value
        if bucket is TimeBucket.MONTH:
            return f"{value.year:04d}-{value.month:02d}"
        if bucket is TimeBucket.QUARTER:
            return f"{value.year:04d}-Q{((value.month - 1) // 3) + 1}"
        if bucket is TimeBucket.YEAR:
            return str(value.year)
        return None

    def _provenance(self, plan, records, row_ids):
        limit = self.policy.max_materialized_provenance_references
        return AggregationProvenance(
            plan.capability_assessment_id,
            plan.capability_id,
            plan.authorization_id,
            plan.measure_id,
            plan.dimension_ids or ((plan.time_dimension_id,) if plan.time_dimension_id else ()),
            plan.alignment_id,
            plan.record_basis_id,
            plan.normalization_run_ids,
            tuple(record.normalized_field_id for record in records[:limit]),
            tuple(record.fingerprint for record in records[:limit]),
            tuple(sorted({record.mapping_decision_id for record in records})),
            tuple(row_ids[:limit]),
        )

    def _completed_result(
        self, request, plan, scalar, groups, unit, statistics, warnings, provenance
    ):
        status = (
            AggregationResultStatus.PARTIAL
            if warnings
            else AggregationResultStatus.COMPLETED
        )
        result_fingerprint = fingerprint(
            request.scope,
            request.request_id,
            plan.plan_fingerprint,
            scalar,
            tuple(group.fingerprint for group in groups),
            unit,
            statistics,
            warnings,
            provenance,
            self.policy.version,
        )
        result = GovernedAggregationResult(
            "aggregation-result-" + result_fingerprint[:24],
            request.request_id,
            plan.plan_id,
            request.scope,
            plan.operation,
            status,
            plan.measure_id,
            plan.dimension_ids or ((plan.time_dimension_id,) if plan.time_dimension_id else ()),
            unit,
            scalar,
            groups,
            statistics,
            warnings,
            provenance,
            plan.capability_policy_version,
            self.policy.version,
            result_fingerprint,
            self.clock(),
        )
        return self.repository.store(result)

    def _governance_result(self, request, status, warning):
        statistics = AggregationExecutionStatistics(0, 0, 0, 0, 0, 0, 0)
        result_fingerprint = fingerprint(
            request.scope,
            request.request_id,
            request.capability_assessment_id,
            request.authorization_id,
            request.operation,
            status,
            warning,
            self.policy.version,
        )
        result = GovernedAggregationResult(
            "aggregation-result-" + result_fingerprint[:24],
            request.request_id,
            None,
            request.scope,
            request.operation if isinstance(request.operation, AuthorizedOperation) else None,
            status,
            request.measure_id,
            request.dimension_ids,
            None,
            None,
            (),
            statistics,
            (warning,),
            None,
            None,
            self.policy.version,
            result_fingerprint,
            self.clock(),
        )
        return self.repository.store(result)
