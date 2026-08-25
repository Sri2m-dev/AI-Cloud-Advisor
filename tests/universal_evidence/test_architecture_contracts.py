"""PUE-000 contract invariants only; no parsing or application integration."""

from dataclasses import fields
from datetime import datetime, timedelta, timezone

import pytest

from universal_evidence.contracts import (
    AggregationCapability,
    AggregationCapabilityState,
    AvailabilityStatus,
    ClassificationState,
    ConfidenceBand,
    ConfirmationRecord,
    ConfirmationState,
    DerivedEvidenceResult,
    EvidenceAnalysisContext,
    EvidenceCoverage,
    EvidenceProvenance,
    EvidenceRowReference,
    GovernedMeasure,
    MappingConfidence,
    QueryCapability,
    QueryCapabilityState,
    SemanticCandidate,
    SemanticClassificationResult,
    StructuralObservation,
)

NOW = datetime.now(timezone.utc)
CONTEXT = EvidenceAnalysisContext("analysis-1", "source-1", "prospect-1")


def confidence(score=0.62):
    return MappingConfidence(
        score, ConfidenceBand.MEDIUM, "contract-test", ("header", "profile"),
        "classifier-1", "policy-1", NOW
    )


def provenance():
    rows = EvidenceRowReference(CONTEXT, "file-1", "sheet-1", row_range=(2, 185))
    return EvidenceProvenance(
        "source-1", "file-1", "sheet-1", ("column-1",), (rows,),
        ("mapping-1",), (1,), ("classifier-1",), (), "analysis-1",
        normalized_record_ids=("normalized-1",),
    )


def test_structural_observation_has_no_semantic_assignment_contract():
    names = {item.name for item in fields(StructuralObservation)}
    assert "semantic_concept_id" not in names
    assert "semantic_mapping" not in names


def test_semantic_classification_supports_multiple_candidates():
    candidates = (
        SemanticCandidate("ownership.team", 1, confidence(0.62)),
        SemanticCandidate("organization.support_group", 1, confidence(0.29)),
    )
    result = SemanticClassificationResult(
        "classification-1", CONTEXT, "column-1", candidates,
        ClassificationState.CONFIRMATION_REQUIRED,
        ConfirmationRecord(ConfirmationState.REQUIRED), NOW,
    )
    assert len(result.candidates) == 2


def test_user_confirmed_is_not_engine_classification_without_confirmation():
    with pytest.raises(ValueError, match="confirmed provenance"):
        SemanticClassificationResult(
            "classification-1", CONTEXT, "column-1", (),
            ClassificationState.USER_CONFIRMED,
            ConfirmationRecord(ConfirmationState.NOT_REQUIRED), NOW,
        )


def test_provenance_links_file_sheet_column_and_rows():
    trace = provenance()
    assert (trace.file_id, trace.sheet_id, trace.column_ids) == (
        "file-1", "sheet-1", ("column-1",)
    )
    assert trace.row_references[0].row_range == (2, 185)


def test_derived_result_requires_normalized_evidence_references():
    with pytest.raises(ValueError, match="normalized evidence"):
        DerivedEvidenceResult(
            "result-1", CONTEXT, "aggregate", 10, (), ("financial.cost.total",),
            "sum", provenance(), "SUFFICIENT", (), NOW,
        )


def test_supported_query_requires_measure_and_dimension_evidence():
    with pytest.raises(ValueError, match="every governed input"):
        QueryCapability(
            CONTEXT, QueryCapabilityState.SUPPORTED, "ec2_spend",
            ("financial.cost.total",), ("technology.service",),
            ("financial.cost.total",), (), ("technology.service",),
        )


@pytest.mark.parametrize("currency_resolved,mixed", [(False, False), (True, True)])
def test_unresolved_or_mixed_currency_blocks_supported_aggregation(currency_resolved, mixed):
    measure = GovernedMeasure(
        "financial.cost.total", ("mapping-1",), 1.0,
        ConfirmationState.NOT_REQUIRED, "money", "USD" if currency_resolved else None,
        currency_resolved, mixed,
    )
    with pytest.raises(ValueError, match="currency"):
        AggregationCapability(
            CONTEXT, AggregationCapabilityState.SUPPORTED, measure, (), (),
            "rows:2-185", "sum", (), provenance(),
        )


@pytest.mark.parametrize("status,coverage", [
    (AvailabilityStatus.PARTIAL, 0.63),
    (AvailabilityStatus.NOT_EVIDENCED, 0.0),
])
def test_coverage_represents_partial_and_not_evidenced(status, coverage):
    item = EvidenceCoverage(
        CONTEXT, "ownership.owner", status, coverage, None,
        ConfirmationState.NOT_REQUIRED, 1, 1,
    )
    assert item.availability_status is status


def test_analysis_isolation_fields_are_mandatory():
    with pytest.raises(ValueError, match="analysis_id"):
        EvidenceAnalysisContext("", "source-1", "prospect-1")


def test_row_reference_requires_one_unambiguous_selector():
    with pytest.raises(ValueError, match="exactly one"):
        EvidenceRowReference(CONTEXT, "file-1", "sheet-1")
