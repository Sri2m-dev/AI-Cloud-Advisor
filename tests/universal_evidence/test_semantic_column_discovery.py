"""PUE-002 semantic discovery and non-authority acceptance tests."""

from __future__ import annotations

from dataclasses import fields
from datetime import datetime, timedelta, timezone
from time import perf_counter

import pytest

from services.prospect_data_intake_service import normalize_upload
from shared.prospect_answers import prospect_evidence_answer
from universal_evidence.contracts import (
    ClassificationState,
    ConfirmationState,
    EvidenceAnalysisContext,
    EvidenceSource,
)
from universal_evidence.profiling import profile_evidence
from universal_evidence.semantic import (
    DiscoveryConfig,
    SemanticRisk,
    discover_semantics,
)


def source() -> EvidenceSource:
    now = datetime(2026, 8, 25, 12, 0, tzinfo=timezone.utc)
    context = EvidenceAnalysisContext(
        "analysis-sem-1", "source-sem-1", "prospect-sem-1"
    )
    return EvidenceSource(
        context, "authorized:source-sem-1", now, now + timedelta(days=30)
    )


def discover(content: bytes, filename: str = "evidence.csv"):
    profile = profile_evidence(source=source(), filename=filename, content=content)
    return discover_semantics(profile)


def column(result, header: str):
    return next(item for item in result.columns if item.original_header == header)


def candidate(result, concept_id: str):
    return next(
        item for item in result.candidates if item.semantic_concept_id == concept_id
    )


def test_exact_alias_match_produces_explainable_candidate():
    result = column(discover(b"Currency\nUSD\nUSD\nEUR\nEUR\n"), "Currency")
    found = candidate(result, "financial.currency")
    assert found.confidence.score >= 0.9
    assert found.confidence.band.value == "HIGH"
    assert any(
        signal.signal_type == "HEADER_ALIAS" for signal in found.supporting_signals
    )


def test_tokenized_alias_match_preserves_original_header():
    result = column(
        discover(b"Observed Monthly Cost Value\n1.5\n2.5\n3.5\n"),
        "Observed Monthly Cost Value",
    )
    assert result.original_header == "Observed Monthly Cost Value"
    assert any(
        item.semantic_concept_id == "financial.cost.monthly"
        for item in result.candidates
    )


def test_primitive_and_role_compatibility_support_cost_candidate():
    result = column(discover(b"Cost\n1.5\n2.5\n3.5\n"), "Cost")
    found = candidate(result, "financial.cost.total")
    signal_types = {signal.signal_type for signal in found.supporting_signals}
    assert {"PRIMITIVE_COMPATIBLE", "STRUCTURAL_ROLE_COMPATIBLE"} <= signal_types


@pytest.mark.parametrize(
    "content",
    [
        b"Cost\nhigh\nmedium\nlow\n",
        b"Renewal Date\n100\n200\n300\n",
        b"Owner\n0.72\n0.18\n0.33\n",
    ],
)
def test_primitive_contradictions_prevent_strong_header_only_claims(content):
    result = discover(content).columns[0]
    assert result.classification_state in {
        ClassificationState.UNCLASSIFIED,
        ClassificationState.CANDIDATE,
        ClassificationState.CONFIRMATION_REQUIRED,
    }
    assert not result.candidates or result.candidates[0].confidence.score < 0.7


def test_safe_sample_shape_support_is_explicit_but_not_value_normalization():
    result = column(discover(b"Provider\nAWS\nAzure\nGCP\n"), "Provider")
    found = candidate(result, "cloud.provider")
    assert any(
        signal.signal_type == "SAFE_SAMPLE_SHAPE" for signal in found.supporting_signals
    )
    assert not hasattr(found, "normalized_values")


def test_sheet_local_column_context_weakly_increases_score():
    isolated = candidate(
        column(discover(b"Service\nCompute\nStorage\nDatabase\n"), "Service"),
        "technology.service",
    )
    contextual = candidate(
        column(
            discover(b"Service,Region\nCompute,east\nStorage,west\nDatabase,east\n"),
            "Service",
        ),
        "technology.service",
    )
    assert contextual.confidence.score > isolated.confidence.score
    assert any(
        signal.signal_type == "SHEET_LOCAL_CONTEXT"
        for signal in contextual.supporting_signals
    )


def test_ambiguous_group_retains_multiple_candidates_and_requires_confirmation():
    result = column(discover(b"Group\nAlpha\nAlpha\nBeta\nBeta\n"), "Group")
    concepts = {item.semantic_concept_id for item in result.candidates}
    assert {"ownership.team", "organization.department"} <= concepts
    assert result.classification_state is ClassificationState.CONFIRMATION_REQUIRED
    assert result.confirmation_state is ConfirmationState.REQUIRED
    assert any("ambiguity gap" in reason for reason in result.confirmation_reasons)


@pytest.mark.parametrize("header", ["Name", "ID", "Value", "Type", "Status", "Date"])
def test_generic_headers_never_auto_classify(header):
    result = column(discover(f"{header}\nalpha\nbeta\ngamma\n".encode()), header)
    assert result.classification_state is not ClassificationState.AUTO_CLASSIFIED


def test_unknown_is_a_successful_result():
    result = column(discover(b"Mystery Zorb\na\nb\nc\n"), "Mystery Zorb")
    assert result.classification_state is ClassificationState.UNCLASSIFIED
    assert result.candidates == ()


def test_high_confidence_does_not_mean_human_confirmed():
    result = column(discover(b"Currency\nUSD\nUSD\nEUR\nEUR\n"), "Currency")
    assert result.classification_state is ClassificationState.AUTO_CLASSIFIED
    assert result.confirmation_state is ConfirmationState.NOT_REQUIRED
    assert result.classification_state is not ClassificationState.USER_CONFIRMED


def test_high_risk_cost_requires_confirmation_even_at_high_confidence():
    result = column(discover(b"Cost,Currency\n1,USD\n2,USD\n3,EUR\n"), "Cost")
    found = candidate(result, "financial.cost.total")
    assert found.confidence.score >= 0.9
    assert found.risk is SemanticRisk.HIGH_RISK
    assert result.classification_state is ClassificationState.CONFIRMATION_REQUIRED
    assert any("risk policy" in reason for reason in result.confirmation_reasons)


def test_explanations_versions_and_provenance_are_complete():
    result = column(
        discover(b"Renewal\n2026-01-01\n2026-02-01\n2026-03-01\n"), "Renewal"
    )
    found = candidate(result, "contract.renewal_date")
    assert found.supporting_signals
    assert "Supporting:" in found.explanation and "Contradicting:" in found.explanation
    assert found.semantic_concept_version == 1
    assert result.classifier_version == "pue-002.1"
    assert result.ontology_version == "pue-ontology-1"
    assert result.policy_version == "pue-semantic-policy-1"
    assert result.provenance.analysis_id == "analysis-sem-1"
    assert result.provenance.file_id
    assert result.provenance.sheet_id
    assert result.provenance.column_id == result.source_column_reference
    assert result.provenance.structural_profile_fingerprint


def test_semantic_discovery_is_deterministic():
    profile = profile_evidence(
        source=source(), filename="same.csv", content=b"Service,Cost\nA,1\nB,2\nC,3\n"
    )
    first = discover_semantics(profile)
    second = discover_semantics(profile)
    assert first.semantic_fingerprint == second.semantic_fingerprint
    assert first.columns == second.columns


def test_filename_alone_never_classifies_provider():
    result = discover(b"Mystery\na\nb\nc\n", filename="aws_cur_january.csv")
    assert all(
        candidate.semantic_concept_id != "cloud.provider"
        for item in result.columns
        for candidate in item.candidates
    )


def test_ec2_value_does_not_create_vendor_or_value_level_semantics():
    result = column(
        discover(
            b"Resource Reference\ni-0123456789abcdef\ni-2222222222222222\ni-3333333333333333\n"
        ),
        "Resource Reference",
    )
    assert all(
        "aws" not in item.semantic_concept_id and "ec2" not in item.semantic_concept_id
        for item in result.candidates
    )
    assert not hasattr(result, "entities")


def test_ec2_cost_classifies_column_hypothesis_only():
    result = column(discover(b"EC2 Cost\n10\n20\n30\n"), "EC2 Cost")
    assert any(
        item.semantic_concept_id.startswith("financial.cost.")
        for item in result.candidates
    )
    assert all(
        "ec2" not in item.semantic_concept_id and "aws" not in item.semantic_concept_id
        for item in result.candidates
    )


def test_application_owner_creates_candidates_not_relationships():
    result = column(
        discover(b"Application Owner\nTeam A\nTeam B\nTeam C\n"), "Application Owner"
    )
    assert any(
        item.semantic_concept_id.startswith("ownership.") for item in result.candidates
    )
    assert not hasattr(result, "relationships")
    assert not hasattr(result, "semantic_mapping")


def test_no_normalization_aggregation_query_or_ai_authority_surface():
    result = discover(b"Service,Cost\nEC2,10\nS3,20\nRDS,30\n")
    result_fields = {item.name for item in fields(type(result))}
    assert not result_fields.intersection(
        {"normalized_evidence", "total_spend", "query_capability", "answers"}
    )
    assert prospect_evidence_answer is not None


def test_mixed_format_columns_produce_cross_dimension_candidates():
    content = (
        b"Account,Service,Resource,Region,Owner,Department,Cost Center,Monthly Value,"
        b"License Count,Usage Percentage,Renewal,Environment,Notes\n"
        b"a1,Compute,r1,east,Team A,IT,CC1,10,5,80,2026-01-01,prod,n1\n"
        b"a2,Storage,r2,west,Team B,Finance,CC2,20,6,70,2026-02-01,uat,n2\n"
        b"a3,Database,r3,east,Team A,IT,CC1,30,7,60,2026-03-01,dev,n3\n"
    )
    result = discover(content)
    dimensions = {
        candidate.dimension for item in result.columns for candidate in item.candidates
    }
    assert {
        "FINANCIAL",
        "CLOUD",
        "OWNERSHIP",
        "ORGANIZATION",
        "CONTRACT",
        "TAGGING",
    } <= dimensions
    assert result.unclassified_column_count >= 1


def test_184_row_discovery_does_not_change_authoritative_analysis_shape():
    costs = ["1"] * 183 + [str(861_828 - 183)]
    content = (
        "provider,service,cost\n" + "".join(f"AWS,EC2,{cost}\n" for cost in costs)
    ).encode()
    before = normalize_upload(
        "AWS billing/CUR-derived CSV", "CUR Jan 2026.csv", content
    )
    profile = profile_evidence(
        source=source(), filename="CUR Jan 2026.csv", content=content
    )
    discovery = discover_semantics(profile)
    after = normalize_upload("AWS billing/CUR-derived CSV", "CUR Jan 2026.csv", content)
    assert column(discovery, "service").candidates
    assert column(discovery, "cost").candidates
    assert not hasattr(discovery, "total_spend")
    assert float(before["cost"].sum()) == float(after["cost"].sum()) == 861_828
    assert before["currency"].isna().all() and after["currency"].isna().all()


def test_custom_policy_can_require_confirmation_without_changing_score():
    profile = profile_evidence(
        source=source(), filename="data.csv", content=b"Environment\nprod\nuat\ndev\n"
    )
    default = discover_semantics(profile)
    restricted = discover_semantics(
        profile,
        config=DiscoveryConfig(confirm_risks=(SemanticRisk.LOW_RISK,)),
    )
    assert (
        default.columns[0].candidates[0].confidence.score
        == restricted.columns[0].candidates[0].confidence.score
    )
    assert restricted.columns[0].confirmation_state is ConfirmationState.REQUIRED


def test_500_column_discovery_has_bounded_runtime():
    headers = [f"Unknown Field {index}" for index in range(500)]
    content = (
        ",".join(headers) + "\n" + ",".join("x" for _ in headers) + "\n"
    ).encode()
    profile = profile_evidence(source=source(), filename="wide.csv", content=content)
    started = perf_counter()
    result = discover_semantics(profile)
    duration = perf_counter() - started
    assert len(result.columns) == 500
    assert duration < 5.0
