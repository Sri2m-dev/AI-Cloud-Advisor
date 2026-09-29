"""Authoritative governed coverage for certified evidence packages.

This module composes existing Universal Evidence normalization and
capability contracts.  It does not create a competing coverage model.
"""

from __future__ import annotations

from dataclasses import dataclass

from universal_evidence.capability import CapabilityState, CoverageState


@dataclass(frozen=True)
class PackageConceptCoverage:
    semantic_concept_id: str
    coverage_state: str
    observed_records: int
    normalized_records: int
    valid_records: int
    invalid_records: int
    coverage_ratio: float
    validity_ratio: float
    mapping_decision_ids: tuple[str, ...]
    normalization_run_ids: tuple[str, ...]


@dataclass(frozen=True)
class PackageGovernedCoverage:
    assessment_id: str
    concept_coverage: tuple[PackageConceptCoverage, ...]
    governed_concept_count: int
    evidenced_concept_count: int
    partial_concept_count: int
    blocked_concept_count: int
    supported_capability_count: int
    partial_capability_count: int
    blocked_capability_count: int

    @property
    def concept_evidence_ratio(self) -> float:
        """Summary of governed concepts reaching EVIDENCED state.

        This is a concept-level summary, not a row-level evidence percentage.
        """
        if not self.governed_concept_count:
            return 0.0
        return self.evidenced_concept_count / self.governed_concept_count


def assess_package_governed_coverage(
    *,
    normalization_service,
    runs,
) -> PackageGovernedCoverage:
    """Evaluate package runs through the existing capability authority."""

    runs = tuple(runs)

    if not runs:
        raise PermissionError("governed normalization is required for package coverage")

    assessment = normalization_service.capabilities.evaluate(runs)

    concept_coverage = tuple(
        PackageConceptCoverage(
            semantic_concept_id=item.semantic_concept_id,
            coverage_state=item.coverage_state.value,
            observed_records=item.observed_records,
            normalized_records=item.normalized_records,
            valid_records=item.valid_records,
            invalid_records=item.invalid_records,
            coverage_ratio=item.coverage_ratio,
            validity_ratio=item.validity_ratio,
            mapping_decision_ids=item.mapping_decision_ids,
            normalization_run_ids=item.normalization_run_ids,
        )
        for item in assessment.coverage
        if item.observed_records > 0
    )

    evidenced = sum(
        1 for item in concept_coverage if item.coverage_state == CoverageState.EVIDENCED.value
    )

    partial = sum(
        1 for item in concept_coverage if item.coverage_state == CoverageState.PARTIAL.value
    )

    blocked = sum(
        1
        for item in concept_coverage
        if item.coverage_state
        in {
            CoverageState.BLOCKED.value,
            CoverageState.CONFLICTED.value,
            CoverageState.INSUFFICIENT.value,
        }
    )

    supported_capabilities = sum(
        1 for item in assessment.capabilities if item.state is CapabilityState.SUPPORTED
    )

    partial_capabilities = sum(
        1 for item in assessment.capabilities if item.state is CapabilityState.PARTIALLY_SUPPORTED
    )

    blocked_capabilities = sum(
        1
        for item in assessment.capabilities
        if item.state
        in {
            CapabilityState.BLOCKED,
            CapabilityState.NOT_SUPPORTED,
            CapabilityState.UNKNOWN,
        }
    )

    return PackageGovernedCoverage(
        assessment_id=assessment.assessment_id,
        concept_coverage=concept_coverage,
        governed_concept_count=len(concept_coverage),
        evidenced_concept_count=evidenced,
        partial_concept_count=partial,
        blocked_concept_count=blocked,
        supported_capability_count=supported_capabilities,
        partial_capability_count=partial_capabilities,
        blocked_capability_count=blocked_capabilities,
    )
