"""ACT-003 semantic discovery/governance pilot integration tests."""

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from io import BytesIO

import pytest
from openpyxl import Workbook

from services.prospect_data_intake_service import ProspectTenant
from universal_evidence.activation import (
    ActivationActor,
    ActivationPermission,
    ActivationScope,
    ActivationStage,
    InMemoryActivationAuditSink,
    InMemoryPueActivationRepository,
    PueActivationResolver,
    PueActivationService,
    ScopeLevel,
)
from universal_evidence.governance import (
    ActorType,
    ConfirmationActor,
    ConfirmationService,
    InMemoryAuditSink,
    MappingDecisionState,
)
from universal_evidence.pilot import admit_uploaded_evidence
from universal_evidence.pilot.semantic_control import authenticated_confirmation_actor
from universal_evidence.pilot.semantic_service import PilotSemanticGovernanceService
from universal_evidence.pilot.semantic_view_models import SemanticMappingStatus
from universal_evidence.pilot.telemetry import InMemoryPilotTelemetry
from universal_evidence.semantic import DiscoveryConfig, discover_semantics

NOW = datetime(2026, 8, 28, 10, 0, tzinfo=timezone.utc)


def _tenant(name="semantic-prospect"):
    return ProspectTenant(
        name,
        f"audit-{name}",
        NOW.isoformat(),
        (NOW + timedelta(days=30)).isoformat(),
        30,
    )


def _workbook(headers, rows):
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Evidence"
    sheet.append(headers)
    for row in rows:
        sheet.append(row)
    stream = BytesIO()
    workbook.save(stream)
    return stream.getvalue()


def _admission(*, tenant=None, headers=None, rows=None):
    return admit_uploaded_evidence(
        tenant or _tenant(),
        filename="evidence.xlsx",
        content=_workbook(
            headers or ("Service", "Region", "Price Per Service (USD)"),
            rows or (("Compute", "us-east-1", 12.5), ("Storage", "eu-west-1", 9.5)),
        ),
        now=NOW,
    )


def _actor(role="super_admin", actor_id="governor@example.com"):
    return ConfirmationActor(actor_id, actor_id, role, ActorType.HUMAN)


def _runtime(admission, *, stage=ActivationStage.EVIDENCE_DISCOVERY_VISIBLE, policy=None):
    repository = InMemoryPueActivationRepository()
    activation_audit = InMemoryActivationAuditSink()
    activation = PueActivationService(
        repository=repository, audit_sink=activation_audit, clock=lambda: NOW
    )
    resolver = PueActivationResolver(repository=repository, clock=lambda: NOW)
    activation_actor = ActivationActor(
        "activation-admin",
        "pue_activation_admin",
        "HUMAN_ADMIN",
        (
            ActivationPermission.CHANGE_PUE_STAGE,
            ActivationPermission.TRIGGER_PUE_KILL_SWITCH,
        ),
    )
    activation.configure(
        scope=ActivationScope(
            ScopeLevel.ANALYSIS,
            analysis_id=admission.scope.analysis_id,
            prospect_id=admission.scope.prospect_id,
        ),
        stage=stage,
        actor=activation_actor,
        reason="ACT-003 fixture",
    )
    governance_audit = InMemoryAuditSink()
    confirmation = ConfirmationService(
        audit=governance_audit, policy=policy, clock=lambda: NOW
    )
    telemetry = InMemoryPilotTelemetry()
    service = PilotSemanticGovernanceService(
        activation_resolver=resolver,
        confirmation_service=confirmation,
        telemetry=telemetry,
    )
    return service, activation, activation_actor, governance_audit, telemetry


def _mapping(model, header):
    return next(item for item in model.mappings if item.source_column_name == header)


def test_observed_fields_project_ranked_candidates_confidence_and_ambiguity():
    admission = _admission()
    service, *_ = _runtime(admission)
    model = service.experience(admission, actor=_actor())
    service_mapping = _mapping(model, "Service")
    assert service_mapping.candidates
    assert service_mapping.candidates[0].concept_id == "technology.service"
    assert service_mapping.candidates[0].confidence_band in {"High", "Medium", "Low"}
    assert 0 <= service_mapping.candidates[0].confidence_percent <= 100
    assert service_mapping.status in {
        SemanticMappingStatus.CANDIDATE,
        SemanticMappingStatus.CONFIRMATION_REQUIRED,
    }
    assert all(item.explanation for item in service_mapping.candidates)


def test_multiple_close_service_candidates_remain_ambiguous_and_unconfirmed():
    admission = _admission()
    service, *_ = _runtime(admission)
    service._discovery_cache[admission.fingerprint] = discover_semantics(
        admission.profile,
        config=DiscoveryConfig(ambiguity_gap_threshold=1.0),
    )
    mapping = _mapping(service.experience(admission, actor=_actor()), "Service")
    assert len(mapping.candidates) >= 2
    assert mapping.ambiguous
    assert mapping.status is SemanticMappingStatus.CONFIRMATION_REQUIRED
    assert mapping.effective_concept_id is None


def test_high_risk_financial_candidate_requires_confirmation_and_does_not_aggregate():
    admission = _admission()
    service, *_ = _runtime(admission)
    model = service.experience(admission, actor=_actor())
    price = _mapping(model, "Price Per Service (USD)")
    assert price.candidates[0].risk == "HIGH_RISK"
    assert price.status is SemanticMappingStatus.CONFIRMATION_REQUIRED
    assert not hasattr(model, "amount")
    assert not {"amount", "total", "result", "currency_amount"} & set(
        model.__dataclass_fields__
    )


def test_confirm_is_idempotent_effective_and_attributed_to_authenticated_actor():
    admission = _admission()
    service, _, _, audit, telemetry = _runtime(admission)
    actor = _actor(actor_id="ceo@company.com")
    before = _mapping(service.experience(admission, actor=actor), "Service")
    candidate = before.candidates[0].concept_id
    first = service.confirm(admission, before.column_reference, candidate, actor=actor)
    repeated = service.confirm(admission, before.column_reference, candidate, actor=actor)
    after = _mapping(service.experience(admission, actor=actor), "Service")
    assert repeated.decision_id == first.decision_id
    assert after.status is SemanticMappingStatus.CONFIRMED
    assert after.effective_concept_id == candidate
    assert after.history[-1].actor_id == "ceo@company.com"
    assert any(item.event_type == "MAPPING_CONFIRMED" for item in audit.events())
    assert telemetry.count("mapping_confirmed_count") == 1


def test_rejection_requires_reason_and_never_creates_effective_mapping():
    admission = _admission()
    service, *_ = _runtime(admission)
    actor = _actor()
    mapping = _mapping(service.experience(admission, actor=actor), "Service")
    candidate = mapping.candidates[0].concept_id
    with pytest.raises(ValueError, match="rejection reason"):
        service.reject(
            admission, mapping.column_reference, candidate, actor=actor, reason=""
        )
    service.reject(
        admission,
        mapping.column_reference,
        candidate,
        actor=actor,
        reason="Evidence conflicts with intended meaning",
    )
    rejected = _mapping(service.experience(admission, actor=actor), "Service")
    assert rejected.status is SemanticMappingStatus.REJECTED
    assert rejected.effective_concept_id is None


def test_override_uses_registry_requires_reason_and_preserves_history():
    admission = _admission()
    service, *_ = _runtime(admission)
    actor = _actor()
    mapping = _mapping(service.experience(admission, actor=actor), "Service")
    service.confirm(
        admission,
        mapping.column_reference,
        mapping.candidates[0].concept_id,
        actor=actor,
    )
    with pytest.raises(ValueError, match="override reason"):
        service.override(
            admission,
            mapping.column_reference,
            "business.service",
            actor=actor,
            reason=None,
        )
    with pytest.raises(ValueError, match="ontology-approved"):
        service.override(
            admission,
            mapping.column_reference,
            "customer.free_text",
            actor=actor,
            reason="Not in registry",
        )
    decision = service.override(
        admission,
        mapping.column_reference,
        "business.service",
        actor=actor,
        reason="Operator resolved the ambiguity",
    )
    overridden = _mapping(service.experience(admission, actor=actor), "Service")
    assert decision.decision_state is MappingDecisionState.OVERRIDDEN
    assert overridden.status is SemanticMappingStatus.OVERRIDDEN
    assert overridden.effective_concept_id == "business.service"
    assert {item.state for item in overridden.history} >= {
        "CONFIRMED",
        "SUPERSEDED",
        "OVERRIDDEN",
    }


def test_classifier_ontology_and_policy_drift_block_stale_mapping():
    admission = _admission()
    service, *_ = _runtime(admission)
    actor = _actor()
    mapping = _mapping(service.experience(admission, actor=actor), "Service")
    service.confirm(
        admission,
        mapping.column_reference,
        mapping.candidates[0].concept_id,
        actor=actor,
    )
    original = service.discovery(admission)
    for changed in (
        replace(original, classifier_version="classifier-drift"),
        replace(original, ontology_version="ontology-drift"),
        replace(original, policy_version="policy-drift"),
    ):
        service._discovery_cache[admission.fingerprint] = changed
        stale = _mapping(service.experience(admission, actor=actor), "Service")
        assert stale.status is SemanticMappingStatus.BLOCKED
        assert stale.stale
        assert stale.effective_concept_id is None


def test_same_evidence_and_versions_replay_deterministically():
    admission = _admission()
    first = discover_semantics(admission.profile)
    second = discover_semantics(admission.profile)
    assert first.semantic_fingerprint == second.semantic_fingerprint
    assert first.columns == second.columns


def test_decisions_are_isolated_across_analysis_and_prospect_scope():
    first = _admission(tenant=_tenant("first"))
    second = _admission(tenant=_tenant("second"))
    service, *_ = _runtime(first)
    actor = _actor()
    first_mapping = _mapping(service.experience(first, actor=actor), "Service")
    service.confirm(
        first,
        first_mapping.column_reference,
        first_mapping.candidates[0].concept_id,
        actor=actor,
    )
    second_service, *_ = _runtime(second)
    second_mapping = _mapping(second_service.experience(second, actor=actor), "Service")
    assert second_mapping.effective_concept_id is None
    assert second.scope.analysis_id != first.scope.analysis_id
    assert second.scope.prospect_id != first.scope.prospect_id


def test_non_cost_evidence_has_application_owner_region_contract_candidates_only():
    admission = _admission(
        headers=("Application", "Owner", "Region", "Contract Renewal Date"),
        rows=(("Portal", "Platform", "us-east-1", "2027-01-01"),),
    )
    service, *_ = _runtime(admission)
    model = service.experience(admission, actor=_actor())
    concepts = {
        candidate.concept_id
        for mapping in model.mappings
        for candidate in mapping.candidates
    }
    assert "application.name" in concepts
    assert "ownership.owner" in concepts
    assert concepts & {"cloud.region", "geography.region"}
    assert "contract.renewal_date" in concepts
    assert not any(item.startswith("financial.") for item in concepts)


def test_stage_zero_and_kill_switch_suppress_surface_stage_two_remains_non_numeric():
    admission = _admission()
    service, activation, activation_actor, _, _ = _runtime(
        admission, stage=ActivationStage.SHADOW_ONLY
    )
    actor = _actor()
    assert service.experience(admission, actor=actor) is None
    activation.configure(
        scope=ActivationScope(
            ScopeLevel.ANALYSIS,
            analysis_id=admission.scope.analysis_id,
            prospect_id=admission.scope.prospect_id,
        ),
        stage=ActivationStage.CAPABILITY_VISIBLE,
        actor=activation_actor,
        reason="stage two",
    )
    assert service.experience(admission, actor=actor) is not None
    activation.set_kill_switch(
        enabled=True,
        actor=activation_actor,
        reason="ACT-003 suppression",
    )
    assert service.experience(admission, actor=actor) is None


def test_production_control_guard_and_authenticated_actor_requirement(monkeypatch):
    from universal_evidence.pilot.dev_control import dev_control_enabled

    assert not dev_control_enabled(
        {"ENVIRONMENT": "production", "PUE_PILOT_DEV_MODE": "true"}
    )
    with pytest.raises(PermissionError, match="authenticated actor"):
        authenticated_confirmation_actor({"role": "executive"})
    actor = authenticated_confirmation_actor(
        {"email": "ceo@company.com", "role": "executive"}
    )
    assert actor.actor_id == "ceo@company.com"
    assert actor.actor_type is ActorType.HUMAN


def test_real_cur_workbook_semantics_are_candidates_not_currency_or_total_authority():
    content = open("temp_uploads/CUR Jan 2026.xlsx", "rb").read()
    admission = admit_uploaded_evidence(
        _tenant("real-cur"), filename="CUR Jan 2026.xlsx", content=content, now=NOW
    )
    service, *_ = _runtime(admission)
    model = service.experience(admission, actor=_actor())
    headers = {item.source_column_name for item in model.mappings}
    assert {
        "Service",
        "Region",
        "Price Per Service (USD)",
    } <= headers
    price = _mapping(model, "Price Per Service (USD)")
    assert price.status is SemanticMappingStatus.CONFIRMATION_REQUIRED
    assert price.effective_concept_id is None
    assert "861828" not in repr(model)
    assert "861830" not in repr(model)


def test_page_only_renders_semantic_adapter_and_does_not_route_or_create_entities():
    page = open("pages/analyze_environment.py", encoding="utf-8").read()
    assert "render_semantic_governance(st, upload_admission)" in page
    assert "discover_semantics" not in page
    assert "ConfirmationService" not in page
    assert "PueQuestionRouter" not in page
    assert "create_entity" not in page
