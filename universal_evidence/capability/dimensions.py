"""Governed dimension qualification without entity resolution."""

from universal_evidence.capability.fingerprint import fingerprint
from universal_evidence.capability.models import (
    CapabilityState,
    CoverageState,
    EvidenceCoverage,
    GovernedDimension,
    ReasonCode,
)
from universal_evidence.capability.policy import CapabilityPolicy, CoveragePolicy


def qualify_dimensions(
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
        eligible = (
            item.coverage_state is CoverageState.EVIDENCED
            and item.validity_ratio >= coverage_policy.minimum_dimension_validity_ratio
        )
        state = CapabilityState.SUPPORTED if eligible else CapabilityState.BLOCKED
        reasons = (
            (ReasonCode.DIMENSION_ELIGIBLE,) if eligible else (ReasonCode.BELOW_VALIDITY_THRESHOLD,)
        )
        identity = fingerprint(
            item.scope.key,
            concept,
            item.fingerprint,
            coverage_policy.version,
            capability_policy.version,
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
                reasons,
                capability_policy.version,
                item.provenance,
                identity,
            )
        )
    return tuple(results)
