"""Authorization-first PUE-006 plan construction."""

from __future__ import annotations

from dataclasses import dataclass

from universal_evidence.aggregation.fingerprint import fingerprint
from universal_evidence.aggregation.models import (
    AggregationRequest,
    AggregationWarning,
    GovernedAggregationPlan,
)
from universal_evidence.aggregation.policy import AggregationExecutionPolicy
from universal_evidence.aggregation.registry import (
    CAPABILITY_OPERATIONS,
    EXECUTION_REGISTRY_VERSION,
)
from universal_evidence.capability import (
    CapabilityAssessment,
    CapabilityState,
    InMemoryCapabilityRepository,
)
from universal_evidence.normalization import NormalizationRun


@dataclass(frozen=True, slots=True)
class PlanRejection(Exception):
    warning: AggregationWarning


class AggregationPlanner:
    def __init__(
        self,
        capability_repository: InMemoryCapabilityRepository,
        policy: AggregationExecutionPolicy,
    ) -> None:
        self.capability_repository = capability_repository
        self.policy = policy

    def plan(
        self,
        request: AggregationRequest,
        assessment: CapabilityAssessment,
        runs: tuple[NormalizationRun, ...],
    ) -> GovernedAggregationPlan:
        if request.scope != assessment.scope:
            raise PlanRejection(AggregationWarning.SCOPE_MISMATCH)
        if request.capability_assessment_id != assessment.assessment_id:
            raise PlanRejection(AggregationWarning.AUTHORIZATION_MISMATCH)
        authorization = next(
            (
                item
                for item in assessment.execution_authorizations
                if item.authorization_id == request.authorization_id
            ),
            None,
        )
        if authorization is None:
            expected = next(
                (
                    capability
                    for capability in assessment.capabilities
                    if request.operation
                    in CAPABILITY_OPERATIONS.get(capability.capability_name, ())
                ),
                None,
            )
            if expected is not None and expected.state is not CapabilityState.SUPPORTED:
                raise PlanRejection(
                    AggregationWarning.UPSTREAM_CAPABILITY_NOT_SUPPORTED
                )
            raise PlanRejection(AggregationWarning.AUTHORIZATION_MISMATCH)
        if not self.capability_repository.is_authorization_current(authorization):
            raise PlanRejection(AggregationWarning.STALE_CAPABILITY)
        if request.execution_policy_version != self.policy.version:
            raise PlanRejection(AggregationWarning.STALE_CAPABILITY)
        if request.operation not in authorization.authorized_operations:
            raise PlanRejection(AggregationWarning.UNSUPPORTED_OPERATION)
        capability = next(
            item
            for item in assessment.capabilities
            if item.capability_id == authorization.capability_id
        )
        if request.operation not in CAPABILITY_OPERATIONS.get(
            capability.capability_name, frozenset()
        ):
            raise PlanRejection(AggregationWarning.UNSUPPORTED_OPERATION)
        if request.measure_id != authorization.measure_id:
            raise PlanRejection(AggregationWarning.MEASURE_MISMATCH)
        if request.dimension_ids != authorization.dimension_ids:
            raise PlanRejection(AggregationWarning.DIMENSION_MISMATCH)
        if request.time_dimension_id != authorization.time_dimension_id:
            raise PlanRejection(AggregationWarning.TIME_DIMENSION_MISMATCH)
        if request.time_bucket is not None and request.time_bucket.value not in (
            authorization.allowed_time_buckets
        ):
            raise PlanRejection(AggregationWarning.TIME_BUCKET_NOT_AUTHORIZED)
        if request.operation.value.startswith("TIME_") and request.time_bucket is None:
            raise PlanRejection(AggregationWarning.TIME_BUCKET_NOT_AUTHORIZED)
        run_ids = tuple(sorted(run.normalization_run_id for run in runs))
        if run_ids != tuple(sorted(authorization.normalization_run_ids)):
            raise PlanRejection(AggregationWarning.NORMALIZATION_RUN_MISMATCH)
        authorized_filter_dimensions = set(authorization.dimension_ids)
        if authorization.time_dimension_id:
            authorized_filter_dimensions.add(authorization.time_dimension_id)
        for item in request.filters:
            if not hasattr(item.operator, "value"):
                raise PlanRejection(AggregationWarning.UNSUPPORTED_FILTER)
            if item.dimension_id not in authorized_filter_dimensions:
                raise PlanRejection(AggregationWarning.UNSUPPORTED_FILTER)
            if isinstance(item.value, str) and any(
                token in item.value.lower()
                for token in ("select ", "drop ", "--", ";", "lambda", "__")
            ):
                raise PlanRejection(AggregationWarning.UNSUPPORTED_FILTER)
        plan_fingerprint = fingerprint(
            request.scope,
            assessment.fingerprint,
            authorization.authorization_fingerprint,
            request.operation,
            request.measure_id,
            request.dimension_ids,
            request.time_dimension_id,
            request.filters,
            request.time_bucket,
            run_ids,
            self.policy.version,
            EXECUTION_REGISTRY_VERSION,
        )
        return GovernedAggregationPlan(
            "aggregation-plan-" + plan_fingerprint[:24],
            request.request_id,
            request.scope,
            assessment.assessment_id,
            capability.capability_id,
            authorization.authorization_id,
            request.operation,
            request.measure_id,
            request.dimension_ids,
            request.time_dimension_id,
            request.filters,
            request.time_bucket,
            run_ids,
            authorization.alignment_id,
            authorization.record_basis_id,
            authorization.currency_requirement,
            authorization.unit_requirement,
            assessment.capability_policy_version,
            self.policy.version,
            plan_fingerprint,
        )
