"""Certified package governed coverage composition."""

from universal_evidence.capability import CapabilityState, CoverageState
from universal_evidence.pilot.evidence_package_coverage import (
    assess_package_governed_coverage,
)


class _Coverage:
    def __init__(
        self,
        concept,
        state,
        observed,
        valid,
        invalid=0,
    ):
        self.semantic_concept_id = concept
        self.coverage_state = state
        self.observed_records = observed
        self.normalized_records = observed
        self.valid_records = valid
        self.invalid_records = invalid
        self.coverage_ratio = valid / observed if observed else 0.0
        self.validity_ratio = valid / observed if observed else 0.0
        self.mapping_decision_ids = ("decision-1",)
        self.normalization_run_ids = ("run-1",)


class _Capability:
    def __init__(self, state):
        self.state = state


class _Assessment:
    assessment_id = "assessment-1"

    coverage = (
        _Coverage(
            "financial.cost.total",
            CoverageState.EVIDENCED,
            10,
            10,
        ),
        _Coverage(
            "financial.currency",
            CoverageState.PARTIAL,
            10,
            8,
            2,
        ),
        _Coverage(
            "resource.identifier",
            CoverageState.NOT_EVIDENCED,
            0,
            0,
        ),
    )

    capabilities = (
        _Capability(CapabilityState.SUPPORTED),
        _Capability(CapabilityState.BLOCKED),
    )


class _Evaluator:
    def __init__(self):
        self.received = None

    def evaluate(self, runs):
        self.received = runs
        return _Assessment()


class _Normalization:
    def __init__(self):
        self.capabilities = _Evaluator()


def test_package_coverage_uses_existing_capability_authority():
    normalization = _Normalization()
    runs = ("run-a", "run-b")

    result = assess_package_governed_coverage(
        normalization_service=normalization,
        runs=runs,
    )

    assert normalization.capabilities.received == runs
    assert result.assessment_id == "assessment-1"
    assert result.governed_concept_count == 2
    assert result.evidenced_concept_count == 1
    assert result.partial_concept_count == 1
    assert result.blocked_concept_count == 0
    assert result.concept_evidence_ratio == 0.5


def test_not_evidenced_zero_observation_is_not_counted_as_governed():
    result = assess_package_governed_coverage(
        normalization_service=_Normalization(),
        runs=("run-a",),
    )

    concepts = {item.semantic_concept_id for item in result.concept_coverage}

    assert "resource.identifier" not in concepts


def test_coverage_preserves_authoritative_ratios_and_provenance():
    result = assess_package_governed_coverage(
        normalization_service=_Normalization(),
        runs=("run-a",),
    )

    cost = next(
        item
        for item in result.concept_coverage
        if item.semantic_concept_id == "financial.cost.total"
    )

    assert cost.coverage_state == CoverageState.EVIDENCED.value
    assert cost.observed_records == 10
    assert cost.valid_records == 10
    assert cost.coverage_ratio == 1.0
    assert cost.mapping_decision_ids == ("decision-1",)
    assert cost.normalization_run_ids == ("run-1",)


def test_capability_summary_preserves_existing_states():
    result = assess_package_governed_coverage(
        normalization_service=_Normalization(),
        runs=("run-a",),
    )

    assert result.supported_capability_count == 1
    assert result.partial_capability_count == 0
    assert result.blocked_capability_count == 1


def test_empty_runs_fail_closed():
    try:
        assess_package_governed_coverage(
            normalization_service=_Normalization(),
            runs=(),
        )
    except PermissionError as exc:
        assert "governed normalization" in str(exc)
    else:
        raise AssertionError("empty package runs must fail closed")
