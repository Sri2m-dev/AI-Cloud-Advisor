"""PUE-005 capability evaluation without analytical execution."""

from __future__ import annotations

from universal_evidence.capability.authorization import (
    build_alignments,
    build_authorizations,
    build_record_basis,
)
from universal_evidence.capability.coverage import assess_coverage, scope_from_runs
from universal_evidence.capability.dimensions import qualify_dimensions
from universal_evidence.capability.fingerprint import fingerprint
from universal_evidence.capability.measures import qualify_measures
from universal_evidence.capability.models import (
    CapabilityAssessment,
    CapabilityProvenance,
    CapabilityState,
    EvidenceCapability,
    ReasonCode,
)
from universal_evidence.capability.policy import CapabilityPolicy, CoveragePolicy
from universal_evidence.capability.registry import (
    CAPABILITY_REGISTRY_VERSION,
    DEFAULT_CAPABILITY_REGISTRY,
    CapabilityDefinition,
)
from universal_evidence.capability.repository import InMemoryCapabilityRepository
from universal_evidence.normalization import NormalizationRun, NormalizationStatus


def _merge_provenance(items) -> CapabilityProvenance:
    provenances = tuple(item.provenance for item in items)
    return CapabilityProvenance(
        tuple(sorted({value for item in provenances for value in item.normalization_run_ids})),
        tuple(sorted({value for item in provenances for value in item.normalized_field_ids})),
        tuple(sorted({value for item in provenances for value in item.normalized_fingerprints})),
        tuple(sorted({value for item in provenances for value in item.mapping_decision_ids})),
        tuple(sorted({value for item in provenances for value in item.source_references})),
    )


class CapabilityEvaluator:
    def __init__(
        self,
        *,
        coverage_policy: CoveragePolicy | None = None,
        capability_policy: CapabilityPolicy | None = None,
        registry: tuple[CapabilityDefinition, ...] = DEFAULT_CAPABILITY_REGISTRY,
        repository: InMemoryCapabilityRepository | None = None,
    ) -> None:
        self.coverage_policy = coverage_policy or CoveragePolicy()
        self.capability_policy = capability_policy or CapabilityPolicy()
        self.registry = registry
        self.repository = repository or InMemoryCapabilityRepository()

    def evaluate(self, runs: tuple[NormalizationRun, ...]) -> CapabilityAssessment:
        scope = scope_from_runs(runs)
        coverage = assess_coverage(runs, self.coverage_policy)
        dimensions = qualify_dimensions(coverage, self.coverage_policy, self.capability_policy)
        measures = qualify_measures(runs, coverage, self.coverage_policy, self.capability_policy)
        capabilities = tuple(
            self._evaluate_capability(definition, scope, coverage, dimensions, measures, runs)
            for definition in self.registry
        )
        record_basis = build_record_basis(runs, scope, self.capability_policy)
        alignments = build_alignments(runs, scope, measures, dimensions, self.capability_policy)
        assessment_fingerprint = fingerprint(
            scope.key,
            tuple(item.fingerprint for item in coverage),
            tuple(item.fingerprint for item in dimensions),
            tuple(item.fingerprint for item in measures),
            tuple(item.fingerprint for item in capabilities),
            record_basis.fingerprint,
            tuple(item.fingerprint for item in alignments),
            self.coverage_policy.version,
            self.capability_policy.version,
            CAPABILITY_REGISTRY_VERSION,
        )
        assessment_id = "capability-assessment-" + assessment_fingerprint[:24]
        authorizations = build_authorizations(
            assessment_id,
            assessment_fingerprint,
            scope,
            capabilities,
            measures,
            dimensions,
            alignments,
            record_basis,
            self.capability_policy,
        )
        assessment = CapabilityAssessment(
            assessment_id,
            scope,
            coverage,
            dimensions,
            measures,
            capabilities,
            record_basis,
            alignments,
            authorizations,
            self.coverage_policy.version,
            self.capability_policy.version,
            assessment_fingerprint,
        )
        return self.repository.store(assessment)

    def _evaluate_capability(
        self, definition, scope, coverage, dimensions, measures, runs
    ) -> EvidenceCapability:
        supported_dimensions = tuple(
            item for item in dimensions if item.state is CapabilityState.SUPPORTED
        )
        supported_measure = next(
            (
                item
                for item in measures
                if item.state is CapabilityState.SUPPORTED
                and item.aggregation_eligibility is CapabilityState.SUPPORTED
            ),
            None,
        )
        any_measure = next(
            (item for item in measures if item.state is CapabilityState.SUPPORTED), None
        )
        support_items = []
        reasons = []
        state = CapabilityState.SUPPORTED
        dimension_by_concept = {item.semantic_concept_id: item for item in dimensions}
        for requirement in definition.requirements:
            if requirement.requirement_type == "COVERAGE":
                if coverage:
                    support_items.extend(coverage)
                else:
                    state = CapabilityState.NOT_SUPPORTED
                    reasons.append(ReasonCode.NO_GOVERNED_EVIDENCE)
            elif requirement.requirement_type == "ANY_DIMENSION":
                eligible_dimensions = supported_dimensions
                if definition.name == "MONETARY_TOTAL_BY_DIMENSION" and any_measure:
                    eligible_dimensions = self._row_compatible_dimensions(
                        runs,
                        tuple(
                            item
                            for item in supported_dimensions
                            if item.semantic_concept_id != "financial.currency"
                        ),
                        any_measure.semantic_concept_id,
                    )
                if eligible_dimensions:
                    support_items.extend(eligible_dimensions)
                else:
                    state = (
                        CapabilityState.BLOCKED
                        if supported_dimensions
                        else CapabilityState.NOT_SUPPORTED
                    )
                    reasons.append(
                        ReasonCode.ROW_BINDING_INCOMPLETE
                        if supported_dimensions
                        else ReasonCode.REQUIRED_DIMENSION_MISSING
                    )
            elif requirement.requirement_type == "TIME_DIMENSION":
                temporal = tuple(
                    item
                    for item in supported_dimensions
                    if any(
                        fragment in item.semantic_concept_id
                        for fragment in self.capability_policy.time_concept_fragments
                    )
                )
                eligible_temporal = temporal
                if definition.name == "MONETARY_TREND" and any_measure:
                    eligible_temporal = self._row_compatible_dimensions(
                        runs, temporal, any_measure.semantic_concept_id
                    )
                if eligible_temporal:
                    support_items.extend(eligible_temporal)
                else:
                    state = CapabilityState.BLOCKED if temporal else CapabilityState.NOT_SUPPORTED
                    reasons.append(
                        ReasonCode.ROW_BINDING_INCOMPLETE
                        if temporal
                        else ReasonCode.REQUIRED_TIME_DIMENSION_MISSING
                    )
            elif requirement.requirement_type == "MONETARY_MEASURE":
                if supported_measure:
                    support_items.append(supported_measure)
                else:
                    state = (
                        CapabilityState.BLOCKED if any_measure else CapabilityState.NOT_SUPPORTED
                    )
                    reasons.append(ReasonCode.REQUIRED_MEASURE_MISSING)
                    if any_measure:
                        reasons.extend(any_measure.reason_codes)
            elif requirement.requirement_type == "CURRENCY_GROUPING":
                mixed = next(
                    (
                        item
                        for item in measures
                        if item.state is CapabilityState.SUPPORTED
                        and len(item.detected_currencies) > 1
                        and item.row_binding_ratio >= self.coverage_policy.minimum_row_binding_ratio
                    ),
                    None,
                )
                if mixed:
                    support_items.append(mixed)
                else:
                    state = CapabilityState.NOT_SUPPORTED
                    reasons.append(ReasonCode.MIXED_CURRENCY)
            elif requirement.requirement_type == "FX":
                state = CapabilityState.NOT_SUPPORTED
                reasons.append(ReasonCode.FX_NOT_SUPPORTED)
            elif requirement.requirement_type == "CONCEPT":
                dimension = dimension_by_concept.get(requirement.semantic_concept_id)
                if dimension and dimension.state is CapabilityState.SUPPORTED:
                    support_items.append(dimension)
                else:
                    state = CapabilityState.NOT_SUPPORTED
                    reasons.append(ReasonCode.REQUIRED_DIMENSION_MISSING)
        if state is CapabilityState.SUPPORTED:
            reasons.append(ReasonCode.CAPABILITY_PREREQUISITES_MET)
        if support_items:
            provenance = _merge_provenance(support_items)
        elif coverage:
            provenance = _merge_provenance(coverage)
        else:
            provenance = CapabilityProvenance((), (), (), (), ())
        identity = fingerprint(
            scope.key,
            definition.name,
            state,
            definition.requirements,
            tuple(item.fingerprint for item in support_items),
            tuple(reasons),
            self.coverage_policy.version,
            self.capability_policy.version,
            CAPABILITY_REGISTRY_VERSION,
        )
        return EvidenceCapability(
            "capability-" + identity[:24],
            definition.name,
            scope,
            state,
            definition.requirements,
            tuple(item.coverage_id for item in support_items if hasattr(item, "coverage_id")),
            tuple(item.dimension_id for item in support_items if hasattr(item, "dimension_id")),
            tuple(item.measure_id for item in support_items if hasattr(item, "measure_id")),
            tuple(dict.fromkeys(reasons)),
            self.capability_policy.version,
            provenance,
            identity,
        )

    @staticmethod
    def _row_compatible_dimensions(runs, dimensions, measure_concept_id):
        valid = {NormalizationStatus.NORMALIZED, NormalizationStatus.UNCHANGED}

        def row_key(record):
            reference = record.row_reference
            return (
                record.source_id,
                record.file_id,
                record.sheet_id,
                reference.row_numbers,
                reference.row_range,
                reference.lineage_expression,
            )

        records = tuple(record for run in runs for record in run.records)
        measure_rows = {
            row_key(record)
            for record in records
            if record.semantic_concept_id == measure_concept_id
            and record.normalization_status in valid
        }
        return tuple(
            dimension
            for dimension in dimensions
            if measure_rows
            <= {
                row_key(record)
                for record in records
                if record.semantic_concept_id == dimension.semantic_concept_id
                and record.normalization_status in valid
            }
        )
