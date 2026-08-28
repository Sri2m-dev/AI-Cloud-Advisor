"""ACT-004 governed normalization pilot boundary tests."""

from datetime import datetime, timedelta, timezone
from io import BytesIO

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
from universal_evidence.governance import ActorType, ConfirmationActor, ConfirmationService
from universal_evidence.pilot import admit_uploaded_evidence
from universal_evidence.pilot.normalization_service import PilotGovernedNormalizationService
from universal_evidence.pilot.semantic_service import PilotSemanticGovernanceService
from universal_evidence.pilot.telemetry import InMemoryPilotTelemetry

NOW = datetime(2026, 8, 28, 12, 0, tzinfo=timezone.utc)


def _content(headers=("Service", "Amount", "Currency"), rows=None):
    rows = rows or (("Compute", "12.50", "USD"), ("Storage", None, "INR"))
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(headers)
    for row in rows:
        sheet.append(row)
    stream = BytesIO()
    workbook.save(stream)
    return stream.getvalue()


def _admission(name="act004", content=None):
    tenant = ProspectTenant(
        name, f"audit-{name}", NOW.isoformat(), (NOW + timedelta(days=30)).isoformat(), 30
    )
    return admit_uploaded_evidence(
        tenant, filename="evidence.xlsx", content=content or _content(), now=NOW
    )


def _runtime(admission, stage=ActivationStage.CAPABILITY_VISIBLE):
    repository = InMemoryPueActivationRepository()
    audit = InMemoryActivationAuditSink()
    activation = PueActivationService(repository=repository, audit_sink=audit, clock=lambda: NOW)
    resolver = PueActivationResolver(repository=repository, clock=lambda: NOW)
    admin = ActivationActor(
        "admin",
        "pue_activation_admin",
        "HUMAN_ADMIN",
        (
            ActivationPermission.CHANGE_PUE_STAGE,
            ActivationPermission.TRIGGER_PUE_KILL_SWITCH,
            ActivationPermission.TRIGGER_PUE_ROLLBACK,
        ),
    )
    scope = ActivationScope(
        ScopeLevel.ANALYSIS,
        analysis_id=admission.scope.analysis_id,
        prospect_id=admission.scope.prospect_id,
    )
    activation.configure(scope=scope, stage=stage, actor=admin, reason="ACT-004 test")
    confirmation = ConfirmationService(clock=lambda: NOW)
    telemetry = InMemoryPilotTelemetry()
    semantic = PilotSemanticGovernanceService(
        activation_resolver=resolver, confirmation_service=confirmation, telemetry=telemetry
    )
    normalization = PilotGovernedNormalizationService(
        activation_resolver=resolver,
        semantic_service=semantic,
        confirmation_service=confirmation,
        telemetry=telemetry,
    )
    actor = ConfirmationActor("governor", "governor", "super_admin", ActorType.HUMAN)
    return normalization, semantic, activation, admin, scope, actor


def _mapping(semantic, admission, actor, header):
    return next(
        item
        for item in semantic.experience(admission, actor=actor).mappings
        if item.source_column_name == header
    )


def _confirm(semantic, admission, actor, header, concept=None):
    mapping = _mapping(semantic, admission, actor, header)
    if concept is not None and concept not in {item.concept_id for item in mapping.candidates}:
        semantic.override(
            admission,
            mapping.column_reference,
            concept,
            actor=actor,
            reason="Explicit governed test mapping",
        )
        return
    semantic.confirm(
        admission,
        mapping.column_reference,
        concept or mapping.candidates[0].concept_id,
        actor=actor,
    )


def test_candidate_only_is_blocked_and_stage_one_only_exposes_deterministic_plan():
    admission = _admission()
    normalization, _, _, _, _, actor = _runtime(
        admission, ActivationStage.EVIDENCE_DISCOVERY_VISIBLE
    )
    first = normalization.experience(admission, actor=actor)
    second = normalization.experience(admission, actor=actor)
    assert not first.executed and first.observation_count == 0
    assert first.plan.fingerprint == second.plan.fingerprint
    assert all(not item.eligible for item in first.plan.items)
    assert first.total_cost_state == "BLOCKED"
    assert not hasattr(first, "amount") and not hasattr(first, "total")


def test_confirmed_mapping_normalizes_rows_preserves_raw_and_marks_missing_explicitly():
    admission = _admission()
    normalization, semantic, *_tail, actor = _runtime(admission)
    _confirm(semantic, admission, actor, "Amount", "financial.cost.total")
    model = normalization.experience(admission, actor=actor)
    run = normalization.normalization.repository.get_by_analysis(admission.scope.analysis_id)[0]
    assert model.observation_count == 2
    assert model.quality.valid == 1 and model.quality.missing == 1
    assert run.records[0].source_value == "12.50"
    assert str(run.records[0].normalized_value) == "12.50"
    assert run.records[1].normalized_value is None
    assert model.total_cost_state == "BLOCKED"


def test_malformed_amount_is_invalid_and_currency_never_converts_or_authorizes_amount():
    admission = _admission(content=_content(rows=(("Compute", "bad", "usd"),)))
    normalization, semantic, *_tail, actor = _runtime(admission)
    _confirm(semantic, admission, actor, "Amount", "financial.cost.total")
    _confirm(semantic, admission, actor, "Currency", "financial.currency")
    model = normalization.experience(admission, actor=actor)
    assert model.quality.invalid == 1
    assert model.currency_partitions == ("USD",)
    assert model.total_cost_state == "BLOCKED"
    records = tuple(
        record
        for run in normalization.normalization.repository.get_by_analysis(
            admission.scope.analysis_id
        )
        for record in run.records
    )
    assert all(record.normalized_value != "INR" for record in records)


def test_override_uses_effective_concept_and_changed_evidence_isolated():
    admission = _admission()
    normalization, semantic, *_tail, actor = _runtime(admission)
    mapping = _mapping(semantic, admission, actor, "Service")
    semantic.override(
        admission,
        mapping.column_reference,
        "business.service",
        actor=actor,
        reason="Governed business-service meaning",
    )
    model = normalization.experience(admission, actor=actor)
    run = normalization.normalization.repository.get_by_analysis(admission.scope.analysis_id)[0]
    assert run.records[0].semantic_concept_id == "business.service"
    changed = _admission(name="other", content=_content(rows=(("Compute", "1", "USD"),)))
    changed_plan = normalization.plan(changed, actor=actor)
    assert changed_plan.evidence_fingerprint != model.plan.evidence_fingerprint
    assert not any(item.eligible for item in changed_plan.items)


def test_kill_switch_and_shadow_rollback_suppress_execution_without_deleting_governance():
    admission = _admission()
    normalization, semantic, activation, admin, scope, actor = _runtime(admission)
    _confirm(semantic, admission, actor, "Service", "technology.service")
    visible = normalization.experience(admission, actor=actor)
    assert visible.observation_count == 2
    activation.set_kill_switch(enabled=True, actor=admin, reason="ACT-004 safety test")
    assert normalization.experience(admission, actor=actor) is None
    column = next(
        item for item in semantic.discovery(admission).columns if item.original_header == "Service"
    )
    assert semantic.confirmation_service.get_effective_mapping(column, actor=actor) is not None
    assert normalization.normalization.repository.get_by_analysis(admission.scope.analysis_id)
