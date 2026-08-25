"""PUE-005 coverage/capability certification and negative-boundary tests."""

from __future__ import annotations

from dataclasses import fields
from datetime import datetime, timedelta, timezone

import pytest

from universal_evidence.capability import (
    CapabilityEvaluator,
    CapabilityPolicy,
    CapabilityState,
    CoveragePolicy,
    CoverageState,
    ReasonCode,
)
from universal_evidence.contracts import (
    EvidenceAnalysisContext,
    EvidenceRowReference,
    EvidenceSource,
)
from universal_evidence.governance import (
    ActorType,
    ConfirmationActor,
    ConfirmationService,
)
from universal_evidence.normalization import AuthorizedSourceValue, NormalizationService
from universal_evidence.profiling import profile_evidence
from universal_evidence.semantic import discover_semantics

NOW = datetime(2026, 8, 25, 12, 0, tzinfo=timezone.utc)


def source(
    *,
    analysis_id: str = "analysis-cap-1",
    prospect_id: str = "prospect-cap-1",
    organization_id: str | None = None,
    tenant_id: str | None = None,
) -> EvidenceSource:
    context = EvidenceAnalysisContext(
        analysis_id,
        "source-cap-1",
        prospect_id,
        organization_id,
        tenant_id,
    )
    return EvidenceSource(context, "authorized:source-cap-1", NOW, NOW + timedelta(days=30))


def actor() -> ConfirmationActor:
    return ConfirmationActor("user-1", "reviewer@example.test", "finance", ActorType.HUMAN)


def normalized_runs(
    content: bytes,
    mappings: dict[str, tuple[str, list[object]]],
    *,
    evidence_source: EvidenceSource | None = None,
):
    profile = profile_evidence(
        source=evidence_source or source(), filename="mixed.csv", content=content
    )
    discovery = discover_semantics(profile)
    runs = []
    for header, (concept_id, values) in mappings.items():
        column = next(item for item in discovery.columns if item.original_header == header)
        governance = ConfirmationService(clock=lambda: NOW)
        governance.override_mapping(
            discovery,
            column.source_column_reference,
            concept_id,
            actor=actor(),
            reason="governed fixture mapping",
        )
        mapping = governance.get_effective_mapping(column, actor=actor())
        assert mapping is not None
        context = EvidenceAnalysisContext(
            mapping.scope.analysis_id,
            mapping.scope.source_id,
            mapping.scope.prospect_id,
            mapping.scope.organization_id,
            mapping.scope.tenant_id,
        )
        rows = [
            AuthorizedSourceValue(
                EvidenceRowReference(
                    context,
                    mapping.scope.file_id,
                    mapping.scope.sheet_id,
                    row_numbers=(index + 2,),
                ),
                value,
            )
            for index, value in enumerate(values)
        ]
        runs.append(
            NormalizationService(
                decision_repository=governance.repository, clock=lambda: NOW
            ).normalize(mapping, rows)
        )
    return tuple(runs)


def coverage(assessment, concept_id: str):
    return next(item for item in assessment.coverage if item.semantic_concept_id == concept_id)


def capability(assessment, name: str):
    return next(item for item in assessment.capabilities if item.capability_name == name)


def measure(assessment, concept_id: str = "financial.cost.total"):
    return next(item for item in assessment.measures if item.semantic_concept_id == concept_id)


def test_service_and_cost_without_currency_separates_presence_from_aggregation():
    runs = normalized_runs(
        b"Service,Cost\nEC2,100\nRDS,50\n",
        {
            "Service": ("technology.service", ["EC2", "RDS"]),
            "Cost": ("financial.cost.total", ["100", "50"]),
        },
    )
    assessment = CapabilityEvaluator().evaluate(runs)
    assert coverage(assessment, "technology.service").coverage_state is CoverageState.EVIDENCED
    assert coverage(assessment, "financial.cost.total").coverage_state is CoverageState.EVIDENCED
    assert coverage(assessment, "financial.currency").coverage_state is CoverageState.NOT_EVIDENCED
    assert measure(assessment).state is CapabilityState.SUPPORTED
    assert measure(assessment).aggregation_eligibility is CapabilityState.BLOCKED
    assert ReasonCode.UNIT_NOT_EVIDENCED in measure(assessment).reason_codes
    assert capability(assessment, "MONETARY_TOTAL").state is CapabilityState.BLOCKED


def test_single_currency_measure_and_dimension_capabilities_are_supported():
    runs = normalized_runs(
        b"Service,Cost,Currency\nEC2,100,USD\nRDS,50,USD\n",
        {
            "Service": ("technology.service", ["EC2", "RDS"]),
            "Cost": ("financial.cost.total", ["100", "50"]),
            "Currency": ("financial.currency", ["USD", "USD"]),
        },
    )
    assessment = CapabilityEvaluator().evaluate(runs)
    governed_measure = measure(assessment)
    assert governed_measure.detected_currencies == ("USD",)
    assert governed_measure.aggregation_eligibility is CapabilityState.SUPPORTED
    assert capability(assessment, "MONETARY_TOTAL").state is CapabilityState.SUPPORTED
    assert capability(assessment, "MONETARY_TOTAL_BY_DIMENSION").state is CapabilityState.SUPPORTED
    assert not hasattr(capability(assessment, "MONETARY_TOTAL"), "result")


def test_mixed_currency_blocks_single_total_but_allows_currency_grouping():
    runs = normalized_runs(
        b"Service,Cost,Currency\nEC2,100,USD\nRDS,200,INR\n",
        {
            "Service": ("technology.service", ["EC2", "RDS"]),
            "Cost": ("financial.cost.total", ["100", "200"]),
            "Currency": ("financial.currency", ["USD", "INR"]),
        },
    )
    assessment = CapabilityEvaluator().evaluate(runs)
    governed_measure = measure(assessment)
    assert governed_measure.detected_currencies == ("INR", "USD")
    assert governed_measure.aggregation_eligibility is CapabilityState.BLOCKED
    assert ReasonCode.MIXED_CURRENCY in governed_measure.reason_codes
    assert capability(assessment, "MONETARY_TOTAL").state is CapabilityState.BLOCKED
    assert capability(assessment, "CURRENCY_GROUPED_TOTAL").state is CapabilityState.SUPPORTED
    assert capability(assessment, "FX_NORMALIZED_TOTAL").state is CapabilityState.NOT_SUPPORTED
    assert ReasonCode.FX_NOT_SUPPORTED in capability(assessment, "FX_NORMALIZED_TOTAL").reason_codes


def test_poor_quality_cost_evidence_is_present_but_not_measure_sufficient():
    values = [str(index) for index in range(60)] + ["bad"] * 40
    rows = "".join(f"{value},USD\n" for value in values)
    runs = normalized_runs(
        ("Cost,Currency\n" + rows).encode(),
        {
            "Cost": ("financial.cost.total", values),
            "Currency": ("financial.currency", ["USD"] * 100),
        },
    )
    assessment = CapabilityEvaluator().evaluate(runs)
    cost = coverage(assessment, "financial.cost.total")
    assert cost.observed_records == 100
    assert cost.invalid_records == 40
    assert cost.coverage_state is CoverageState.PARTIAL
    assert measure(assessment).state is CapabilityState.BLOCKED
    assert capability(assessment, "MONETARY_TOTAL").state is CapabilityState.NOT_SUPPORTED


def test_rich_mixed_evidence_inventory_spans_governed_domains():
    headers = (
        "Provider,Service,Resource ID,Region,Application,Owner,Cost Center,"
        "Usage Date,Cost,Currency,Contract Renewal Date,Notes\n"
    )
    data = (
        "AWS,EC2,i-1,us-east-1,Checkout,Alice,CC10,2026-01-01,100,USD,"
        "2026-12-31,review\n"
        "Azure,VM,vm-2,eastus,ERP,Bob,CC20,2026-01-02,200,USD,"
        "31/12/2026,review\n"
    )
    runs = normalized_runs(
        (headers + data).encode(),
        {
            "Provider": ("cloud.provider", ["AWS", "Azure"]),
            "Service": ("technology.service", ["EC2", "VM"]),
            "Resource ID": ("resource.identifier", ["i-1", "vm-2"]),
            "Region": ("geography.region", ["us-east-1", "eastus"]),
            "Application": ("application.name", ["Checkout", "ERP"]),
            "Owner": ("ownership.owner", ["Alice", "Bob"]),
            "Cost Center": ("organization.cost_center", ["CC10", "CC20"]),
            "Usage Date": ("contract.start_date", ["2026-01-01", "2026-01-02"]),
            "Cost": ("financial.cost.total", ["100", "200"]),
            "Currency": ("financial.currency", ["USD", "USD"]),
            "Contract Renewal Date": (
                "contract.renewal_date",
                ["2026-12-31", "31/12/2026"],
            ),
        },
    )
    assessment = CapabilityEvaluator().evaluate(runs)
    evidenced = {
        item.semantic_concept_id
        for item in assessment.coverage
        if item.coverage_state is CoverageState.EVIDENCED
    }
    assert {
        "cloud.provider",
        "technology.service",
        "resource.identifier",
        "geography.region",
        "application.name",
        "ownership.owner",
        "organization.cost_center",
        "contract.start_date",
        "financial.cost.total",
        "financial.currency",
        "contract.renewal_date",
    } <= evidenced
    assert capability(assessment, "RESOURCE_INVENTORY").state is CapabilityState.SUPPORTED
    assert capability(assessment, "APPLICATION_INVENTORY").state is CapabilityState.SUPPORTED
    assert capability(assessment, "OWNER_INVENTORY").state is CapabilityState.SUPPORTED
    assert capability(assessment, "REGION_INVENTORY").state is CapabilityState.SUPPORTED
    assert capability(assessment, "TIME_RANGE_ANALYSIS").state is CapabilityState.SUPPORTED


def test_row_binding_must_be_complete_for_currency_qualified_measure():
    runs = normalized_runs(
        b"Cost,Currency\n100,USD\n200,\n",
        {
            "Cost": ("financial.cost.total", ["100", "200"]),
            "Currency": ("financial.currency", ["USD", ""]),
        },
    )
    governed_measure = measure(CapabilityEvaluator().evaluate(runs))
    assert governed_measure.row_binding_ratio == 0.5
    assert governed_measure.aggregation_eligibility is CapabilityState.BLOCKED
    assert ReasonCode.ROW_BINDING_INCOMPLETE in governed_measure.reason_codes


def test_measure_by_dimension_requires_compatible_source_rows():
    runs = normalized_runs(
        b"Service,Cost,Currency\nEC2,100,USD\n,200,USD\n",
        {
            "Service": ("technology.service", ["EC2", ""]),
            "Cost": ("financial.cost.total", ["100", "200"]),
            "Currency": ("financial.currency", ["USD", "USD"]),
        },
    )
    assessment = CapabilityEvaluator(
        coverage_policy=CoveragePolicy(
            minimum_coverage_ratio=0.5,
            minimum_validity_ratio=0.5,
            minimum_dimension_validity_ratio=0.5,
        )
    ).evaluate(runs)
    result = capability(assessment, "MONETARY_TOTAL_BY_DIMENSION")
    assert result.state is CapabilityState.BLOCKED
    assert ReasonCode.ROW_BINDING_INCOMPLETE in result.reason_codes


def test_capability_provenance_traces_to_normalized_fields_and_mapping_decisions():
    runs = normalized_runs(
        b"Service\nEC2\n",
        {"Service": ("technology.service", ["EC2"])},
    )
    assessment = CapabilityEvaluator().evaluate(runs)
    result = capability(assessment, "DESCRIBE_AVAILABLE_EVIDENCE")
    assert result.provenance.normalization_run_ids == (runs[0].normalization_run_id,)
    assert result.provenance.normalized_field_ids == (runs[0].records[0].normalized_field_id,)
    assert result.provenance.mapping_decision_ids == (runs[0].records[0].mapping_decision_id,)


def test_analysis_and_tenant_scope_change_capability_identity():
    fingerprints = []
    for analysis_id, tenant_id in (("analysis-a", "tenant-a"), ("analysis-b", "tenant-b")):
        runs = normalized_runs(
            b"Service\nEC2\n",
            {"Service": ("technology.service", ["EC2"])},
            evidence_source=source(
                analysis_id=analysis_id,
                prospect_id="prospect",
                organization_id="org",
                tenant_id=tenant_id,
            ),
        )
        fingerprints.append(CapabilityEvaluator().evaluate(runs).fingerprint)
    assert fingerprints[0] != fingerprints[1]


def test_cross_scope_runs_are_rejected_not_merged():
    first = normalized_runs(
        b"Service\nEC2\n",
        {"Service": ("technology.service", ["EC2"])},
        evidence_source=source(analysis_id="analysis-a"),
    )
    second = normalized_runs(
        b"Service\nRDS\n",
        {"Service": ("technology.service", ["RDS"])},
        evidence_source=source(analysis_id="analysis-b"),
    )
    with pytest.raises(PermissionError, match="conflicting evidence scope"):
        CapabilityEvaluator().evaluate(first + second)


def test_same_inputs_are_idempotent_and_policy_drift_creates_new_identity():
    runs = normalized_runs(
        b"Service\nEC2\n",
        {"Service": ("technology.service", ["EC2"])},
    )
    evaluator = CapabilityEvaluator()
    first = evaluator.evaluate(runs)
    repeated = evaluator.evaluate(runs)
    changed = CapabilityEvaluator(
        coverage_policy=CoveragePolicy(version="pue-coverage-policy-2")
    ).evaluate(runs)
    changed_capability = CapabilityEvaluator(
        capability_policy=CapabilityPolicy(version="pue-capability-policy-2")
    ).evaluate(runs)
    assert first is repeated
    assert first.fingerprint != changed.fingerprint
    assert first.fingerprint != changed_capability.fingerprint


def test_184_cost_records_establish_coverage_but_do_not_emit_total():
    values = ["1"] * 183 + [str(861_828 - 183)]
    runs = normalized_runs(
        ("Cost\n" + "\n".join(values) + "\n").encode(),
        {"Cost": ("financial.cost.total", values)},
    )
    assessment = CapabilityEvaluator().evaluate(runs)
    cost = coverage(assessment, "financial.cost.total")
    assert cost.observed_records == cost.valid_records == 184
    assert cost.coverage_state is CoverageState.EVIDENCED
    assert capability(assessment, "MONETARY_TOTAL").state is CapabilityState.BLOCKED
    assert not hasattr(assessment, "total_cost")
    assert "861828" not in repr(assessment)


def test_contracts_contain_no_execution_entity_graph_or_ai_outputs():
    runs = normalized_runs(
        b"Service,Cost,Currency\nEC2,10,USD\n",
        {
            "Service": ("technology.service", ["EC2"]),
            "Cost": ("financial.cost.total", ["10"]),
            "Currency": ("financial.currency", ["USD"]),
        },
    )
    assessment = CapabilityEvaluator().evaluate(runs)
    names = {field.name for field in fields(type(assessment))}
    forbidden = {
        "result",
        "total",
        "average",
        "ranking",
        "entity",
        "relationship",
        "graph_edge",
        "recommendation",
        "answer",
    }
    assert names.isdisjoint(forbidden)
