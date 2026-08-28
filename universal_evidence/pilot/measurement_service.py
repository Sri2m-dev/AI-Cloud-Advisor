"""ACT-005 pilot adapter over certified capability, planning, and aggregation."""

from __future__ import annotations

from datetime import datetime, timezone
from time import perf_counter

from universal_evidence.activation import (
    ActivationScope,
    ActivationStage,
    RoutingReason,
    ScopeLevel,
)
from universal_evidence.aggregation import AggregationExecutor, AggregationResultStatus
from universal_evidence.capability import AuthorizedOperation
from universal_evidence.normalization.fingerprints import fingerprint
from universal_evidence.pilot.measurement_view_models import MeasurementReadinessViewModel
from universal_evidence.planning import (
    AnalyticalIntent,
    AnalyticalQueryPlanner,
    PlanningStatus,
)


class PilotGovernedMeasurementService:
    """Coordinates existing certified layers; performs no aggregation itself."""

    def __init__(
        self,
        *,
        activation_resolver,
        normalization_service,
        telemetry,
        audit_sink=None,
        clock=None,
    ) -> None:
        self.activation_resolver = activation_resolver
        self.normalization_service = normalization_service
        self.telemetry = telemetry
        self.audit_sink = audit_sink
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        capability_repository = normalization_service.capabilities.repository
        self.planner = AnalyticalQueryPlanner(
            capability_repository=capability_repository, clock=self.clock
        )
        self.executor = AggregationExecutor(
            capability_repository=capability_repository, clock=self.clock
        )

    def readiness(self, admission, *, actor):
        activation = self._activation(admission)
        if self._suppressed(activation):
            return None
        if activation.stage < ActivationStage.CAPABILITY_VISIBLE:
            identity = fingerprint(admission.evidence_fingerprint, activation.stage)
            return MeasurementReadinessViewModel(
                True,
                False,
                (),
                (),
                False,
                (),
                (),
                "BLOCKED",
                ("Normalization and execution authorization are not visible at Stage 1.",),
                None,
                identity,
            )
        try:
            runs, assessment = self._current(admission, actor=actor)
        except PermissionError as exc:
            identity = fingerprint(admission.evidence_fingerprint, str(exc))
            return MeasurementReadinessViewModel(
                True,
                False,
                (),
                (),
                False,
                (),
                (),
                "BLOCKED",
                (str(exc),),
                None,
                identity,
            )
        measures = tuple(sorted(item.semantic_concept_id for item in assessment.measures))
        dimensions = tuple(sorted(item.semantic_concept_id for item in assessment.dimensions))
        operations = tuple(
            sorted(
                {
                    operation.value
                    for authorization in assessment.execution_authorizations
                    for operation in authorization.authorized_operations
                    if operation
                    in {
                        AuthorizedOperation.COUNT,
                        AuthorizedOperation.SUM,
                        AuthorizedOperation.GROUPED_COUNT,
                        AuthorizedOperation.GROUPED_SUM,
                    }
                }
            )
        )
        currency_ready = any(
            item.semantic_concept_id == "financial.currency" and item.valid_records > 0
            for item in assessment.coverage
        )
        monetary_ready = AuthorizedOperation.SUM.value in operations
        reasons = (
            ()
            if monetary_ready
            else (
                "A current monetary execution authorization requires governed amount and currency.",
            )
        )
        identity = fingerprint(
            admission.evidence_fingerprint,
            tuple(run.fingerprint for run in runs),
            assessment.fingerprint,
            operations,
        )
        return MeasurementReadinessViewModel(
            True,
            bool(runs),
            measures,
            dimensions,
            currency_ready,
            operations,
            tuple(item.authorization_id for item in assessment.execution_authorizations),
            "EXECUTABLE" if operations else "BLOCKED",
            reasons,
            assessment.assessment_id,
            identity,
        )

    def execute(
        self,
        admission,
        *,
        actor,
        intent_type,
        measure_concept_id=None,
        dimension_concept_ids=(),
    ):
        started = perf_counter()
        activation = self._activation(admission)
        if self._suppressed(activation) or activation.stage < ActivationStage.CAPABILITY_VISIBLE:
            self._metric("measurement_execution_blocked", admission, 1)
            self._audit("PUE_MEASUREMENT_EXECUTION_BLOCKED", admission, actor)
            raise PermissionError("ACT-C1 activation does not authorize measurement execution")
        runs, assessment = self._current(admission, actor=actor)
        intent_fingerprint = fingerprint(
            admission.evidence_fingerprint,
            assessment.fingerprint,
            intent_type,
            measure_concept_id,
            tuple(dimension_concept_ids),
        )
        intent = AnalyticalIntent(
            "act005-intent-" + intent_fingerprint[:24],
            admission.scope,
            intent_type,
            measure_concept_id,
            tuple(dimension_concept_ids),
            None,
            (),
            None,
            None,
            actor.actor_id,
            "HUMAN",
            assessment.assessment_id,
            None,
            self.planner.policy.intent_version,
            admission.created_at,
        )
        planning = self.planner.plan(intent)
        self._metric("measurement_plan_created", admission, 1)
        self._audit("PUE_MEASUREMENT_PLAN_CREATED", admission, actor)
        if planning.plan.planning_status is not PlanningStatus.READY:
            self._metric("measurement_execution_blocked", admission, 1)
            self._audit("PUE_MEASUREMENT_EXECUTION_BLOCKED", admission, actor)
            return planning, None
        result = self.executor.execute(planning.aggregation_request, assessment, runs)
        operation_metric = {
            AuthorizedOperation.COUNT: "measurement_operation_count",
            AuthorizedOperation.SUM: "measurement_operation_sum",
            AuthorizedOperation.GROUPED_SUM: "measurement_operation_grouped_sum",
        }.get(planning.plan.operation)
        if operation_metric:
            self._metric(operation_metric, admission, 1)
        self._metric(
            "measurement_latency_ms",
            admission,
            max(0, round((perf_counter() - started) * 1000)),
        )
        if result.status is AggregationResultStatus.COMPLETED:
            self._metric("measurement_execution_succeeded", admission, 1)
            self._metric("measurement_record_count", admission, result.statistics.included_records)
            excluded = (
                result.statistics.excluded_null_records
                + result.statistics.excluded_invalid_records
                + result.statistics.excluded_partial_records
                + result.statistics.excluded_unsupported_records
                + result.statistics.excluded_filter_records
            )
            self._metric("measurement_exclusion_count", admission, excluded)
            self._audit("PUE_AGGREGATION_EXECUTED", admission, actor)
        else:
            self._metric("measurement_execution_blocked", admission, 1)
            self._audit("PUE_MEASUREMENT_EXECUTION_BLOCKED", admission, actor)
        return planning, result

    def record_result_viewed(self, admission, *, actor):
        self._audit("PUE_AGGREGATION_RESULT_VIEWED", admission, actor)

    def result_is_current(self, admission, planning, result, *, actor):
        if result is None or planning.plan.scope != admission.scope:
            return False
        activation = self._activation(admission)
        if self._suppressed(activation):
            return False
        try:
            runs, assessment = self._current(admission, actor=actor)
        except PermissionError:
            return False
        return (
            planning.plan.capability_assessment_id == assessment.assessment_id
            and tuple(sorted(planning.plan.normalization_run_ids))
            == tuple(sorted(run.normalization_run_id for run in runs))
            and planning.aggregation_request is not None
            and result.request_id == planning.aggregation_request.request_id
            and result.provenance is not None
            and result.provenance.authorization_id
            == planning.plan.execution_authorization_id
            and result in self.executor.repository.get_versions(admission.scope.key)
        )

    def _current(self, admission, *, actor):
        plan = self.normalization_service.plan(admission, actor=actor)
        runs = self.normalization_service.execute(admission, plan=plan, actor=actor)
        if not runs:
            raise PermissionError("governed normalization is required")
        assessment = self.normalization_service.capabilities.evaluate(runs)
        return runs, assessment

    def _activation(self, admission):
        return self.activation_resolver.resolve(
            ActivationScope(
                ScopeLevel.ANALYSIS,
                organization_id=admission.scope.organization_id,
                tenant_id=admission.scope.tenant_id,
                prospect_id=admission.scope.prospect_id,
                analysis_id=admission.scope.analysis_id,
            )
        )

    @staticmethod
    def _suppressed(activation):
        return (
            RoutingReason.KILL_SWITCH_ACTIVE in activation.reason_codes
            or activation.stage is ActivationStage.SHADOW_ONLY
        )

    def _metric(self, name, admission, value):
        self.telemetry.increment(name, admission.scope.key, value)

    def _audit(self, event_type, admission, actor):
        if self.audit_sink is not None:
            self.audit_sink.record(
                event_type=event_type,
                actor_id=actor.actor_id,
                timestamp=self.clock(),
                reason="ACT-005 governed measurement pilot",
                scope_key=admission.scope.key,
                activation_id=None,
            )
