"""Fail-closed orchestration across certified PUE contracts in shadow mode only."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timezone
from time import perf_counter

from universal_evidence.aggregation import AggregationExecutionPolicy, AggregationExecutor
from universal_evidence.answers import AnswerCompositionPolicy, GovernedAnswerComposer
from universal_evidence.capability import CapabilityEvaluator, CapabilityPolicy, CoveragePolicy
from universal_evidence.interpretation import (
    DeterministicAnalyticalInterpreter,
    InterpretationPolicy,
    InterpretationStatus,
    NaturalLanguageQuestion,
    build_concept_catalog,
)
from universal_evidence.normalization import NormalizationPolicy, NormalizationService
from universal_evidence.planning import (
    AnalyticalPlanningPolicy,
    AnalyticalQueryPlanner,
    PlanningStatus,
)
from universal_evidence.profiling import ProfileStatus, profile_evidence
from universal_evidence.semantic import discover_semantics
from universal_evidence.shadow.fingerprint import fingerprint
from universal_evidence.shadow.models import (
    PipelineVersions,
    ShadowAnalysisResult,
    ShadowProvenance,
    ShadowQuestionResult,
    ShadowStage,
    ShadowStatus,
    StageResult,
    StageStatus,
)
from universal_evidence.shadow.repository import InMemoryShadowRepository

SHADOW_ORCHESTRATOR_VERSION = "pue-010.1"


@dataclass(slots=True)
class _Runtime:
    capability_repository: object
    normalization_runs: tuple
    planner: object
    executor: object
    composer: object


def _elapsed(start: float) -> float:
    return round((perf_counter() - start) * 1000, 3)


def _stage(stage, status, start, reasons=(), references=()):
    return StageResult(stage, status, tuple(reasons), tuple(references), _elapsed(start))


class ShadowOrchestrator:
    """Owns disposable shadow repositories and never touches application state."""

    def __init__(self, *, repository=None, clock=None):
        self.repository = repository or InMemoryShadowRepository()
        self.clock = clock or (lambda: datetime.now(timezone.utc))

    def run_shadow_analysis(self, request):
        started_at = self.clock()
        total_start = perf_counter()
        stages = []

        tick = perf_counter()
        profile = profile_evidence(
            source=request.source, filename=request.filename, content=request.content
        )
        profile_status = (
            StageStatus.COMPLETED
            if profile.status is ProfileStatus.COMPLETE
            else StageStatus.PARTIAL
            if profile.status is ProfileStatus.PARTIAL
            else StageStatus.BLOCKED
        )
        stages.append(
            _stage(
                ShadowStage.PROFILING,
                profile_status,
                tick,
                (profile.status.value,),
                (profile.evidence_file.file_id,),
            )
        )

        tick = perf_counter()
        discovery = discover_semantics(profile)
        semantic_status = StageStatus.COMPLETED if discovery.columns else StageStatus.BLOCKED
        stages.append(
            _stage(
                ShadowStage.SEMANTIC_DISCOVERY,
                semantic_status,
                tick,
                references=(discovery.semantic_fingerprint,),
            )
        )

        bindings = request.normalization_bindings
        tick = perf_counter()
        governance_errors = self._validate_bindings(request, discovery, bindings)
        governance_status = (
            StageStatus.BLOCKED if governance_errors or not bindings else StageStatus.COMPLETED
        )
        stages.append(
            _stage(
                ShadowStage.CONFIRMATION_GOVERNANCE,
                governance_status,
                tick,
                governance_errors or (() if bindings else ("NO_EFFECTIVE_MAPPING",)),
                tuple(item.mapping.decision_id for item in bindings),
            )
        )

        normalization_runs = ()
        capability = None
        capability_repository = None
        if (
            governance_status is StageStatus.COMPLETED
            and semantic_status is not StageStatus.BLOCKED
        ):
            tick = perf_counter()
            service = NormalizationService(
                decision_repository=request.decision_repository,
                policy=NormalizationPolicy(),
                clock=self.clock,
            )
            try:
                normalization_runs = tuple(
                    service.normalize(item.mapping, item.values) for item in bindings
                )
            except Exception as error:  # noqa: BLE001 - shadow boundary contains stage failure
                stages.append(
                    _stage(
                        ShadowStage.NORMALIZATION,
                        StageStatus.FAILED,
                        tick,
                        (type(error).__name__,),
                    )
                )
                stages.append(
                    _stage(
                        ShadowStage.CAPABILITY,
                        StageStatus.SKIPPED,
                        perf_counter(),
                        ("NORMALIZATION_FAILED",),
                    )
                )
            else:
                partial = any(run.status.value != "COMPLETE" for run in normalization_runs)
                stages.append(
                    _stage(
                        ShadowStage.NORMALIZATION,
                        StageStatus.PARTIAL if partial else StageStatus.COMPLETED,
                        tick,
                        references=tuple(run.normalization_run_id for run in normalization_runs),
                    )
                )
                tick = perf_counter()
                evaluator = CapabilityEvaluator()
                try:
                    capability = evaluator.evaluate(normalization_runs)
                except Exception as error:  # noqa: BLE001 - shadow boundary contains stage failure
                    stages.append(
                        _stage(
                            ShadowStage.CAPABILITY,
                            StageStatus.FAILED,
                            tick,
                            (type(error).__name__,),
                        )
                    )
                else:
                    capability_repository = evaluator.repository
                    stages.append(
                        _stage(
                            ShadowStage.CAPABILITY,
                            StageStatus.COMPLETED,
                            tick,
                            references=(
                                capability.assessment_id,
                                *tuple(
                                    item.authorization_id
                                    for item in capability.execution_authorizations
                                ),
                            ),
                        )
                    )
        else:
            stages.extend(
                (
                    _stage(
                        ShadowStage.NORMALIZATION,
                        StageStatus.SKIPPED,
                        perf_counter(),
                        ("UPSTREAM_BLOCKED",),
                    ),
                    _stage(
                        ShadowStage.CAPABILITY,
                        StageStatus.SKIPPED,
                        perf_counter(),
                        ("UPSTREAM_BLOCKED",),
                    ),
                )
            )

        versions = self._versions(profile, discovery, normalization_runs)
        scope = request.source.context
        scope_key = (
            scope.analysis_id,
            scope.prospect_id,
            scope.organization_id,
            scope.tenant_id,
            scope.source_id,
        )
        identity = fingerprint(
            scope_key,
            profile.structural_fingerprint,
            discovery.semantic_fingerprint,
            tuple(run.fingerprint for run in normalization_runs),
            capability.fingerprint if capability else None,
            versions,
        )
        completed_at = self.clock()
        provenance = ShadowProvenance(
            scope.source_id,
            profile.evidence_file.file_id,
            fingerprint(profile.structural_fingerprint),
            discovery.semantic_fingerprint,
            tuple(item.mapping.decision_id for item in bindings),
            tuple(run.normalization_run_id for run in normalization_runs),
            capability.assessment_id if capability else None,
            tuple(item.authorization_id for item in capability.execution_authorizations)
            if capability
            else (),
        )
        result = ShadowAnalysisResult(
            "shadow-run-" + identity[:24],
            scope_key,
            "EXISTING_PROSPECT_PIPELINE",
            (
                ShadowStatus.SHADOW_FAILED
                if any(item.status is StageStatus.FAILED for item in stages)
                else ShadowStatus.SHADOW_BLOCKED
                if capability is None
                else ShadowStatus.SHADOW_COMPLETE
            ),
            tuple(stages),
            profile,
            discovery,
            normalization_runs,
            capability,
            tuple(warning.code.value for warning in profile.warnings),
            provenance,
            versions,
            len(request.content),
            profile.logical_data_row_count,
            len(profile.sheets),
            _elapsed(total_start),
            identity,
            started_at,
            completed_at,
        )
        runtime = None
        if capability is not None:
            planner = AnalyticalQueryPlanner(
                capability_repository=capability_repository, clock=self.clock
            )
            executor = AggregationExecutor(
                capability_repository=capability_repository, clock=self.clock
            )
            composer = GovernedAnswerComposer(
                capability_repository=capability_repository,
                plan_repository=planner.repository,
                aggregation_repository=executor.repository,
                clock=self.clock,
            )
            runtime = _Runtime(
                capability_repository, normalization_runs, planner, executor, composer
            )
        return self.repository.store_analysis(result, runtime)

    def run_shadow_question(self, analysis, question, *, caller_id=None):
        runtime = self.repository.runtime(analysis.shadow_run_id)
        if runtime is None or analysis.capability_assessment is None:
            raise PermissionError("shadow analysis is unavailable, purged, or blocked")
        scope = analysis.capability_assessment.scope
        catalog = build_concept_catalog(runtime.capability_repository, scope)
        if catalog is None:
            raise PermissionError("current governed concept catalog is unavailable")
        stages = []
        tick = perf_counter()
        question_identity = fingerprint(analysis.fingerprint, question, caller_id)
        contract = NaturalLanguageQuestion(
            "shadow-question-input-" + question_identity[:24],
            question,
            scope,
            caller_id,
            "SHADOW",
            "pue-natural-language-question-1",
            self.clock(),
        )
        interpretation = DeterministicAnalyticalInterpreter(clock=self.clock).interpret(
            contract, catalog
        )
        interpretation_status = (
            StageStatus.COMPLETED
            if interpretation.status is InterpretationStatus.INTERPRETED
            else StageStatus.BLOCKED
        )
        stages.append(
            _stage(
                ShadowStage.INTERPRETATION,
                interpretation_status,
                tick,
                tuple(item.value for item in interpretation.reason_codes),
                (interpretation.interpretation_id,),
            )
        )

        planning = None
        aggregation_result = None
        if (
            interpretation.status is InterpretationStatus.INTERPRETED
            and interpretation.primary_intent is not None
        ):
            tick = perf_counter()
            planning = runtime.planner.plan(interpretation.primary_intent)
            plan_status = (
                StageStatus.COMPLETED
                if planning.plan.planning_status is PlanningStatus.READY
                else StageStatus.BLOCKED
            )
            stages.append(
                _stage(
                    ShadowStage.PLANNING,
                    plan_status,
                    tick,
                    tuple(item.value for item in planning.plan.reason_codes),
                    (planning.plan.plan_id,),
                )
            )
            if (
                planning.plan.planning_status is PlanningStatus.READY
                and planning.aggregation_request is not None
            ):
                tick = perf_counter()
                try:
                    aggregation_result = runtime.executor.execute(
                        planning.aggregation_request,
                        analysis.capability_assessment,
                        runtime.normalization_runs,
                    )
                except Exception as error:  # noqa: BLE001 - shadow boundary contains stage failure
                    stages.append(
                        _stage(
                            ShadowStage.EXECUTION,
                            StageStatus.FAILED,
                            tick,
                            (type(error).__name__,),
                        )
                    )
                else:
                    stages.append(
                        _stage(
                            ShadowStage.EXECUTION,
                            StageStatus.COMPLETED,
                            tick,
                            references=(aggregation_result.result_id,),
                        )
                    )
            else:
                stages.append(
                    _stage(
                        ShadowStage.EXECUTION,
                        StageStatus.SKIPPED,
                        perf_counter(),
                        ("PLANNING_NOT_READY",),
                    )
                )
        else:
            stages.extend(
                (
                    _stage(
                        ShadowStage.PLANNING,
                        StageStatus.SKIPPED,
                        perf_counter(),
                        ("INTERPRETATION_NOT_READY",),
                    ),
                    _stage(
                        ShadowStage.EXECUTION,
                        StageStatus.SKIPPED,
                        perf_counter(),
                        ("INTERPRETATION_NOT_READY",),
                    ),
                )
            )

        tick = perf_counter()
        answer = runtime.composer.compose(
            interpretation,
            planning.plan if planning is not None else None,
            aggregation_result,
        )
        stages.append(
            _stage(
                ShadowStage.ANSWER_COMPOSITION,
                StageStatus.COMPLETED,
                tick,
                tuple(item.value for item in answer.reason_codes),
                (answer.answer_id,),
            )
        )
        final = self._question_status(interpretation, planning, answer)
        identity = fingerprint(
            analysis.fingerprint,
            interpretation.fingerprint,
            planning.plan.plan_fingerprint if planning else None,
            aggregation_result.result_fingerprint if aggregation_result else None,
            answer.fingerprint,
            final,
        )
        provenance = replace(
            analysis.provenance,
            interpretation_id=interpretation.interpretation_id,
            analytical_plan_id=planning.plan.plan_id if planning else None,
            aggregation_result_id=aggregation_result.result_id if aggregation_result else None,
            answer_id=answer.answer_id,
        )
        result = ShadowQuestionResult(
            "shadow-question-" + identity[:24],
            analysis.shadow_run_id,
            question,
            interpretation,
            planning,
            aggregation_result,
            answer,
            tuple(stages),
            final,
            tuple(item.value for item in answer.reason_codes),
            provenance,
            identity,
        )
        return self.repository.store_question(result)

    @staticmethod
    def _validate_bindings(request, discovery, bindings):
        discoveries = {item.provenance.column_id: item for item in discovery.columns}
        errors = []
        for binding in bindings:
            mapping = binding.mapping
            current = request.decision_repository.effective(mapping.scope)
            discovered = discoveries.get(mapping.scope.column_id)
            if current is None or current.decision_id != mapping.decision_id:
                errors.append("MAPPING_NOT_EFFECTIVE")
            if discovered is None:
                errors.append("COLUMN_NOT_DISCOVERED")
            elif mapping.provenance.semantic_fingerprint != discovery.semantic_fingerprint:
                errors.append("SEMANTIC_PROVENANCE_MISMATCH")
        return tuple(dict.fromkeys(errors))

    @staticmethod
    def _question_status(interpretation, planning, answer):
        if interpretation.status is InterpretationStatus.AMBIGUOUS:
            return ShadowStatus.SHADOW_COMPLETE_WITH_AMBIGUOUS_QUERY
        if interpretation.status is not InterpretationStatus.INTERPRETED:
            return ShadowStatus.SHADOW_COMPLETE_WITH_UNSUPPORTED_QUERY
        if planning is None or planning.plan.planning_status is not PlanningStatus.READY:
            return ShadowStatus.SHADOW_COMPLETE_WITH_BLOCKED_QUERY
        if answer.answer_state.value in {"FAILED", "BLOCKED"}:
            return ShadowStatus.SHADOW_FAILED
        return ShadowStatus.SHADOW_COMPLETE

    @staticmethod
    def _versions(profile, discovery, runs):
        return PipelineVersions(
            profile.profiler_version,
            discovery.ontology_version,
            discovery.classifier_version,
            "pue-governance-policy-1",
            runs[0].normalization_policy_version if runs else NormalizationPolicy().version,
            CoveragePolicy().version,
            CapabilityPolicy().execution_authorization_version,
            CapabilityPolicy().version,
            AggregationExecutionPolicy().version,
            AnalyticalPlanningPolicy().version,
            InterpretationPolicy().version,
            AnswerCompositionPolicy().version,
            SHADOW_ORCHESTRATOR_VERSION,
        )
