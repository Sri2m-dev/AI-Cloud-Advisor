"""PUE-004 governed row-level normalization and negative-boundary tests."""

from __future__ import annotations

from dataclasses import fields, replace
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace

import pytest

from shared.prospect_answers import prospect_evidence_answer
from universal_evidence.contracts import (
    EvidenceAnalysisContext,
    EvidenceDimension,
    EvidenceRowReference,
    EvidenceSource,
    SemanticConcept,
)
from universal_evidence.governance import (
    ActorType,
    ConfirmationActor,
    ConfirmationService,
    EffectiveSemanticMapping,
    MappingDecisionState,
)
from universal_evidence.normalization import (
    AuthorizedSourceValue,
    InMemoryNormalizedEvidenceRepository,
    NormalizationPolicy,
    NormalizationRunStatus,
    NormalizationService,
    NormalizationStatus,
    NormalizationWarning,
    NormalizerRegistry,
)
from universal_evidence.normalization.normalizers import (
    normalize_boolean,
    normalize_date,
    normalize_datetime,
    normalize_decimal,
    normalize_integer,
    normalize_string,
)
from universal_evidence.profiling import StructuralRole, profile_evidence
from universal_evidence.semantic import SemanticRisk, discover_semantics
from universal_evidence.semantic.models import ConceptDefinition
from universal_evidence.semantic.registry import ConceptRegistry

NOW = datetime(2026, 8, 25, 12, 0, tzinfo=timezone.utc)


def source(
    *,
    analysis_id: str = "analysis-norm-1",
    prospect_id: str = "prospect-norm-1",
    organization_id: str | None = None,
    tenant_id: str | None = None,
) -> EvidenceSource:
    context = EvidenceAnalysisContext(
        analysis_id,
        "source-norm-1",
        prospect_id,
        organization_id,
        tenant_id,
    )
    return EvidenceSource(context, "authorized:source-norm-1", NOW, NOW + timedelta(days=30))


def discover(content: bytes, *, evidence_source: EvidenceSource | None = None):
    profile = profile_evidence(
        source=evidence_source or source(), filename="evidence.csv", content=content
    )
    return discover_semantics(profile)


def column(result, header: str):
    return next(item for item in result.columns if item.original_header == header)


def actor(role: str = "finance") -> ConfirmationActor:
    return ConfirmationActor("user-1", "reviewer@example.test", role, ActorType.HUMAN)


def governed_mapping(
    content: bytes,
    header: str,
    concept_id: str,
    *,
    evidence_source: EvidenceSource | None = None,
    override: bool = False,
):
    result = discover(content, evidence_source=evidence_source)
    item = column(result, header)
    governance = ConfirmationService(clock=lambda: NOW)
    if override:
        governance.override_mapping(
            result,
            item.source_column_reference,
            concept_id,
            actor=actor(),
            reason="reviewed semantic override",
        )
    else:
        governance.request_confirmation(result, item.source_column_reference, concept_id)
        governance.confirm_mapping(result, item.source_column_reference, concept_id, actor=actor())
    effective = governance.get_effective_mapping(item, actor=actor())
    assert effective is not None
    return result, item, governance, effective


def row(mapping: EffectiveSemanticMapping, number: int, value, **kwargs):
    scope = mapping.scope
    context = EvidenceAnalysisContext(
        scope.analysis_id,
        scope.source_id,
        scope.prospect_id,
        scope.organization_id,
        scope.tenant_id,
    )
    reference = EvidenceRowReference(context, scope.file_id, scope.sheet_id, row_numbers=(number,))
    return AuthorizedSourceValue(reference, value, **kwargs)


def service(governance: ConfirmationService, **kwargs) -> NormalizationService:
    return NormalizationService(
        decision_repository=governance.repository, clock=lambda: NOW, **kwargs
    )


def effective_from_decision(decision) -> EffectiveSemanticMapping:
    return EffectiveSemanticMapping(
        decision.scope,
        decision.semantic_concept_id,
        decision.decision_state,
        decision.decision_id,
        None,
        decision.actor,
        decision.provenance,
    )


def test_effective_mapping_is_mandatory_and_confidence_alone_cannot_normalize():
    result = discover(b"Cost\n10\n")
    item = column(result, "Cost")
    governance = ConfirmationService()
    fake = EffectiveSemanticMapping(
        governance._scope(item),
        "financial.cost.total",
        MappingDecisionState.CONFIRMED,
        "candidate-only",
        0.99,
        actor(),
        None,  # type: ignore[arg-type]
    )
    with pytest.raises(PermissionError, match="effective PUE-003"):
        service(governance).normalize(fake, ())


def test_confirmed_mapping_normalizes_decimal_and_preserves_source_value():
    _, _, governance, mapping = governed_mapping(b"Cost\n7.50\n", "Cost", "financial.cost.total")
    run = service(governance).normalize(mapping, [row(mapping, 2, " 7.50 ")])
    record = run.records[0]

    assert record.source_value == " 7.50 "
    assert record.normalized_value == Decimal("7.50")
    assert record.normalized_type == "DECIMAL"
    assert record.normalization_status is NormalizationStatus.NORMALIZED
    assert record.mapping_decision_id == mapping.decision_id
    assert NormalizationWarning.UNIT_UNKNOWN in record.warnings


def test_overridden_mapping_authorizes_normalization():
    _, _, governance, mapping = governed_mapping(
        b"Cost\n7.50\n",
        "Cost",
        "financial.cost.monthly",
        override=True,
    )
    run = service(governance).normalize(mapping, [row(mapping, 2, "7.50")])
    assert mapping.decision_state is MappingDecisionState.OVERRIDDEN
    assert run.records[0].normalized_value == Decimal("7.50")


def test_auto_accepted_mapping_authorizes_normalization_when_policy_permits():
    result = discover(b"Environment\nprod\ndev\n")
    observed = column(result, "Environment")
    eligible = replace(
        observed,
        classification_state=__import__(
            "universal_evidence.contracts", fromlist=["ClassificationState"]
        ).ClassificationState.AUTO_CLASSIFIED,
        confirmation_state=__import__(
            "universal_evidence.contracts", fromlist=["ConfirmationState"]
        ).ConfirmationState.NOT_REQUIRED,
        confirmation_reasons=(),
    )
    result = replace(result, columns=(eligible,))
    governance = ConfirmationService(clock=lambda: NOW)
    governance.auto_accept(result, eligible.source_column_reference)
    mapping = governance.get_effective_mapping(eligible, actor=actor())
    assert mapping is not None
    run = service(governance).normalize(mapping, [row(mapping, 2, " prod ")])
    assert run.records[0].normalized_value == "prod"


@pytest.mark.parametrize(
    "terminal_state",
    [
        MappingDecisionState.REJECTED,
        MappingDecisionState.EXPIRED,
        MappingDecisionState.SUPERSEDED,
        MappingDecisionState.PENDING
        if hasattr(MappingDecisionState, "PENDING")
        else MappingDecisionState.UNDECIDED,
    ],
)
def test_non_effective_decision_states_cannot_normalize(terminal_state):
    result = discover(b"Cost\n10\n")
    item = column(result, "Cost")
    governance = ConfirmationService(clock=lambda: NOW)
    if terminal_state is MappingDecisionState.REJECTED:
        governance.request_confirmation(
            result, item.source_column_reference, "financial.cost.total"
        )
        decision = governance.reject_mapping(
            result,
            item.source_column_reference,
            "financial.cost.total",
            actor=actor(),
            reason="not a cost",
        )
    else:
        governance.request_confirmation(
            result, item.source_column_reference, "financial.cost.total"
        )
        decision = governance.confirm_mapping(
            result, item.source_column_reference, "financial.cost.total", actor=actor()
        )
        decision = replace(decision, decision_state=terminal_state)
    mapping = effective_from_decision(decision)
    with pytest.raises(PermissionError):
        service(governance).normalize(mapping, [row(mapping, 2, "10")])


def test_superseded_mapping_cannot_authorize_new_normalization():
    result, item, governance, old = governed_mapping(b"Cost\n10\n", "Cost", "financial.cost.total")
    governance.override_mapping(
        result,
        item.source_column_reference,
        "financial.cost.monthly",
        actor=actor(),
        reason="monthly period confirmed",
    )
    with pytest.raises(PermissionError, match="superseded"):
        service(governance).normalize(old, [row(old, 2, "10")])


def test_effective_mapping_provenance_cannot_be_replaced_by_caller():
    _, _, governance, mapping = governed_mapping(b"Cost\n10\n", "Cost", "financial.cost.total")
    forged = replace(
        mapping,
        provenance=replace(mapping.provenance, ontology_version="caller-ontology"),
    )
    with pytest.raises(PermissionError, match="does not match"):
        service(governance).normalize(forged, [row(forged, 2, "10")])


@pytest.mark.parametrize(
    ("normalizer", "source_value", "expected", "normalized_type"),
    [
        (normalize_string, " EC2 ", "EC2", "STRING"),
        (normalize_decimal, "7.50", Decimal("7.50"), "DECIMAL"),
        (normalize_integer, "42", 42, "INTEGER"),
        (normalize_date, "31/12/2026", date(2026, 12, 31), "DATE"),
        (
            normalize_datetime,
            "2026-12-31T10:30:00+0530",
            datetime(2026, 12, 31, 10, 30, tzinfo=timezone(timedelta(hours=5, minutes=30))),
            "DATETIME",
        ),
        (normalize_boolean, "yes", True, "BOOLEAN"),
    ],
)
def test_primitive_normalizers_are_typed_and_deterministic(
    normalizer, source_value, expected, normalized_type
):
    normalized, actual_type, status, warnings = normalizer(source_value, NormalizationPolicy())
    assert normalized == expected
    assert actual_type == normalized_type
    assert status is NormalizationStatus.NORMALIZED
    assert warnings == ()


@pytest.mark.parametrize(
    ("normalizer", "value", "warning"),
    [
        (normalize_decimal, "bad", NormalizationWarning.NUMERIC_PARSE_FAILED),
        (normalize_date, "invalid", NormalizationWarning.DATE_PARSE_FAILED),
        (normalize_datetime, "invalid", NormalizationWarning.DATETIME_PARSE_FAILED),
        (normalize_boolean, "unknown", NormalizationWarning.BOOLEAN_PARSE_FAILED),
    ],
)
def test_invalid_primitives_remain_explicit(normalizer, value, warning):
    normalized, _, status, warnings = normalizer(value, NormalizationPolicy())
    assert normalized is None
    assert status is NormalizationStatus.INVALID
    assert warning in warnings


def test_currency_codes_use_explicit_values_only():
    _, _, governance, mapping = governed_mapping(
        b"Currency\nusd\nUSD\neur\n", "Currency", "financial.currency"
    )
    run = service(governance).normalize(
        mapping,
        [row(mapping, 2, "usd"), row(mapping, 3, "USD"), row(mapping, 4, "eur")],
    )
    assert [record.normalized_value for record in run.records] == ["USD", "USD", "EUR"]
    assert not hasattr(run, "fx_rate")


def test_null_and_invalid_cost_rows_are_preserved_in_partial_run():
    _, _, governance, mapping = governed_mapping(
        b"Cost\n10\n20\nbad\n30\n", "Cost", "financial.cost.total"
    )
    run = service(governance).normalize(
        mapping,
        [
            row(mapping, 2, "10"),
            row(mapping, 3, "20"),
            row(mapping, 4, "bad"),
            row(mapping, 5, ""),
        ],
    )
    assert run.status is NormalizationRunStatus.PARTIAL
    assert run.normalized_count == 2
    assert run.invalid_count == 1
    assert run.skipped_count == 1
    assert run.records[2].source_value == "bad"
    assert run.records[2].normalized_value is None
    assert run.records[3].normalization_status is NormalizationStatus.SKIPPED
    assert not hasattr(run, "total")


def test_row_and_decision_provenance_are_complete_and_prospect_scope_stays_absent():
    _, _, governance, mapping = governed_mapping(b"Service\nEC2\n", "Service", "technology.service")
    record = service(governance).normalize(mapping, [row(mapping, 2, " EC2 ")]).records[0]
    assert record.analysis_id == mapping.scope.analysis_id
    assert record.prospect_id == mapping.scope.prospect_id
    assert record.organization_id is None and record.tenant_id is None
    assert record.row_reference.row_numbers == (2,)
    assert record.provenance.mapping_decision_id == mapping.decision_id
    assert record.provenance.semantic_concept_id == "technology.service"


def test_mismatched_row_scope_is_rejected_instead_of_supplemented():
    _, _, governance, mapping = governed_mapping(b"Service\nEC2\n", "Service", "technology.service")
    wrong_context = EvidenceAnalysisContext("other", mapping.scope.source_id, "other")
    wrong = AuthorizedSourceValue(
        EvidenceRowReference(
            wrong_context, mapping.scope.file_id, mapping.scope.sheet_id, row_numbers=(2,)
        ),
        "EC2",
    )
    with pytest.raises(PermissionError, match="row provenance"):
        service(governance).normalize(mapping, [wrong])


def test_same_inputs_are_idempotent_and_policy_or_scope_changes_identity():
    _, _, governance, mapping = governed_mapping(
        b"Service\nEC2\n",
        "Service",
        "technology.service",
        evidence_source=source(tenant_id="tenant-a", organization_id="org-a"),
    )
    repository = InMemoryNormalizedEvidenceRepository()
    first_service = service(governance, repository=repository)
    first = first_service.normalize(mapping, [row(mapping, 2, " EC2 ")])
    repeated = first_service.normalize(mapping, [row(mapping, 2, " EC2 ")])
    revised = service(
        governance,
        repository=repository,
        policy=NormalizationPolicy(version="pue-normalization-policy-2"),
    ).normalize(mapping, [row(mapping, 2, " EC2 ")])
    assert first is repeated
    assert first.fingerprint != revised.fingerprint
    assert first.records[0].fingerprint != revised.records[0].fingerprint


def test_same_data_in_different_tenant_and_analysis_has_distinct_identity():
    identities = []
    for analysis_id, tenant_id in (("analysis-a", "tenant-a"), ("analysis-b", "tenant-b")):
        _, _, governance, mapping = governed_mapping(
            b"Service\nEC2\n",
            "Service",
            "technology.service",
            evidence_source=source(
                analysis_id=analysis_id,
                tenant_id=tenant_id,
                organization_id="org",
            ),
        )
        record = service(governance).normalize(mapping, [row(mapping, 2, "EC2")]).records[0]
        identities.append(record.fingerprint)
    assert identities[0] != identities[1]


def test_mapping_drift_creates_new_run_and_preserves_prior_version():
    result, item, governance, first_mapping = governed_mapping(
        b"Cost\n10\n", "Cost", "financial.cost.total"
    )
    repository = InMemoryNormalizedEvidenceRepository()
    normalizer = service(governance, repository=repository)
    first = normalizer.normalize(first_mapping, [row(first_mapping, 2, "10")])
    governance.override_mapping(
        result,
        item.source_column_reference,
        "financial.cost.monthly",
        actor=actor(),
        reason="monthly period confirmed",
    )
    second_mapping = governance.get_effective_mapping(item, actor=actor())
    assert second_mapping is not None
    second = normalizer.normalize(second_mapping, [row(second_mapping, 2, "10")])
    versions = repository.get_versions(tuple(str(value) for value in first_mapping.scope.key))
    assert second.supersedes_run_id == first.normalization_run_id
    assert NormalizationWarning.MAPPING_CHANGED in second.records[0].warnings
    assert len(versions) == 2
    assert versions[0].records[0].fingerprint != versions[1].records[0].fingerprint


def test_formula_is_not_evaluated_and_cached_value_requires_explicit_policy():
    _, _, governance, mapping = governed_mapping(b"Cost\n10\n", "Cost", "financial.cost.total")
    formula = row(
        mapping,
        2,
        "=A2*2",
        formula_expression="=A2*2",
        cached_formula_value="20",
    )
    blocked = service(governance).normalize(mapping, [formula]).records[0]
    permitted = (
        service(
            governance,
            policy=NormalizationPolicy(allow_cached_formula_values=True),
        )
        .normalize(mapping, [formula])
        .records[0]
    )
    assert blocked.normalization_status is NormalizationStatus.PARTIAL
    assert blocked.normalized_value is None
    assert permitted.normalized_value == Decimal("20")
    assert permitted.provenance.used_cached_formula_value


def test_duplicate_rows_are_normalized_independently_without_deduplication():
    _, _, governance, mapping = governed_mapping(
        b"Service\nEC2\nEC2\n", "Service", "technology.service"
    )
    run = service(governance).normalize(mapping, [row(mapping, 2, "EC2"), row(mapping, 3, "EC2")])
    assert len(run.records) == 2
    assert run.records[0].fingerprint != run.records[1].fingerprint


def test_unsupported_concept_normalizer_returns_unsupported_not_string_success():
    definition = ConceptDefinition(
        SemanticConcept(
            "custom.binary", 1, EvidenceDimension.TECHNOLOGY, "Binary value", ("BINARY",)
        ),
        (StructuralRole.FREE_TEXT_LIKE,),
        SemanticRisk.LOW_RISK,
    )
    registry = NormalizerRegistry(ConceptRegistry("custom-ontology-1", (definition,)))
    assert registry.normalizer("custom.binary") is None


def test_critical_negative_boundary_contains_rows_not_business_results():
    service_result, service_item, service_governance, service_mapping = governed_mapping(
        b"Service,Cost\nEC2,10\nEC2,20\nRDS,5\n",
        "Service",
        "technology.service",
    )
    _, cost_item, cost_governance, cost_mapping = governed_mapping(
        b"Service,Cost\nEC2,10\nEC2,20\nRDS,5\n",
        "Cost",
        "financial.cost.total",
    )
    del service_result, service_item, cost_item
    services = service(service_governance).normalize(
        service_mapping,
        [
            row(service_mapping, 2, "EC2"),
            row(service_mapping, 3, "EC2"),
            row(service_mapping, 4, "RDS"),
        ],
    )
    costs = service(cost_governance).normalize(
        cost_mapping,
        [row(cost_mapping, 2, "10"), row(cost_mapping, 3, "20"), row(cost_mapping, 4, "5")],
    )
    assert [record.normalized_value for record in services.records] == ["EC2", "EC2", "RDS"]
    assert [record.normalized_value for record in costs.records] == [
        Decimal("10"),
        Decimal("20"),
        Decimal("5"),
    ]
    forbidden = {"total", "average", "top_service", "query_capability", "entity_id"}
    assert forbidden.isdisjoint({field.name for field in fields(type(costs))})


def test_184_rows_normalize_individually_without_authoritative_total():
    costs = ["1"] * 183 + [str(861_828 - 183)]
    content = ("Service,Cost\n" + "".join(f"EC2,{cost}\n" for cost in costs)).encode()
    _, _, service_governance, service_mapping = governed_mapping(
        content, "Service", "technology.service"
    )
    _, _, cost_governance, cost_mapping = governed_mapping(content, "Cost", "financial.cost.total")
    service_run = service(service_governance).normalize(
        service_mapping,
        [row(service_mapping, index + 2, "EC2") for index in range(184)],
    )
    cost_run = service(cost_governance).normalize(
        cost_mapping,
        [row(cost_mapping, index + 2, value) for index, value in enumerate(costs)],
    )
    assert service_run.processed_count == service_run.normalized_count == 184
    assert cost_run.processed_count == cost_run.normalized_count == 184
    assert len(service_run.records) == len(cost_run.records) == 184
    assert not hasattr(cost_run, "total_cost")
    assert not hasattr(cost_run, "query_capability")


def test_shadow_normalization_does_not_change_ask_nexora_prospect_authority():
    analysis = SimpleNamespace(
        total_spend=861_828,
        currency="USD",
        currency_resolution_required=False,
        row_count=184,
        evidence_coverage=100.0,
    )
    before = prospect_evidence_answer("what is the total cost of EC2", analysis)
    _, _, governance, mapping = governed_mapping(b"Cost\n10\n", "Cost", "financial.cost.total")
    service(governance).normalize(mapping, [row(mapping, 2, "10")])
    after = prospect_evidence_answer("what is the total cost of EC2", analysis)
    assert before == after
    assert "not evidenced" in after
