"""PUE-007 authorization-bound structured analytical planning."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date, datetime, timezone
from decimal import Decimal

from universal_evidence.aggregation.models import (
    AggregationFilter,
    AggregationRequest,
    FilterOperator,
)
from universal_evidence.capability import (
    CapabilityState,
    InMemoryCapabilityRepository,
)
from universal_evidence.planning.fingerprint import fingerprint
from universal_evidence.planning.models import (
    AnalyticalIntent,
    AnalyticalIntentType,
    AnalyticalPlan,
    AnalyticalPlanProvenance,
    PlanningReason,
    PlanningResult,
    PlanningStatus,
)
from universal_evidence.planning.policy import AnalyticalPlanningPolicy
from universal_evidence.planning.registry import INTENT_REGISTRY, PLANNING_REGISTRY_VERSION
from universal_evidence.planning.repository import InMemoryAnalyticalPlanRepository

FILTER_VALUE_TYPES = (str, int, float, Decimal, date, datetime)


class AnalyticalQueryPlanner:
    def __init__(
        self,
        *,
        capability_repository: InMemoryCapabilityRepository,
        repository: InMemoryAnalyticalPlanRepository | None = None,
        policy: AnalyticalPlanningPolicy | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.capability_repository = capability_repository
        self.repository = repository or InMemoryAnalyticalPlanRepository()
        self.policy = policy or AnalyticalPlanningPolicy()
        self.clock = clock or (lambda: datetime.now(timezone.utc))

    def plan(self, intent: AnalyticalIntent) -> PlanningResult:
        current = self.capability_repository.get_current_assessment(intent.scope.key)
        if current is None:
            return self._finish(intent, PlanningStatus.STALE, PlanningReason.CAPABILITY_STALE)
        if current.scope != intent.scope:
            return self._finish(intent, PlanningStatus.REJECTED, PlanningReason.SCOPE_MISMATCH)
        if (
            intent.capability_assessment_id is not None
            and intent.capability_assessment_id != current.assessment_id
        ):
            return self._finish(intent, PlanningStatus.STALE, PlanningReason.CAPABILITY_STALE)
        if (
            not isinstance(intent.intent_type, AnalyticalIntentType)
            or intent.intent_type not in INTENT_REGISTRY
            or intent.intent_version != self.policy.intent_version
        ):
            return self._finish(intent, PlanningStatus.REJECTED, PlanningReason.INTENT_UNSUPPORTED)
        capability_name, operation = INTENT_REGISTRY[intent.intent_type]
        shape_reason = self._validate_shape(intent)
        if shape_reason is not None:
            return self._finish(intent, PlanningStatus.REJECTED, shape_reason, current)

        measure, reason = self._resolve_unique(
            current.measures,
            intent.measure_concept_id,
            PlanningReason.MEASURE_NOT_GOVERNED,
            PlanningReason.AMBIGUOUS_MEASURE,
        )
        if intent.intent_type is AnalyticalIntentType.COUNT_RECORDS:
            measure, reason = None, None
        if reason is not None:
            status = (
                PlanningStatus.AMBIGUOUS if "AMBIGUOUS" in reason.value else PlanningStatus.REJECTED
            )
            return self._finish(intent, status, reason, current)

        dimensions = []
        for concept_id in intent.dimension_concept_ids:
            dimension, reason = self._resolve_unique(
                current.dimensions,
                concept_id,
                PlanningReason.DIMENSION_NOT_GOVERNED,
                PlanningReason.AMBIGUOUS_DIMENSION,
            )
            if reason is not None:
                status = (
                    PlanningStatus.AMBIGUOUS
                    if reason is PlanningReason.AMBIGUOUS_DIMENSION
                    else PlanningStatus.REJECTED
                )
                return self._finish(intent, status, reason, current)
            dimensions.append(dimension)

        time_dimension = None
        if intent.time_dimension_concept_id is not None:
            time_dimension, reason = self._resolve_unique(
                current.dimensions,
                intent.time_dimension_concept_id,
                PlanningReason.TIME_DIMENSION_NOT_GOVERNED,
                PlanningReason.AMBIGUOUS_DIMENSION,
            )
            if reason is not None:
                return self._finish(intent, PlanningStatus.REJECTED, reason, current)

        capability = next(
            (item for item in current.capabilities if item.capability_name == capability_name),
            None,
        )
        if capability is None:
            return self._finish(
                intent, PlanningStatus.REJECTED, PlanningReason.CAPABILITY_NOT_FOUND, current
            )
        if capability.state is not CapabilityState.SUPPORTED:
            return self._finish(
                intent,
                PlanningStatus.BLOCKED,
                PlanningReason.CAPABILITY_BLOCKED,
                current,
                capability=capability,
                measure=measure,
                dimensions=tuple(dimensions),
                time_dimension=time_dimension,
            )

        dimension_ids = tuple(item.dimension_id for item in dimensions)
        time_dimension_id = time_dimension.dimension_id if time_dimension else None
        candidates = tuple(
            item
            for item in current.execution_authorizations
            if item.capability_id == capability.capability_id
            and operation in item.authorized_operations
            and item.measure_id == (measure.measure_id if measure else None)
            and item.dimension_ids == dimension_ids
            and item.time_dimension_id == time_dimension_id
        )
        if intent.execution_authorization_id is not None:
            historical = any(
                item.authorization_id == intent.execution_authorization_id
                for assessment in self.capability_repository.get_versions(intent.scope.key)
                if assessment.assessment_id != current.assessment_id
                for item in assessment.execution_authorizations
            )
            candidates = tuple(
                item
                for item in candidates
                if item.authorization_id == intent.execution_authorization_id
            )
            if not candidates and historical:
                return self._finish(
                    intent,
                    PlanningStatus.STALE,
                    PlanningReason.AUTHORIZATION_STALE,
                    current,
                    capability=capability,
                    measure=measure,
                    dimensions=tuple(dimensions),
                    time_dimension=time_dimension,
                )
        if not candidates:
            return self._finish(
                intent,
                PlanningStatus.REJECTED,
                PlanningReason.AUTHORIZATION_NOT_FOUND,
                current,
                capability=capability,
                measure=measure,
                dimensions=tuple(dimensions),
                time_dimension=time_dimension,
            )
        if len(candidates) != 1:
            return self._finish(
                intent,
                PlanningStatus.AMBIGUOUS,
                PlanningReason.AUTHORIZATION_NOT_FOUND,
                current,
                capability=capability,
                measure=measure,
                dimensions=tuple(dimensions),
                time_dimension=time_dimension,
            )
        authorization = candidates[0]
        if not self.capability_repository.is_authorization_current(authorization):
            return self._finish(
                intent,
                PlanningStatus.STALE,
                PlanningReason.AUTHORIZATION_STALE,
                current,
                capability=capability,
                authorization=authorization,
                measure=measure,
                dimensions=tuple(dimensions),
                time_dimension=time_dimension,
            )
        if (
            intent.time_bucket is not None
            and intent.time_bucket.value not in authorization.allowed_time_buckets
        ):
            return self._finish(
                intent,
                PlanningStatus.REJECTED,
                PlanningReason.TIME_BUCKET_NOT_AUTHORIZED,
                current,
                capability=capability,
                authorization=authorization,
                measure=measure,
                dimensions=tuple(dimensions),
                time_dimension=time_dimension,
            )
        if (
            intent.requested_currency_behavior is not None
            and intent.requested_currency_behavior != authorization.currency_requirement
        ):
            return self._finish(
                intent,
                PlanningStatus.REJECTED,
                PlanningReason.OPERATION_NOT_AUTHORIZED,
                current,
                capability=capability,
                authorization=authorization,
                measure=measure,
                dimensions=tuple(dimensions),
                time_dimension=time_dimension,
            )
        filters, filter_reason = self._resolve_filters(intent, current, authorization)
        if filter_reason is not None:
            return self._finish(
                intent,
                PlanningStatus.REJECTED,
                filter_reason,
                current,
                capability=capability,
                authorization=authorization,
                measure=measure,
                dimensions=tuple(dimensions),
                time_dimension=time_dimension,
            )
        if (
            intent.intent_type
            in {
                AnalyticalIntentType.GROUP_MEASURE_BY_DIMENSION,
                AnalyticalIntentType.TIME_SERIES_MEASURE,
            }
            and authorization.alignment_id is None
        ):
            return self._finish(
                intent,
                PlanningStatus.REJECTED,
                PlanningReason.ALIGNMENT_NOT_AUTHORIZED,
                current,
                capability=capability,
                authorization=authorization,
                measure=measure,
                dimensions=tuple(dimensions),
                time_dimension=time_dimension,
            )
        return self._ready(
            intent,
            current,
            capability,
            authorization,
            measure,
            tuple(dimensions),
            time_dimension,
            filters,
            operation,
        )

    def _validate_shape(self, intent):
        def canonical(value):
            return value is None or (
                isinstance(value, str) and self.policy.canonical_concept_separator in value
            )

        if (
            not canonical(intent.measure_concept_id)
            or not all(canonical(item) for item in intent.dimension_concept_ids)
            or not canonical(intent.time_dimension_concept_id)
        ):
            return PlanningReason.INTENT_UNSUPPORTED
        expected = {
            AnalyticalIntentType.COUNT_RECORDS: (False, 0, False, False),
            AnalyticalIntentType.TOTAL_MEASURE: (True, 0, False, False),
            AnalyticalIntentType.GROUP_MEASURE_BY_DIMENSION: (True, 1, False, False),
            AnalyticalIntentType.TIME_SERIES_MEASURE: (True, 0, True, True),
        }[intent.intent_type]
        needs_measure, dimension_count, needs_time, needs_bucket = expected
        if bool(intent.measure_concept_id) != needs_measure:
            return PlanningReason.INTENT_UNSUPPORTED
        if len(intent.dimension_concept_ids) != dimension_count:
            return PlanningReason.INTENT_UNSUPPORTED
        if bool(intent.time_dimension_concept_id) != needs_time:
            return PlanningReason.INTENT_UNSUPPORTED
        if bool(intent.time_bucket) != needs_bucket:
            return PlanningReason.TIME_BUCKET_NOT_AUTHORIZED
        return None

    @staticmethod
    def _resolve_unique(items, concept_id, missing_reason, ambiguous_reason):
        matches = tuple(
            item
            for item in items
            if item.semantic_concept_id == concept_id and item.state is CapabilityState.SUPPORTED
        )
        if not matches:
            return None, missing_reason
        if len(matches) != 1:
            return None, ambiguous_reason
        return matches[0], None

    def _resolve_filters(self, intent, assessment, authorization):
        dimensions = {item.semantic_concept_id: item for item in assessment.dimensions}
        results = []
        authorized = set(authorization.dimension_ids)
        if authorization.time_dimension_id:
            authorized.add(authorization.time_dimension_id)
        for item in intent.filters:
            dimension = dimensions.get(item.dimension_concept_id)
            tuple_value = (
                isinstance(item.value, tuple)
                and item.value
                and all(isinstance(value, FILTER_VALUE_TYPES) for value in item.value)
            )
            scalar_value = isinstance(item.value, FILTER_VALUE_TYPES)
            value_ok = tuple_value if item.operator is FilterOperator.IN else scalar_value
            strings = item.value if isinstance(item.value, tuple) else (item.value,)
            injection_like = any(
                isinstance(value, str)
                and any(
                    token in value.lower()
                    for token in ("select ", "drop ", "--", ";", "lambda", "__")
                )
                for value in strings
            )
            if (
                dimension is None
                or dimension.dimension_id not in authorized
                or not isinstance(item.operator, FilterOperator)
                or not value_ok
                or injection_like
            ):
                return (), PlanningReason.FILTER_NOT_AUTHORIZED
            results.append(AggregationFilter(dimension.dimension_id, item.operator, item.value))
        return tuple(results), None

    def _ready(
        self,
        intent,
        assessment,
        capability,
        authorization,
        measure,
        dimensions,
        time_dimension,
        filters,
        operation,
    ):
        result = self._finish(
            intent,
            PlanningStatus.READY,
            PlanningReason.PLAN_READY,
            assessment,
            capability=capability,
            authorization=authorization,
            measure=measure,
            dimensions=dimensions,
            time_dimension=time_dimension,
            filters=filters,
            operation=operation,
        )
        plan = result.plan
        request = AggregationRequest(
            plan.plan_id,
            plan.scope,
            plan.capability_assessment_id,
            plan.execution_authorization_id,
            plan.operation,
            plan.measure_id,
            plan.dimension_ids,
            plan.time_dimension_id,
            plan.filters,
            plan.time_bucket,
            self.policy.execution_policy_version,
            intent.created_at,
        )
        return PlanningResult(plan, request)

    def _finish(
        self,
        intent,
        status,
        reason,
        assessment=None,
        *,
        capability=None,
        authorization=None,
        measure=None,
        dimensions=(),
        time_dimension=None,
        filters=(),
        operation=None,
    ):
        coverage_ids = ()
        if capability is not None:
            coverage_ids = capability.supporting_coverage_ids
        provenance = AnalyticalPlanProvenance(
            assessment.assessment_id if assessment else None,
            capability.capability_id if capability else None,
            authorization.authorization_id if authorization else None,
            measure.measure_id if measure else None,
            tuple(item.dimension_id for item in dimensions),
            time_dimension.dimension_id if time_dimension else None,
            authorization.alignment_id if authorization else None,
            authorization.record_basis_id if authorization else None,
            authorization.normalization_run_ids if authorization else (),
            coverage_ids,
            assessment.capability_policy_version if assessment else None,
            authorization.policy_version if authorization else None,
        )
        identity = fingerprint(
            intent,
            status,
            reason,
            provenance,
            filters,
            operation,
            self.policy.version,
            PLANNING_REGISTRY_VERSION,
        )
        plan = AnalyticalPlan(
            "analytical-plan-" + identity[:24],
            intent.intent_id,
            intent.scope,
            intent.intent_type if isinstance(intent.intent_type, AnalyticalIntentType) else None,
            provenance.capability_assessment_id,
            provenance.capability_id,
            provenance.execution_authorization_id,
            operation,
            provenance.measure_id,
            provenance.dimension_ids,
            provenance.time_dimension_id,
            filters,
            intent.time_bucket,
            authorization.currency_requirement if authorization else None,
            authorization.unit_requirement if authorization else None,
            provenance.alignment_id,
            provenance.record_basis_id,
            provenance.normalization_run_ids,
            status,
            (PlanningReason.INTENT_VALID, reason) if status is PlanningStatus.READY else (reason,),
            provenance,
            self.policy.version,
            identity,
            self.clock(),
        )
        plan = self.repository.store(plan)
        return PlanningResult(plan, None)
