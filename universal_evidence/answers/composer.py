"""Deterministic PUE-009 composition over certified upstream objects only."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone

from universal_evidence.aggregation import (
    AggregationResultStatus,
    GovernedAggregationResult,
    InMemoryAggregationRepository,
)
from universal_evidence.answers.fingerprint import fingerprint
from universal_evidence.answers.formatting import format_governed_value
from universal_evidence.answers.models import (
    AnswerGroup,
    AnswerProvenance,
    AnswerReason,
    AnswerScalar,
    AnswerState,
    AnswerStructuredValues,
    GovernedAnalyticalAnswer,
)
from universal_evidence.answers.policy import AnswerCompositionPolicy
from universal_evidence.answers.repository import InMemoryAnswerRepository
from universal_evidence.capability import (
    InMemoryCapabilityRepository,
    ReasonCode,
)
from universal_evidence.interpretation import (
    InterpretationStatus,
    NaturalLanguageInterpretationResult,
)
from universal_evidence.planning import (
    AnalyticalIntentType,
    AnalyticalPlan,
    InMemoryAnalyticalPlanRepository,
    PlanningStatus,
)


class GovernedAnswerComposer:
    def __init__(
        self,
        *,
        capability_repository: InMemoryCapabilityRepository,
        plan_repository: InMemoryAnalyticalPlanRepository,
        aggregation_repository: InMemoryAggregationRepository,
        repository: InMemoryAnswerRepository | None = None,
        policy: AnswerCompositionPolicy | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.capability_repository = capability_repository
        self.plan_repository = plan_repository
        self.aggregation_repository = aggregation_repository
        self.repository = repository or InMemoryAnswerRepository()
        self.policy = policy or AnswerCompositionPolicy()
        self.clock = clock or (lambda: datetime.now(timezone.utc))

    def compose(
        self,
        interpretation: NaturalLanguageInterpretationResult,
        plan: AnalyticalPlan | None = None,
        result: GovernedAggregationResult | None = None,
    ) -> GovernedAnalyticalAnswer:
        if interpretation.status is InterpretationStatus.AMBIGUOUS:
            return self._answer(
                interpretation,
                None,
                None,
                AnswerState.AMBIGUOUS,
                "The question is ambiguous in the current governed concept set.",
                (),
                (AnswerReason.QUESTION_AMBIGUOUS,),
            )
        if interpretation.status is not InterpretationStatus.INTERPRETED:
            return self._answer(
                interpretation,
                None,
                None,
                AnswerState.UNSUPPORTED,
                "This question is not supported by the currently certified analytical intents.",
                (),
                (AnswerReason.QUESTION_UNSUPPORTED,),
            )
        if plan is None:
            return self._failed(
                interpretation,
                None,
                result,
                AnswerReason.UPSTREAM_FAILED,
                "No governed analytical plan is available for this interpretation.",
            )
        validation = self._validate_plan(interpretation, plan)
        if validation is not None:
            return self._failed(interpretation, plan, result, *validation)
        if plan.planning_status is PlanningStatus.BLOCKED:
            return self._blocked(interpretation, plan)
        if plan.planning_status is not PlanningStatus.READY:
            return self._failed(
                interpretation,
                plan,
                result,
                AnswerReason.UPSTREAM_FAILED,
                "The governed analytical plan did not reach READY state.",
            )
        if result is None:
            return self._failed(
                interpretation,
                plan,
                None,
                AnswerReason.RESULT_MISSING,
                "No governed execution result is available for this READY plan.",
            )
        validation = self._validate_result(plan, result)
        if validation is not None:
            return self._failed(interpretation, plan, result, *validation)
        if result.status not in {
            AggregationResultStatus.COMPLETED,
            AggregationResultStatus.PARTIAL,
        }:
            return self._failed(
                interpretation,
                plan,
                result,
                AnswerReason.UPSTREAM_FAILED,
                "The governed execution did not produce a composable result.",
            )
        return self._compose_result(interpretation, plan, result)

    def _validate_plan(self, interpretation, plan):
        if interpretation.scope != plan.scope:
            return AnswerReason.SCOPE_MISMATCH, "Interpretation and plan scopes do not match."
        if interpretation.primary_intent is None or (
            interpretation.primary_intent.intent_id != plan.intent_id
        ):
            return (
                AnswerReason.RESULT_PLAN_MISMATCH,
                "Plan does not reference the interpreted intent.",
            )
        if plan not in self.plan_repository.get_versions(plan.scope.key):
            return AnswerReason.PLAN_NOT_CURRENT, "The analytical plan is not certified in history."
        current = self.capability_repository.get_current_assessment(plan.scope.key)
        if current is None or current.assessment_id != plan.capability_assessment_id:
            return AnswerReason.PLAN_NOT_CURRENT, "The analytical plan is no longer current."
        return None

    def _validate_result(self, plan, result):
        if result.scope != plan.scope:
            return AnswerReason.SCOPE_MISMATCH, "Plan and execution result scopes do not match."
        if result not in self.aggregation_repository.get_versions(result.scope.key):
            return AnswerReason.RESULT_NOT_CURRENT, "Execution result is not certified in history."
        if result.request_id != plan.plan_id:
            return (
                AnswerReason.RESULT_PLAN_MISMATCH,
                "Execution result does not reference this plan.",
            )
        effective_dimensions = plan.dimension_ids or (
            (plan.time_dimension_id,) if plan.time_dimension_id else ()
        )
        if (
            result.operation != plan.operation
            or result.measure_id != plan.measure_id
            or result.dimension_ids != effective_dimensions
            or result.provenance is None
            or result.provenance.authorization_id != plan.execution_authorization_id
            or result.provenance.capability_assessment_id != plan.capability_assessment_id
        ):
            return (
                AnswerReason.RESULT_PLAN_MISMATCH,
                "Execution result metadata does not match the plan.",
            )
        current = self.capability_repository.get_current_assessment(plan.scope.key)
        authorization = next(
            (
                item
                for item in current.execution_authorizations
                if item.authorization_id == plan.execution_authorization_id
            ),
            None,
        )
        if authorization is None or not self.capability_repository.is_authorization_current(
            authorization
        ):
            return (
                AnswerReason.AUTHORIZATION_NOT_CURRENT,
                "Execution authorization is no longer current.",
            )
        return None

    def _blocked(self, interpretation, plan):
        current = self.capability_repository.get_current_assessment(plan.scope.key)
        reasons = set()
        if current is not None:
            capability = next(
                (item for item in current.capabilities if item.capability_id == plan.capability_id),
                None,
            )
            if capability is not None:
                reasons.update(capability.reason_codes)
            if plan.measure_id is not None:
                measure = next(
                    (item for item in current.measures if item.measure_id == plan.measure_id), None
                )
                if measure is not None:
                    reasons.update(measure.reason_codes)
        currency_missing = bool(
            {ReasonCode.UNIT_NOT_EVIDENCED, ReasonCode.MIXED_CURRENCY} & reasons
        )
        if currency_missing:
            text = (
                "Total cost cannot be calculated because governed currency evidence "
                "is not available or compatible."
            )
            code = AnswerReason.CURRENCY_EVIDENCE_REQUIRED
        else:
            text = "The requested calculation is blocked by the current governed evidence."
            code = AnswerReason.UPSTREAM_BLOCKED
        return self._answer(interpretation, plan, None, AnswerState.BLOCKED, text, (), (code,))

    def _compose_result(self, interpretation, plan, result):
        limitations = list(self._partial_limitations(result))
        reasons = [AnswerReason.GOVERNED_RESULT_RENDERED]
        state = AnswerState.ANSWERED
        if result.status is AggregationResultStatus.PARTIAL:
            state = AnswerState.PARTIAL
            reasons.append(AnswerReason.PARTIAL_RESULT_DISCLOSED)
        displayed_groups = result.groups[: self.policy.maximum_displayed_groups]
        groups = tuple(
            AnswerGroup(
                item.dimension_values,
                item.value,
                item.unit,
                item.record_count,
                item.group_id,
            )
            for item in displayed_groups
        )
        if len(displayed_groups) < len(result.groups):
            limitations.append(
                f"{len(result.groups)} governed groups were returned; the first "
                f"{len(displayed_groups)} are shown in certified result order."
            )
            reasons.append(AnswerReason.GROUPS_TRUNCATED)
        scalar = (
            AnswerScalar(result.scalar_value, result.currency_or_unit)
            if result.scalar_value is not None
            else None
        )
        structured = AnswerStructuredValues(
            scalar, groups, len(result.groups), len(displayed_groups)
        )
        if scalar is not None:
            rendered = format_governed_value(scalar.value, scalar.unit)
            if plan.intent_type is AnalyticalIntentType.COUNT_RECORDS:
                text = f"{rendered} governed source records are available."
            else:
                text = f"Total governed cost is {rendered}."
        else:
            lines = ["Governed analytical results:"]
            for item in groups:
                label = ", ".join(str(value) for _, value in item.dimension_values)
                lines.append(f"- {label}: {format_governed_value(item.value, item.unit)}")
            text = "\n".join(lines)
        if limitations:
            text = f"{text}\nLimitations: {' '.join(limitations)}"
        return self._answer(
            interpretation,
            plan,
            result,
            state,
            text,
            tuple(limitations),
            tuple(reasons),
            structured,
        )

    @staticmethod
    def _partial_limitations(result):
        if result.status is not AggregationResultStatus.PARTIAL:
            return ()
        statistics = result.statistics
        messages = [f"{statistics.included_records} records were included."]
        categories = (
            (statistics.excluded_invalid_records, "invalid normalized values"),
            (statistics.excluded_null_records, "null values"),
            (statistics.excluded_partial_records, "partial normalized values"),
            (statistics.excluded_unsupported_records, "unsupported normalized values"),
            (statistics.excluded_filter_records, "the governed filter"),
        )
        messages.extend(
            f"{count} records were excluded due to {reason}."
            for count, reason in categories
            if count
        )
        return tuple(messages)

    def _failed(self, interpretation, plan, result, reason, text):
        return self._answer(interpretation, plan, result, AnswerState.FAILED, text, (), (reason,))

    def _answer(
        self,
        interpretation,
        plan,
        result,
        state,
        text,
        limitations,
        reasons,
        structured=None,
    ):
        structured = structured or AnswerStructuredValues(None, (), 0, 0)
        result_provenance = result.provenance if result is not None else None
        provenance = AnswerProvenance(
            interpretation.interpretation_id,
            interpretation.fingerprint,
            plan.plan_id if plan else None,
            plan.plan_fingerprint if plan else None,
            result.result_id if result else None,
            result.result_fingerprint if result else None,
            (
                result_provenance.capability_assessment_id
                if result_provenance
                else plan.capability_assessment_id
                if plan
                else None
            ),
            result_provenance.capability_id
            if result_provenance
            else plan.capability_id
            if plan
            else None,
            (
                result_provenance.authorization_id
                if result_provenance
                else plan.execution_authorization_id
                if plan
                else None
            ),
            result_provenance.normalization_run_ids if result_provenance else (),
            result_provenance.source_row_fingerprints if result_provenance else (),
            result.statistics.included_records if result else None,
            self.policy.composer_version,
            self.policy.version,
        )
        text = text[: self.policy.maximum_answer_length]
        identity = fingerprint(
            interpretation.original_question,
            interpretation.fingerprint,
            plan.plan_fingerprint if plan else None,
            result.result_fingerprint if result else None,
            state,
            text,
            structured,
            limitations,
            reasons,
            provenance,
            self.policy,
        )
        answer = GovernedAnalyticalAnswer(
            "governed-answer-" + identity[:24],
            interpretation.original_question,
            interpretation.scope,
            state,
            text,
            structured,
            limitations,
            reasons,
            provenance,
            self.policy.composer_version,
            self.policy.version,
            identity,
            self.clock(),
        )
        return self.repository.store(answer)
