"""PUE-003 semantic confirmation governance and non-authority tests."""

from __future__ import annotations

from dataclasses import fields, replace
from datetime import datetime, timedelta, timezone

import pytest

from universal_evidence.contracts import (
    ClassificationState,
    ConfirmationState,
    EvidenceAnalysisContext,
    EvidenceSource,
)
from universal_evidence.governance import (
    ActorType,
    ConfirmationActor,
    ConfirmationService,
    GovernancePolicy,
    MappingDecisionState,
)
from universal_evidence.profiling import profile_evidence
from universal_evidence.semantic import discover_semantics


def source(
    *,
    analysis_id: str = "analysis-gov-1",
    prospect_id: str = "prospect-gov-1",
    organization_id: str | None = None,
    tenant_id: str | None = None,
) -> EvidenceSource:
    now = datetime(2026, 8, 25, 12, 0, tzinfo=timezone.utc)
    context = EvidenceAnalysisContext(
        analysis_id,
        "source-gov-1",
        prospect_id,
        organization_id,
        tenant_id,
    )
    return EvidenceSource(context, "authorized:source-gov-1", now, now + timedelta(days=30))


def discovery(content: bytes, *, evidence_source: EvidenceSource | None = None):
    profile = profile_evidence(
        source=evidence_source or source(), filename="evidence.csv", content=content
    )
    return discover_semantics(profile)


def column(result, header: str):
    return next(item for item in result.columns if item.original_header == header)


def human(role: str = "finance", actor_id: str = "user-1") -> ConfirmationActor:
    return ConfirmationActor(actor_id, "reviewer@example.test", role, ActorType.HUMAN)


def request_cost(service: ConfirmationService, result):
    item = column(result, "Cost")
    request = service.request_confirmation(
        result, item.source_column_reference, "financial.cost.total"
    )
    return item, request


def test_high_risk_candidate_requires_confirmation_and_request_is_pending():
    result = discovery(b"Cost\n10.5\n20.5\n")
    service = ConfirmationService()
    item, request = request_cost(service, result)

    requirement = service.evaluate_confirmation_requirement(item)
    assert requirement.state is ConfirmationState.REQUIRED
    assert request.confirmation_state is ConfirmationState.PENDING
    assert request.discovery_id == item.discovery_id


def test_decision_scope_is_copied_only_from_semantic_discovery_provenance():
    result = discovery(
        b"Cost\n10\n20\n",
        evidence_source=source(
            analysis_id="a-7",
            prospect_id="p-7",
            organization_id="o-7",
            tenant_id="t-7",
        ),
    )
    service = ConfirmationService()
    item, request = request_cost(service, result)
    provenance = item.provenance

    assert request.scope.key == (
        provenance.analysis_id,
        provenance.prospect_id,
        provenance.organization_id,
        provenance.tenant_id,
        provenance.source_id,
        provenance.file_id,
        provenance.sheet_id,
        provenance.column_id,
    )


def test_prospect_only_scope_preserves_absent_organization_and_tenant():
    result = discovery(b"Cost\n10\n20\n")
    service = ConfirmationService()
    _, request = request_cost(service, result)

    assert request.scope.organization_id is None
    assert request.scope.tenant_id is None


def test_confirm_creates_effective_mapping_with_actor_and_audit():
    result = discovery(b"Cost\n10\n20\n")
    service = ConfirmationService()
    item, _ = request_cost(service, result)
    actor = human()
    decision = service.confirm_mapping(
        result,
        item.source_column_reference,
        "financial.cost.total",
        actor=actor,
    )

    effective = service.get_effective_mapping(item, actor=actor)
    assert decision.decision_state is MappingDecisionState.CONFIRMED
    assert effective is not None
    assert effective.semantic_concept_id == "financial.cost.total"
    assert effective.actor == actor
    assert service.audit.events()[-1].event_type == "MAPPING_CONFIRMED"


def test_decision_timestamp_records_governance_action_not_classification_time():
    result = discovery(b"Cost\n10\n20\n")
    action_time = datetime(2026, 8, 26, 9, 30, tzinfo=timezone.utc)
    service = ConfirmationService(clock=lambda: action_time)
    item, request = request_cost(service, result)
    decision = service.confirm_mapping(
        result,
        item.source_column_reference,
        "financial.cost.total",
        actor=human(),
    )

    assert request.created_at == action_time
    assert decision.decision_timestamp == action_time
    assert decision.decision_timestamp != item.classification_timestamp


def test_rejection_requires_reason_and_creates_no_effective_mapping():
    result = discovery(b"Cost\n10\n20\n")
    service = ConfirmationService()
    item, _ = request_cost(service, result)

    with pytest.raises(ValueError, match="reason"):
        service.reject_mapping(
            result,
            item.source_column_reference,
            "financial.cost.total",
            actor=human(),
            reason=None,
        )
    rejected = service.reject_mapping(
        result,
        item.source_column_reference,
        "financial.cost.total",
        actor=human(),
        reason="not the billed amount",
    )
    assert rejected.decision_state is MappingDecisionState.REJECTED
    assert service.get_effective_mapping(item, actor=human()) is None


def test_override_requires_privileged_role_reason_and_approved_ontology_concept():
    result = discovery(b"Cost\n10\n20\n")
    item = column(result, "Cost")
    service = ConfirmationService()

    with pytest.raises(PermissionError):
        service.override_mapping(
            result,
            item.source_column_reference,
            "financial.cost.monthly",
            actor=human("sales_engineer"),
            reason="monthly evidence",
        )
    with pytest.raises(ValueError, match="reason"):
        service.override_mapping(
            result,
            item.source_column_reference,
            "financial.cost.monthly",
            actor=human(),
            reason=None,
        )
    with pytest.raises(ValueError, match="ontology-approved"):
        service.override_mapping(
            result,
            item.source_column_reference,
            "invented.cost",
            actor=human(),
            reason="manual selection",
        )


def test_override_supersedes_effective_mapping_without_deleting_history():
    result = discovery(b"Cost\n10\n20\n")
    service = ConfirmationService()
    item, _ = request_cost(service, result)
    first = service.confirm_mapping(
        result,
        item.source_column_reference,
        "financial.cost.total",
        actor=human(),
    )
    override = service.override_mapping(
        result,
        item.source_column_reference,
        "financial.cost.monthly",
        actor=human(),
        reason="the source period is monthly",
    )

    history = service.get_decision_history(item, actor=human("auditor"))
    assert [entry.decision_state for entry in history.decisions] == [
        MappingDecisionState.CONFIRMED,
        MappingDecisionState.SUPERSEDED,
        MappingDecisionState.OVERRIDDEN,
    ]
    assert override.supersedes_decision_id == first.decision_id
    assert service.get_effective_mapping(item, actor=human()).decision_id == override.decision_id


def test_original_candidate_ranking_is_retained_on_override():
    result = discovery(b"Cost\n10\n20\n")
    item = column(result, "Cost")
    decision = ConfirmationService().override_mapping(
        result,
        item.source_column_reference,
        "financial.cost.monthly",
        actor=human(),
        reason="confirmed billing period",
    )
    assert decision.original_candidate_ranking == tuple(
        (candidate.semantic_concept_id, candidate.confidence.score)
        for candidate in item.candidates
    )


def test_low_risk_auto_classified_mapping_may_be_auto_accepted():
    result = discovery(b"Environment\nprod\ndev\ntest\n")
    observed = column(result, "Environment")
    item = replace(
        observed,
        classification_state=ClassificationState.AUTO_CLASSIFIED,
        confirmation_state=ConfirmationState.NOT_REQUIRED,
        confirmation_reasons=(),
    )
    result = replace(result, columns=(item,))
    service = ConfirmationService()
    decision = service.auto_accept(result, item.source_column_reference)

    assert decision.decision_state is MappingDecisionState.AUTO_ACCEPTED
    assert decision.actor.actor_type is ActorType.POLICY_ENGINE


def test_high_risk_mapping_cannot_be_auto_accepted():
    result = discovery(b"Cost\n10\n20\n")
    item = column(result, "Cost")
    with pytest.raises(ValueError, match="does not permit"):
        ConfirmationService().auto_accept(result, item.source_column_reference)


def test_human_actions_reject_system_actor_and_unauthorized_role():
    result = discovery(b"Cost\n10\n20\n")
    service = ConfirmationService()
    item, _ = request_cost(service, result)
    system = ConfirmationActor("engine", "engine", "finance", ActorType.SYSTEM)

    with pytest.raises(PermissionError, match="human actor"):
        service.confirm_mapping(
            result,
            item.source_column_reference,
            "financial.cost.total",
            actor=system,
        )
    with pytest.raises(PermissionError, match="not authorized"):
        service.confirm_mapping(
            result,
            item.source_column_reference,
            "financial.cost.total",
            actor=human("viewer"),
        )


def test_confirmation_requires_matching_pending_request():
    result = discovery(b"Cost\n10\n20\n")
    item = column(result, "Cost")
    with pytest.raises(ValueError, match="pending"):
        ConfirmationService().confirm_mapping(
            result,
            item.source_column_reference,
            "financial.cost.total",
            actor=human(),
        )


def test_request_and_confirmation_are_idempotent():
    result = discovery(b"Cost\n10\n20\n")
    service = ConfirmationService()
    item, first_request = request_cost(service, result)
    second_request = service.request_confirmation(
        result, item.source_column_reference, "financial.cost.total"
    )
    first = service.confirm_mapping(
        result,
        item.source_column_reference,
        "financial.cost.total",
        actor=human(),
    )
    second = service.confirm_mapping(
        result,
        item.source_column_reference,
        "financial.cost.total",
        actor=human(),
    )

    assert first_request is second_request
    assert first is second
    assert len(service.get_decision_history(item, actor=human()).decisions) == 1


def test_effective_mapping_cannot_transition_back_to_pending():
    result = discovery(b"Cost\n10\n20\n")
    service = ConfirmationService()
    item, _ = request_cost(service, result)
    service.confirm_mapping(
        result,
        item.source_column_reference,
        "financial.cost.total",
        actor=human(),
    )
    with pytest.raises(ValueError, match="transition back"):
        request_cost(service, result)


def test_rejected_mapping_cannot_be_silently_confirmed_from_stale_request():
    result = discovery(b"Cost\n10\n20\n")
    service = ConfirmationService()
    item, _ = request_cost(service, result)
    service.reject_mapping(
        result,
        item.source_column_reference,
        "financial.cost.total",
        actor=human(),
        reason="not a total",
    )
    with pytest.raises(ValueError, match="explicit override"):
        service.confirm_mapping(
            result,
            item.source_column_reference,
            "financial.cost.total",
            actor=human(),
        )


def test_expiry_removes_effective_mapping_but_retains_history():
    result = discovery(b"Cost\n10\n20\n")
    service = ConfirmationService()
    item, _ = request_cost(service, result)
    service.confirm_mapping(
        result,
        item.source_column_reference,
        "financial.cost.total",
        actor=human(),
    )
    expired = service.expire_mapping(result, item.source_column_reference, actor=human())

    assert expired.decision_state is MappingDecisionState.EXPIRED
    assert service.get_effective_mapping(item, actor=human()) is None
    assert len(service.get_decision_history(item, actor=human()).decisions) == 2


@pytest.mark.parametrize(
    ("changed_field", "expected"),
    [
        ("semantic_fingerprint", "discovery_changed"),
        ("classifier_version", "classifier_changed"),
        ("ontology_version", "ontology_changed"),
        ("policy_version", "policy_changed"),
    ],
)
def test_discovery_drift_requires_reevaluation(changed_field: str, expected: str):
    result = discovery(b"Cost\n10\n20\n")
    service = ConfirmationService()
    item, _ = request_cost(service, result)
    decision = service.confirm_mapping(
        result,
        item.source_column_reference,
        "financial.cost.total",
        actor=human(),
    )
    changed = replace(result, **{changed_field: "changed-version"})
    drift = service.detect_drift(decision, changed)

    assert drift.requires_reevaluation
    assert getattr(drift, expected)


def test_governance_policy_drift_requires_reevaluation():
    result = discovery(b"Cost\n10\n20\n")
    service = ConfirmationService()
    item, _ = request_cost(service, result)
    decision = service.confirm_mapping(
        result,
        item.source_column_reference,
        "financial.cost.total",
        actor=human(),
    )
    revised = ConfirmationService(
        repository=service.repository,
        policy=GovernancePolicy(version="pue-governance-policy-2"),
    )
    assert revised.detect_drift(decision, result).policy_changed


def test_decisions_are_partitioned_by_analysis_and_prospect_scope():
    first = discovery(
        b"Cost\n10\n", evidence_source=source(analysis_id="a-1", prospect_id="p-1")
    )
    second = discovery(
        b"Cost\n10\n", evidence_source=source(analysis_id="a-2", prospect_id="p-2")
    )
    service = ConfirmationService()
    first_column, _ = request_cost(service, first)
    service.confirm_mapping(
        first,
        first_column.source_column_reference,
        "financial.cost.total",
        actor=human(),
    )

    second_column = column(second, "Cost")
    assert service.get_effective_mapping(second_column, actor=human()) is None


def test_pue003_contracts_expose_no_normalization_aggregation_or_query_outputs():
    field_names = {
        field.name
        for contract in (
            __import__(
                "universal_evidence.governance.models", fromlist=["MappingDecision"]
            ).MappingDecision,
            __import__(
                "universal_evidence.governance.models",
                fromlist=["EffectiveSemanticMapping"],
            ).EffectiveSemanticMapping,
        )
        for field in fields(contract)
    }
    forbidden = {"normalized_value", "aggregate", "entity", "query_capability"}
    assert field_names.isdisjoint(forbidden)
