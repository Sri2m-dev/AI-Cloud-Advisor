"""ACT-004 adapter from admitted rows and effective mappings to PUE-004 normalization."""

from __future__ import annotations

from universal_evidence.activation import (
    ActivationScope,
    ActivationStage,
    RoutingReason,
    ScopeLevel,
)
from universal_evidence.capability import CapabilityEvaluator, CapabilityState
from universal_evidence.contracts import EvidenceAnalysisContext, EvidenceRowReference
from universal_evidence.normalization import (
    AuthorizedSourceValue,
    NormalizationService,
    NormalizationStatus,
)
from universal_evidence.normalization.fingerprints import fingerprint
from universal_evidence.pilot.admission import admitted_source_rows
from universal_evidence.pilot.normalization_view_models import (
    GovernedNormalizationViewModel,
    NormalizationPlan,
    NormalizationPlanItem,
    NormalizationQualitySummary,
    ObservationQuality,
)


class PilotGovernedNormalizationService:
    def __init__(
        self,
        *,
        activation_resolver,
        semantic_service,
        confirmation_service,
        telemetry,
        operations=None,
        operation_context=None,
    ):
        self.activation_resolver = activation_resolver
        self.semantic_service = semantic_service
        self.confirmation_service = confirmation_service
        self.telemetry = telemetry
        self.operations = operations
        self.operation_context = operation_context
        self.normalization = NormalizationService(
            decision_repository=confirmation_service.repository
        )
        self.capabilities = CapabilityEvaluator()

    def plan(self, admission, *, actor):
        discovery = self.semantic_service.discovery(admission)
        items = []
        decision_ids = []
        for column in discovery.columns:
            effective = self.confirmation_service.get_effective_mapping(column, actor=actor)
            stale = False
            if effective is not None:
                decision = next(
                    item
                    for item in self.confirmation_service.get_decision_history(
                        column, actor=actor
                    ).decisions
                    if item.decision_id == effective.decision_id
                )
                stale = self.confirmation_service.detect_drift(
                    decision, discovery
                ).requires_reevaluation
            eligible = effective is not None and not stale
            concept = effective.semantic_concept_id if eligible else None
            if eligible:
                decision_ids.append(effective.decision_id)
            items.append(
                NormalizationPlanItem(
                    column.source_column_reference,
                    column.original_header,
                    concept,
                    self._proposed_type(concept),
                    eligible,
                    ObservationQuality.VALID if eligible else ObservationQuality.BLOCKED,
                    "Normalize each admitted detail-row value using the ontology primitive type.",
                    "Effective governed mapping authorizes normalization."
                    if eligible
                    else "No current effective governed mapping authorizes normalization.",
                )
            )
        governance_fingerprint = fingerprint(tuple(sorted(decision_ids)))
        plan_fingerprint = fingerprint(
            admission.evidence_fingerprint, governance_fingerprint, tuple(items)
        )
        return NormalizationPlan(
            admission.scope.analysis_id,
            admission.evidence_fingerprint,
            governance_fingerprint,
            tuple(items),
            plan_fingerprint,
        )

    def experience(self, admission, *, actor):
        activation = self.activation_resolver.resolve(
            ActivationScope(
                ScopeLevel.ANALYSIS,
                organization_id=admission.scope.organization_id,
                tenant_id=admission.scope.tenant_id,
                prospect_id=admission.scope.prospect_id,
                analysis_id=admission.scope.analysis_id,
            )
        )
        if (
            RoutingReason.KILL_SWITCH_ACTIVE in activation.reason_codes
            or activation.stage is ActivationStage.SHADOW_ONLY
        ):
            return None
        plan = self.plan(admission, actor=actor)
        if activation.stage < ActivationStage.CAPABILITY_VISIBLE:
            return self._view(plan, (), executed=False)
        runs = self.execute(admission, plan=plan, actor=actor)
        return self._view(plan, runs, executed=True)

    def execute(self, admission, *, plan=None, actor):
        from time import perf_counter

        from universal_evidence.operations import GovernedEventType, observe, workflow_context

        context = workflow_context(self.operation_context, admission.scope, actor=actor)
        started = perf_counter()
        observe(
            self.operations,
            GovernedEventType.NORMALIZATION_STARTED,
            context,
            audit=False,
            references={"evidence": admission.evidence_fingerprint},
        )
        current_plan = self.plan(admission, actor=actor)
        if plan is not None and plan.fingerprint != current_plan.fingerprint:
            observe(
                self.operations,
                GovernedEventType.NORMALIZATION_BLOCKED,
                context,
                audit=False,
                outcome="BLOCKED",
                references={"evidence": admission.evidence_fingerprint},
            )
            raise PermissionError("normalization plan is stale for current evidence or governance")
        plan = current_plan
        discovery = self.semantic_service.discovery(admission)
        rows_by_sheet = admitted_source_rows(admission)
        runs = []
        for planned in plan.items:
            if not planned.eligible:
                continue
            column = next(
                item
                for item in discovery.columns
                if item.source_column_reference == planned.column_reference
            )
            mapping = self.confirmation_service.get_effective_mapping(column, actor=actor)
            if mapping is None:
                continue
            values = self._values(admission, mapping, rows_by_sheet)
            runs.append(self.normalization.normalize(mapping, values))
        self.telemetry.increment("normalization_run_count", admission.scope.key, len(runs))
        self.telemetry.increment(
            "normalized_observation_count",
            admission.scope.key,
            sum(run.processed_count for run in runs),
        )
        observe(
            self.operations,
            GovernedEventType.NORMALIZATION_COMPLETED,
            context,
            audit=False,
            duration_ms=(perf_counter() - started) * 1000,
            references={
                "evidence": admission.evidence_fingerprint,
                "governance": plan.governance_fingerprint,
                "plan": plan.fingerprint,
            },
            attributes={
                "runs": len(runs),
                "records": sum(run.processed_count for run in runs),
            },
        )
        return tuple(runs)

    @staticmethod
    def _values(admission, mapping, rows_by_sheet):
        sheet_index = next(
            index
            for index, sheet in enumerate(admission.profile.sheets)
            if sheet.sheet.sheet_id == mapping.scope.sheet_id
        )
        sheet_profile = admission.profile.sheets[sheet_index]
        column = next(
            item.column
            for item in sheet_profile.columns
            if item.column.column_id == mapping.scope.column_id
        )
        region = next(
            item
            for item in admission.regions
            if item.sheet_id == mapping.scope.sheet_id and item.region_kind == "PRIMARY_DETAIL"
        )
        context = EvidenceAnalysisContext(
            mapping.scope.analysis_id,
            mapping.scope.source_id,
            mapping.scope.prospect_id,
            mapping.scope.organization_id,
            mapping.scope.tenant_id,
        )
        rows = rows_by_sheet[sheet_index]
        return tuple(
            AuthorizedSourceValue(
                EvidenceRowReference(
                    context,
                    mapping.scope.file_id,
                    mapping.scope.sheet_id,
                    row_numbers=(row_number,),
                ),
                rows[row_number - 1][column.ordinal - 1]
                if column.ordinal <= len(rows[row_number - 1])
                else None,
            )
            for row_number in range((region.header_row or region.start_row) + 1, region.end_row + 1)
        )

    def _view(self, plan, runs, *, executed):
        records = tuple(record for run in runs for record in run.records)
        qualities = tuple(self._quality(record.normalization_status) for record in records)
        summary = NormalizationQualitySummary(
            qualities.count(ObservationQuality.VALID),
            qualities.count(ObservationQuality.INVALID),
            qualities.count(ObservationQuality.MISSING),
            sum(not item.eligible for item in plan.items),
            qualities.count(ObservationQuality.UNSUPPORTED),
        )
        currency_partitions = tuple(
            sorted(
                {
                    str(record.normalized_value)
                    for record in records
                    if record.semantic_concept_id == "financial.currency"
                    and self._quality(record.normalization_status) is ObservationQuality.VALID
                }
            )
        )
        total_state = "BLOCKED"
        total_reason = (
            "Governed amount and compatible governed currency prerequisites are incomplete."
        )
        if runs:
            assessment = self.capabilities.evaluate(runs)
            total = next(
                (
                    item
                    for item in assessment.capabilities
                    if item.capability_name == "MONETARY_TOTAL"
                ),
                None,
            )
            if total is not None:
                # ACT-004 never authorizes or presents an executive numerical result.
                total_reason = "; ".join(reason.value for reason in total.reason_codes)
                if total.state is CapabilityState.SUPPORTED:
                    total_reason = (
                        "Prerequisites observed; numerical execution is not authorized by ACT-004."
                    )
        view_fingerprint = fingerprint(
            plan.fingerprint, tuple(run.fingerprint for run in runs), summary, currency_partitions
        )
        return GovernedNormalizationViewModel(
            plan,
            executed,
            len(records),
            summary,
            tuple(run.normalization_run_id for run in runs),
            total_state,
            total_reason,
            currency_partitions,
            view_fingerprint,
        )

    @staticmethod
    def _quality(status):
        if status in {NormalizationStatus.NORMALIZED, NormalizationStatus.UNCHANGED}:
            return ObservationQuality.VALID
        if status is NormalizationStatus.INVALID:
            return ObservationQuality.INVALID
        if status is NormalizationStatus.SKIPPED:
            return ObservationQuality.MISSING
        if status is NormalizationStatus.UNSUPPORTED:
            return ObservationQuality.UNSUPPORTED
        return ObservationQuality.BLOCKED

    def _proposed_type(self, concept_id):
        if concept_id is None:
            return None
        definition = next(
            item
            for item in self.confirmation_service.registry.concepts
            if item.concept.concept_id == concept_id
        )
        return "/".join(definition.concept.expected_primitive_types)
