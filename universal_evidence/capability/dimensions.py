"""Governed dimension qualification without entity resolution."""

from universal_evidence.capability.fingerprint import fingerprint
from universal_evidence.capability.models import (
    CapabilityState,
    CoverageState,
    DimensionValueType,
    EvidenceCoverage,
    GovernedDimension,
    ReasonCode,
)
from universal_evidence.capability.policy import CapabilityPolicy, CoveragePolicy
from universal_evidence.normalization import NormalizationStatus

VALID = {NormalizationStatus.NORMALIZED, NormalizationStatus.UNCHANGED}

TYPE_ALIASES = {"CURRENCY_CODE": DimensionValueType.STRING}
OPERATOR_POLICY = {
    DimensionValueType.STRING: ("EQUALS", "NOT_EQUALS", "IN"),
    DimensionValueType.INTEGER: ("EQUALS", "NOT_EQUALS", "IN"),
    DimensionValueType.DECIMAL: ("EQUALS", "NOT_EQUALS", "IN"),
    DimensionValueType.BOOLEAN: ("EQUALS",),
    DimensionValueType.DATE: ("EQUALS", "DATE_FROM", "DATE_TO"),
    DimensionValueType.DATETIME: ("EQUALS", "DATE_FROM", "DATE_TO"),
}


def qualify_dimensions(
    runs,
    coverage: tuple[EvidenceCoverage, ...],
    coverage_policy: CoveragePolicy,
    capability_policy: CapabilityPolicy,
) -> tuple[GovernedDimension, ...]:
    results = []
    for item in coverage:
        concept = item.semantic_concept_id
        if concept in capability_policy.monetary_measure_concepts:
            continue
        if concept in capability_policy.non_dimension_concepts:
            continue
        normalized_types = {
            TYPE_ALIASES.get(record.normalized_type, record.normalized_type)
            for run in runs
            for record in run.records
            if record.semantic_concept_id == concept
            and record.normalization_status in VALID
            and record.normalized_type is not None
        }
        certified_type = None
        if len(normalized_types) == 1:
            candidate = next(iter(normalized_types))
            try:
                certified_type = DimensionValueType(candidate)
            except ValueError:
                certified_type = None
        type_certified = certified_type is not None
        eligible = (
            item.coverage_state is CoverageState.EVIDENCED
            and item.validity_ratio >= coverage_policy.minimum_dimension_validity_ratio
            and type_certified
        )
        state = CapabilityState.SUPPORTED if eligible else CapabilityState.BLOCKED
        reasons = (
            (ReasonCode.DIMENSION_ELIGIBLE, ReasonCode.DIMENSION_VALUE_TYPE_CERTIFIED)
            if eligible
            else (
                ReasonCode.DIMENSION_VALUE_TYPE_CONFLICT
                if not type_certified
                else ReasonCode.BELOW_VALIDITY_THRESHOLD,
            )
        )
        operators = OPERATOR_POLICY.get(certified_type, ()) if eligible else ()
        identity = fingerprint(
            item.scope.key,
            concept,
            item.fingerprint,
            coverage_policy.version,
            capability_policy.version,
            certified_type,
            operators,
            capability_policy.dimension_value_policy_version,
            state,
        )
        results.append(
            GovernedDimension(
                "dimension-" + identity[:24],
                concept,
                item.scope,
                item.coverage_id,
                state,
                item.distinct_count,
                certified_type,
                operators,
                eligible,
                capability_policy.dimension_value_policy_version,
                reasons,
                capability_policy.version,
                item.provenance,
                identity,
            )
        )
    return tuple(results)
