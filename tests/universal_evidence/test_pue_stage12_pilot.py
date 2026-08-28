"""PUE-ACT-002 Stage 1/2 additive prospect-pilot certification tests."""

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from tests.universal_evidence.test_pue_shadow_end_to_end import (
    governed_request,
    run,
    source,
)
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
from universal_evidence.capability import CapabilityScope
from universal_evidence.governance import ConfirmationService
from universal_evidence.pilot import (
    InMemoryPilotTelemetry,
    PilotAnalysisContext,
    PilotVisibility,
    PueStage12PilotService,
)
from universal_evidence.shadow import ShadowAnalysisInput, ShadowOrchestrator

NOW = datetime(2026, 8, 27, 9, 0, tzinfo=timezone.utc)


def _admin():
    return ActivationActor(
        "pilot-admin",
        "pue_activation_admin",
        "HUMAN_ADMIN",
        (
            ActivationPermission.CHANGE_PUE_STAGE,
            ActivationPermission.TRIGGER_PUE_ROLLBACK,
            ActivationPermission.TRIGGER_PUE_KILL_SWITCH,
        ),
    )


@pytest.fixture
def pilot():
    repository = InMemoryPueActivationRepository()
    audit = InMemoryActivationAuditSink()
    telemetry = InMemoryPilotTelemetry()
    activation_service = PueActivationService(
        repository=repository, audit_sink=audit, clock=lambda: NOW
    )
    service = PueStage12PilotService(
        activation_resolver=PueActivationResolver(
            repository=repository, clock=lambda: NOW
        ),
        shadow_orchestrator=ShadowOrchestrator(clock=lambda: NOW),
        telemetry=telemetry,
        audit_sink=audit,
        clock=lambda: NOW,
    )
    return activation_service, service, telemetry, audit


def _prospect(shadow):
    scope = shadow.capability_assessment.scope
    return SimpleNamespace(
        tenant_id=scope.tenant_id,
        audit_id="audit-current",
        analysis_timestamp="2026-08-27T09:00:00+00:00",
        row_count=shadow.source_rows,
        currency_source="EVIDENCE",
        currency_resolution_required=False,
        total_spend=999999,
    )


def _context(service, prospect, shadow):
    return PilotAnalysisContext(
        shadow.capability_assessment.scope,
        service.prospect_fingerprint(prospect),
        shadow.fingerprint,
    )


def _configure(activation_service, shadow, stage):
    scope = shadow.capability_assessment.scope
    return activation_service.configure(
        scope=ActivationScope(
            ScopeLevel.ANALYSIS,
            organization_id=scope.organization_id,
            tenant_id=scope.tenant_id,
            prospect_id=scope.prospect_id,
            analysis_id=scope.analysis_id,
        ),
        stage=stage,
        actor=_admin(),
        reason="approved ACT-002 pilot fixture",
    )


def _governed_shadow():
    _, shadow = run(
        b"Service,Cost,Currency\nEC2,100,USD\nEC2,200,USD\nRDS,50,USD\n",
        {
            "Service": ("technology.service", ["EC2", "EC2", "RDS"]),
            "Cost": ("financial.cost.total", ["100", "200", "50"]),
            "Currency": ("financial.currency", ["USD", "USD", "USD"]),
        },
    )
    return shadow


def test_stage_zero_is_invisible_and_does_not_change_prospect_authority(pilot):
    _, service, telemetry, _ = pilot
    shadow = _governed_shadow()
    prospect = _prospect(shadow)
    before = vars(prospect).copy()
    model = service.experience(
        prospect_analysis=prospect,
        context=_context(service, prospect, shadow),
        shadow_result=shadow,
    )
    assert model is None
    assert vars(prospect) == before
    assert telemetry.count("stage_1_views") == 0


def test_stage_one_exposes_discovery_but_no_capabilities_or_values(pilot):
    activation, service, _, audit = pilot
    shadow = _governed_shadow()
    _configure(activation, shadow, ActivationStage.EVIDENCE_DISCOVERY_VISIBLE)
    prospect = _prospect(shadow)
    model = service.experience(
        prospect_analysis=prospect,
        context=_context(service, prospect, shadow),
        shadow_result=shadow,
    )
    assert model.visibility is PilotVisibility.DISCOVERY
    assert {item.concept_id for item in model.evidence_items} >= {
        "technology.service",
        "financial.cost.total",
        "financial.currency",
        "security.risk",
    }
    assert not model.capability_items
    assert "999999" not in repr(model)
    assert audit.events[-1].event_type == "PUE_EVIDENCE_SURFACED"


@pytest.mark.parametrize(
    "configured_stage",
    [
        ActivationStage.CAPABILITY_VISIBLE,
        ActivationStage.SELECTED_ANSWERS,
        ActivationStage.ASK_NEXORA_SELECTED_ROUTING,
    ],
)
def test_stage_two_and_higher_are_capped_at_non_numerical_capability_visibility(
    pilot, configured_stage
):
    activation, service, telemetry, _ = pilot
    shadow = _governed_shadow()
    _configure(activation, shadow, configured_stage)
    prospect = _prospect(shadow)
    model = service.experience(
        prospect_analysis=prospect,
        context=_context(service, prospect, shadow),
        shadow_result=shadow,
    )
    assert model.visibility is PilotVisibility.DISCOVERY_AND_CAPABILITY
    assert model.capability_items
    assert not hasattr(model, "answer")
    assert not hasattr(model, "amount")
    assert "999999" not in repr(model)
    assert telemetry.count("stage_2_views") == 1


def test_missing_currency_shows_blocked_cost_capability_without_legacy_total(pilot):
    costs = ["4683"] * 183 + ["4869"]
    _, shadow = run(
        ("Cost\n" + "\n".join(costs) + "\n").encode(),
        {"Cost": ("financial.cost.total", costs)},
    )
    activation, service, _, _ = pilot
    _configure(activation, shadow, ActivationStage.CAPABILITY_VISIBLE)
    prospect = _prospect(shadow)
    prospect.currency_source = "UNRESOLVED"
    prospect.currency_resolution_required = True
    context = _context(service, prospect, shadow)
    model = service.experience(
        prospect_analysis=prospect, context=context, shadow_result=shadow
    )
    monetary = next(
        item for item in model.capability_items if item.label == "Total cost"
    )
    assert monetary.state == "BLOCKED"
    assert "currency" in monetary.reason.lower()
    currency = next(
        item for item in model.evidence_items if item.concept_id == "financial.currency"
    )
    assert currency.state != "EVIDENCED"
    assert model.details.record_count == 184
    assert "861828" not in repr(model)


def test_scope_or_fingerprint_mismatch_fails_closed_without_visible_panel(pilot):
    activation, service, _, _ = pilot
    shadow = _governed_shadow()
    _configure(activation, shadow, ActivationStage.CAPABILITY_VISIBLE)
    prospect = _prospect(shadow)
    valid = _context(service, prospect, shadow)
    stale_prospect = PilotAnalysisContext(
        valid.scope, "stale-prospect", valid.shadow_fingerprint
    )
    stale_shadow = PilotAnalysisContext(
        valid.scope, valid.prospect_analysis_fingerprint, "stale-shadow"
    )
    assert (
        service.experience(
            prospect_analysis=prospect,
            context=stale_prospect,
            shadow_result=shadow,
        )
        is None
    )
    assert (
        service.experience(
            prospect_analysis=prospect,
            context=stale_shadow,
            shadow_result=shadow,
        )
        is None
    )


def test_shadow_failure_is_isolated_as_safe_unavailable_state(pilot):
    activation, service, telemetry, _ = pilot
    shadow = _governed_shadow()
    _configure(activation, shadow, ActivationStage.EVIDENCE_DISCOVERY_VISIBLE)
    prospect = _prospect(shadow)
    model = service.experience(
        prospect_analysis=prospect,
        context=_context(service, prospect, shadow),
        shadow_result=None,
    )
    assert model.visibility is PilotVisibility.UNAVAILABLE
    assert "unaffected" in model.safe_message
    assert telemetry.count("shadow_failures") == 1


def test_kill_switch_immediately_suppresses_visible_pilot(pilot):
    activation, service, telemetry, _ = pilot
    shadow = _governed_shadow()
    _configure(activation, shadow, ActivationStage.CAPABILITY_VISIBLE)
    activation.set_kill_switch(
        enabled=True, actor=_admin(), reason="pilot emergency stop"
    )
    prospect = _prospect(shadow)
    assert (
        service.experience(
            prospect_analysis=prospect,
            context=_context(service, prospect, shadow),
            shadow_result=shadow,
        )
        is None
    )
    assert telemetry.count("kill_switch_suppressions") == 1


def test_rollback_from_stage_two_to_stage_zero_removes_panels(pilot):
    activation, service, _, _ = pilot
    shadow = _governed_shadow()
    config = _configure(activation, shadow, ActivationStage.CAPABILITY_VISIBLE)
    prospect = _prospect(shadow)
    context = _context(service, prospect, shadow)
    assert service.experience(
        prospect_analysis=prospect, context=context, shadow_result=shadow
    )
    activation.rollback(
        config,
        target_stage=ActivationStage.SHADOW_ONLY,
        actor=_admin(),
        reason="pilot rollback",
    )
    assert (
        service.experience(
            prospect_analysis=prospect, context=context, shadow_result=shadow
        )
        is None
    )


def test_expired_stage_two_does_not_leave_stale_visibility(pilot):
    activation, service, _, _ = pilot
    shadow = _governed_shadow()
    scope = shadow.capability_assessment.scope
    activation.configure(
        scope=ActivationScope(
            ScopeLevel.ANALYSIS,
            organization_id=scope.organization_id,
            tenant_id=scope.tenant_id,
            prospect_id=scope.prospect_id,
            analysis_id=scope.analysis_id,
        ),
        stage=ActivationStage.CAPABILITY_VISIBLE,
        actor=_admin(),
        reason="expired pilot fixture",
        effective_from=NOW.replace(day=25),
        expires_at=NOW.replace(day=26),
    )
    prospect = _prospect(shadow)
    assert (
        service.experience(
            prospect_analysis=prospect,
            context=_context(service, prospect, shadow),
            shadow_result=shadow,
        )
        is None
    )


def test_analysis_activation_does_not_spill_to_another_analysis(pilot):
    activation, service, _, _ = pilot
    first = _governed_shadow()
    _configure(activation, first, ActivationStage.CAPABILITY_VISIBLE)
    _, second = run(
        b"Service,Cost,Currency\nEC2,10,USD\n",
        {
            "Service": ("technology.service", ["EC2"]),
            "Cost": ("financial.cost.total", ["10"]),
            "Currency": ("financial.currency", ["USD"]),
        },
        evidence_source=source(analysis="analysis-other", prospect="prospect-shadow"),
    )
    prospect = _prospect(second)
    assert (
        service.experience(
            prospect_analysis=prospect,
            context=_context(service, prospect, second),
            shadow_result=second,
        )
        is None
    )


def test_prospect_only_scope_is_preserved_without_session_enrichment(pilot):
    activation, service, _, _ = pilot
    shadow = _governed_shadow()
    assert shadow.capability_assessment.scope.organization_id is None
    assert shadow.capability_assessment.scope.tenant_id is None
    _configure(activation, shadow, ActivationStage.EVIDENCE_DISCOVERY_VISIBLE)
    prospect = _prospect(shadow)
    model = service.experience(
        prospect_analysis=prospect,
        context=_context(service, prospect, shadow),
        shadow_result=shadow,
    )
    assert model.scope.organization_id is None
    assert model.scope.tenant_id is None


def test_view_model_is_deterministic_for_same_certified_inputs(pilot):
    activation, service, _, _ = pilot
    shadow = _governed_shadow()
    _configure(activation, shadow, ActivationStage.CAPABILITY_VISIBLE)
    prospect = _prospect(shadow)
    context = _context(service, prospect, shadow)
    first = service.experience(
        prospect_analysis=prospect, context=context, shadow_result=shadow
    )
    second = service.experience(
        prospect_analysis=prospect, context=context, shadow_result=shadow
    )
    assert first == second
    assert first.fingerprint == second.fingerprint


def test_mixed_enterprise_evidence_surfaces_multiple_governed_domains(pilot):
    _, shadow = run(
        (
            b"Provider,Service,Resource ID,Region,Application,Owner,Cost Center,"
            b"Cost,Currency,Contract Renewal Date\n"
            b"AWS,EC2,i-1,ap-south-1,Portal,Platform,CC-1,10,USD,2026-12-01\n"
        ),
        {
            "Provider": ("cloud.provider", ["AWS"]),
            "Service": ("technology.service", ["EC2"]),
            "Resource ID": ("resource.identifier", ["i-1"]),
            "Region": ("cloud.region", ["ap-south-1"]),
            "Application": ("application.name", ["Portal"]),
            "Owner": ("ownership.owner", ["Platform"]),
            "Cost Center": ("organization.cost_center", ["CC-1"]),
            "Cost": ("financial.cost.total", ["10"]),
            "Currency": ("financial.currency", ["USD"]),
            "Contract Renewal Date": ("contract.renewal_date", ["2026-12-01"]),
        },
    )
    activation, service, _, _ = pilot
    _configure(activation, shadow, ActivationStage.CAPABILITY_VISIBLE)
    prospect = _prospect(shadow)
    model = service.experience(
        prospect_analysis=prospect,
        context=_context(service, prospect, shadow),
        shadow_result=shadow,
    )
    labels = {item.label for item in model.evidence_items if item.state == "EVIDENCED"}
    assert {"Technology service", "Region", "Application", "Owner", "Cost"} <= labels
    assert not hasattr(model, "normalized_values")
    assert not hasattr(model, "analytical_result")


def test_mixed_currency_remains_a_blocked_capability_without_combined_total(pilot):
    _, shadow = run(
        b"Cost,Currency\n100,USD\n200,INR\n",
        {
            "Cost": ("financial.cost.total", ["100", "200"]),
            "Currency": ("financial.currency", ["USD", "INR"]),
        },
    )
    activation, service, _, _ = pilot
    _configure(activation, shadow, ActivationStage.CAPABILITY_VISIBLE)
    prospect = _prospect(shadow)
    model = service.experience(
        prospect_analysis=prospect,
        context=_context(service, prospect, shadow),
        shadow_result=shadow,
    )
    total = next(item for item in model.capability_items if item.label == "Total cost")
    assert total.state == "BLOCKED"
    currency = next(
        item for item in model.evidence_items if item.concept_id == "financial.currency"
    )
    assert currency.state == "EVIDENCED"
    assert not hasattr(model, "currency_totals")
    assert "300" not in repr(model)


def test_irregular_unconfirmed_evidence_degrades_to_safe_unavailable_panel(pilot):
    from tests.universal_evidence.test_pue_shadow_end_to_end import workbook_bytes

    evidence_source = source()
    shadow = ShadowOrchestrator(clock=lambda: NOW).run_shadow_analysis(
        ShadowAnalysisInput(
            evidence_source,
            "irregular.xlsx",
            workbook_bytes(irregular=True),
            ConfirmationService().repository,
            (),
        )
    )
    activation, service, _, _ = pilot
    activation.configure(
        scope=ActivationScope(
            ScopeLevel.ANALYSIS,
            analysis_id=evidence_source.context.analysis_id,
            prospect_id=evidence_source.context.prospect_id,
        ),
        stage=ActivationStage.EVIDENCE_DISCOVERY_VISIBLE,
        actor=_admin(),
        reason="irregular workbook pilot fixture",
    )
    scope = CapabilityScope(
        evidence_source.context.analysis_id,
        evidence_source.context.prospect_id,
        evidence_source.context.organization_id,
        evidence_source.context.tenant_id,
    )
    prospect = SimpleNamespace(
        tenant_id=None,
        audit_id="audit-irregular",
        analysis_timestamp="2026-08-27T09:00:00+00:00",
        row_count=shadow.source_rows,
        currency_source="UNRESOLVED",
        currency_resolution_required=True,
    )
    context = PilotAnalysisContext(
        scope,
        service.prospect_fingerprint(prospect),
        shadow.fingerprint,
    )
    model = service.experience(
        prospect_analysis=prospect, context=context, shadow_result=shadow
    )
    assert model.visibility is PilotVisibility.UNAVAILABLE
    assert not model.evidence_items


def test_shadow_execution_is_cached_by_exact_input(pilot):
    _, service, telemetry, _ = pilot
    request = governed_request(
        b"Cost,Currency\n10,USD\n",
        {
            "Cost": ("financial.cost.total", ["10"]),
            "Currency": ("financial.currency", ["USD"]),
        },
    )
    first = service.run_or_reuse_shadow(request)
    second = service.run_or_reuse_shadow(request)
    assert first is second
    assert telemetry.count("shadow_runs") == 1
    assert telemetry.count("shadow_reuse") == 1


def test_page_integration_is_additive_and_has_no_question_router_or_execution():
    page = open("pages/analyze_environment.py", encoding="utf-8").read()
    pilot_files = " ".join(
        open(path, encoding="utf-8").read()
        for path in (
            "universal_evidence/pilot/models.py",
            "universal_evidence/pilot/render.py",
            "universal_evidence/pilot/service.py",
            "universal_evidence/pilot/view_models.py",
        )
    )
    assert "render_pue_stage12" in page
    assert "PueQuestionRouter" not in page + pilot_files
    assert "run_shadow_question" not in page + pilot_files
    assert "AggregationExecutor" not in page + pilot_files
    assert "confirm_mapping" not in page + pilot_files
