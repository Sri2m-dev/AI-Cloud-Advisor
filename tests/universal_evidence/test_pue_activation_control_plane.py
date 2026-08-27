"""PUE-ACT-001 activation control-plane certification tests."""

from __future__ import annotations

from dataclasses import fields
from datetime import datetime, timedelta, timezone

import pytest

from universal_evidence.activation import (
    ActivationActor,
    ActivationHealthState,
    ActivationMetrics,
    ActivationPermission,
    ActivationScope,
    ActivationStage,
    ConfigState,
    FallbackPolicy,
    InMemoryActivationAuditSink,
    InMemoryPueActivationRepository,
    PueActivationResolver,
    PueActivationService,
    PueQuestionRouter,
    ReadinessState,
    Route,
    RoutingDecision,
    RoutingReason,
    ScopeLevel,
    build_activation_readiness_report,
    evaluate_activation_health,
)
from universal_evidence.capability import CapabilityScope
from universal_evidence.interpretation import InterpretationStatus
from universal_evidence.planning import AnalyticalIntentType

NOW = datetime(2026, 8, 26, 18, 0, tzinfo=timezone.utc)


def admin(*permissions):
    return ActivationActor(
        "activation-admin-1",
        "pue_activation_admin",
        "HUMAN_ADMIN",
        tuple(permissions)
        or (
            ActivationPermission.VIEW_PUE_ACTIVATION,
            ActivationPermission.CHANGE_PUE_STAGE,
            ActivationPermission.TRIGGER_PUE_ROLLBACK,
            ActivationPermission.TRIGGER_PUE_KILL_SWITCH,
        ),
    )


@pytest.fixture
def control_plane():
    repository = InMemoryPueActivationRepository()
    audit = InMemoryActivationAuditSink()
    service = PueActivationService(repository=repository, audit_sink=audit, clock=lambda: NOW)
    resolver = PueActivationResolver(repository=repository, clock=lambda: NOW)
    return repository, audit, service, resolver


def scope(
    analysis="analysis-1",
    prospect="prospect-1",
    organization="org-1",
    tenant="tenant-1",
):
    return CapabilityScope(analysis, prospect, organization, tenant)


def configure(service, activation_scope, stage, **kwargs):
    return service.configure(
        scope=activation_scope,
        stage=stage,
        actor=kwargs.pop("actor", admin()),
        reason=kwargs.pop("reason", "approved ACT-001 certification fixture"),
        **kwargs,
    )


def stage4(service, activation_scope=None, fallback=None):
    return configure(
        service,
        activation_scope or ActivationScope(ScopeLevel.TENANT, tenant_id="tenant-1"),
        ActivationStage.ASK_NEXORA_SELECTED_ROUTING,
        allowed_question_types=(
            AnalyticalIntentType.COUNT_RECORDS,
            AnalyticalIntentType.TOTAL_MEASURE,
            AnalyticalIntentType.GROUP_MEASURE_BY_DIMENSION,
        ),
        fallback_policy=fallback or FallbackPolicy.PUE_IF_CERTIFIED_ELSE_LEGACY,
    )


def route(
    resolver,
    target_scope,
    *,
    intent=AnalyticalIntentType.TOTAL_MEASURE,
    status=InterpretationStatus.INTERPRETED,
    supported=True,
    failed=False,
    legacy=True,
    router=None,
):
    router = router or PueQuestionRouter()
    return router.route(
        question_id="question-1",
        scope=target_scope,
        activation=resolver.resolve(target_scope),
        question_type=intent,
        interpretation_status=status,
        pue_capability_supported=supported,
        pue_failed=failed,
        legacy_available=legacy,
    )


def test_no_config_defaults_to_shadow_only_and_legacy_authority(control_plane):
    _, _, _, resolver = control_plane
    resolution = resolver.resolve(scope())
    assert resolution.stage is ActivationStage.SHADOW_ONLY
    assert resolution.fallback_policy is FallbackPolicy.LEGACY_AUTHORITATIVE
    assert not any(
        vars for vars in resolution.features.__slots__ if getattr(resolution.features, vars)
    )


@pytest.mark.parametrize(
    ("stage", "expected"),
    [
        (ActivationStage.SHADOW_ONLY, (False, False, False, False)),
        (ActivationStage.EVIDENCE_DISCOVERY_VISIBLE, (True, False, False, False)),
        (ActivationStage.CAPABILITY_VISIBLE, (True, True, False, False)),
        (ActivationStage.SELECTED_ANSWERS, (True, True, True, False)),
        (ActivationStage.ASK_NEXORA_SELECTED_ROUTING, (True, True, True, True)),
    ],
)
def test_activation_ladder_derives_flags_without_scattered_booleans(control_plane, stage, expected):
    _, _, service, resolver = control_plane
    configure(service, ActivationScope(ScopeLevel.GLOBAL), stage)
    features = resolver.resolve(scope()).features
    assert (
        features.show_evidence_discovery,
        features.show_capability_matrix,
        features.allow_selected_answers,
        features.route_selected_questions,
    ) == expected
    assert not features.enable_confirmation_ui


def test_stage_five_cannot_be_configured(control_plane):
    _, _, service, _ = control_plane
    with pytest.raises(PermissionError):
        configure(
            service,
            ActivationScope(ScopeLevel.GLOBAL),
            ActivationStage.BROADER_AUTHORITY_REVIEW,
        )


def test_scope_precedence_is_global_org_tenant_prospect_analysis(control_plane):
    _, _, service, resolver = control_plane
    configurations = (
        (ActivationScope(ScopeLevel.GLOBAL), ActivationStage.SHADOW_ONLY),
        (
            ActivationScope(ScopeLevel.ORGANIZATION, organization_id="org-1"),
            ActivationStage.EVIDENCE_DISCOVERY_VISIBLE,
        ),
        (
            ActivationScope(ScopeLevel.TENANT, tenant_id="tenant-1"),
            ActivationStage.CAPABILITY_VISIBLE,
        ),
        (
            ActivationScope(ScopeLevel.PROSPECT, prospect_id="prospect-1"),
            ActivationStage.SELECTED_ANSWERS,
        ),
        (
            ActivationScope(ScopeLevel.ANALYSIS, analysis_id="analysis-1"),
            ActivationStage.ASK_NEXORA_SELECTED_ROUTING,
        ),
    )
    for activation_scope, stage in configurations:
        configure(service, activation_scope, stage)
    assert resolver.resolve(scope()).stage is ActivationStage.ASK_NEXORA_SELECTED_ROUTING
    assert resolver.resolve(scope(analysis="analysis-2")).stage is ActivationStage.SELECTED_ANSWERS
    assert (
        resolver.resolve(scope(analysis="analysis-2", prospect="prospect-2")).stage
        is ActivationStage.CAPABILITY_VISIBLE
    )
    assert (
        resolver.resolve(
            scope(analysis="analysis-2", prospect="prospect-2", tenant="tenant-2")
        ).stage
        is ActivationStage.EVIDENCE_DISCOVERY_VISIBLE
    )
    unrelated = scope(
        analysis="analysis-2",
        prospect="prospect-2",
        organization="org-2",
        tenant="tenant-2",
    )
    assert resolver.resolve(unrelated).stage is ActivationStage.SHADOW_ONLY


@pytest.mark.parametrize(
    ("other_scope", "expected"),
    [
        (
            scope(analysis="analysis-2", prospect="prospect-2", tenant="tenant-2"),
            ActivationStage.SHADOW_ONLY,
        ),
        (
            scope(analysis="analysis-2", prospect="prospect-2"),
            ActivationStage.CAPABILITY_VISIBLE,
        ),
        (scope(analysis="analysis-2"), ActivationStage.SELECTED_ANSWERS),
    ],
)
def test_tenant_prospect_and_analysis_activation_do_not_spill(control_plane, other_scope, expected):
    _, _, service, resolver = control_plane
    configure(
        service,
        ActivationScope(ScopeLevel.TENANT, tenant_id="tenant-1"),
        ActivationStage.CAPABILITY_VISIBLE,
    )
    configure(
        service,
        ActivationScope(ScopeLevel.PROSPECT, prospect_id="prospect-1"),
        ActivationStage.SELECTED_ANSWERS,
    )
    configure(
        service,
        ActivationScope(ScopeLevel.ANALYSIS, analysis_id="analysis-1"),
        ActivationStage.ASK_NEXORA_SELECTED_ROUTING,
    )
    assert resolver.resolve(other_scope).stage is expected


def test_prospect_only_absence_is_not_enriched_from_runtime(control_plane):
    _, _, service, resolver = control_plane
    configure(
        service,
        ActivationScope(ScopeLevel.PROSPECT, prospect_id="prospect-1"),
        ActivationStage.EVIDENCE_DISCOVERY_VISIBLE,
    )
    resolution = resolver.resolve(scope(organization=None, tenant=None))
    assert resolution.stage is ActivationStage.EVIDENCE_DISCOVERY_VISIBLE
    assert resolution.scope.organization_id is None
    assert resolution.scope.tenant_id is None


def test_expired_specific_config_falls_back_to_previous_applicable_scope(control_plane):
    _, _, service, resolver = control_plane
    configure(
        service,
        ActivationScope(ScopeLevel.GLOBAL),
        ActivationStage.EVIDENCE_DISCOVERY_VISIBLE,
    )
    configure(
        service,
        ActivationScope(ScopeLevel.TENANT, tenant_id="tenant-1"),
        ActivationStage.ASK_NEXORA_SELECTED_ROUTING,
        effective_from=NOW - timedelta(days=2),
        expires_at=NOW - timedelta(days=1),
    )
    assert resolver.resolve(scope()).stage is ActivationStage.EVIDENCE_DISCOVERY_VISIBLE


def test_global_kill_switch_overrides_stage_four_immediately(control_plane):
    _, _, service, resolver = control_plane
    stage4(service)
    service.set_kill_switch(
        enabled=True,
        actor=admin(),
        reason="critical global rollback fixture",
    )
    resolution = resolver.resolve(scope())
    decision = route(resolver, scope())
    assert resolution.stage is ActivationStage.SHADOW_ONLY
    assert not resolution.features.show_evidence_discovery
    assert decision.route is Route.ROUTE_LEGACY
    assert RoutingReason.KILL_SWITCH_ACTIVE in decision.reason_codes


def test_kill_switch_history_is_immutable_and_disable_restores_resolution(control_plane):
    repository, _, service, resolver = control_plane
    stage4(service)
    first = service.set_kill_switch(enabled=True, actor=admin(), reason="pause pilot")
    second = service.set_kill_switch(enabled=False, actor=admin(), reason="resume governed pilot")
    assert repository.kill_switch_history == (first, second)
    assert resolver.resolve(scope()).stage is ActivationStage.ASK_NEXORA_SELECTED_ROUTING


def test_rollback_is_configuration_driven_and_history_is_preserved(control_plane):
    repository, audit, service, resolver = control_plane
    config = stage4(service)
    rolled = service.rollback(
        config,
        target_stage=ActivationStage.CAPABILITY_VISIBLE,
        actor=admin(),
        reason="pilot fallback rate threshold exceeded",
    )
    history = repository.history(config.scope)
    assert len(history) == 2
    assert history[0].state is ConfigState.SUPERSEDED
    assert rolled.supersedes_activation_id == config.activation_id
    assert resolver.resolve(scope()).stage is ActivationStage.CAPABILITY_VISIBLE
    assert any(event.event_type == "PUE_ROLLBACK_TRIGGERED" for event in audit.events)


def test_rollback_does_not_supplement_actor_permissions(control_plane):
    _, _, service, _ = control_plane
    config = stage4(service)
    rollback_only = admin(ActivationPermission.TRIGGER_PUE_ROLLBACK)
    with pytest.raises(PermissionError):
        service.rollback(
            config,
            target_stage=ActivationStage.SHADOW_ONLY,
            actor=rollback_only,
            reason="insufficient combined authority fixture",
        )


def test_unauthorized_or_end_user_actor_cannot_change_activation(control_plane):
    _, _, service, _ = control_plane
    actor = ActivationActor(
        "prospect-user", "executive", "END_USER", (ActivationPermission.CHANGE_PUE_STAGE,)
    )
    with pytest.raises(PermissionError):
        configure(
            service,
            ActivationScope(ScopeLevel.GLOBAL),
            ActivationStage.EVIDENCE_DISCOVERY_VISIBLE,
            actor=actor,
        )
    with pytest.raises(PermissionError):
        configure(
            service,
            ActivationScope(ScopeLevel.GLOBAL),
            ActivationStage.EVIDENCE_DISCOVERY_VISIBLE,
            actor=admin(ActivationPermission.VIEW_PUE_ACTIVATION),
        )


def test_stage_three_allows_selected_answer_visibility_but_not_ask_routing(control_plane):
    _, _, service, resolver = control_plane
    configure(
        service,
        ActivationScope(ScopeLevel.TENANT, tenant_id="tenant-1"),
        ActivationStage.SELECTED_ANSWERS,
        allowed_question_types=(AnalyticalIntentType.TOTAL_MEASURE,),
    )
    resolution = resolver.resolve(scope())
    assert resolution.features.allow_selected_answers
    assert not resolution.features.route_selected_questions
    assert route(resolver, scope()).route is Route.SHADOW_ONLY


def test_stage_four_routes_only_allowlisted_certified_question(control_plane):
    _, _, service, resolver = control_plane
    stage4(service)
    assert route(resolver, scope()).route is Route.ROUTE_PUE
    denied = route(
        resolver,
        scope(),
        intent=AnalyticalIntentType.TIME_SERIES_MEASURE,
    )
    assert denied.route is Route.ROUTE_LEGACY
    assert RoutingReason.QUESTION_TYPE_NOT_ALLOWED in denied.reason_codes


@pytest.mark.parametrize(
    ("status", "reason"),
    [
        (InterpretationStatus.UNSUPPORTED, RoutingReason.PUE_INTERPRETATION_UNSUPPORTED),
        (InterpretationStatus.AMBIGUOUS, RoutingReason.PUE_INTERPRETATION_AMBIGUOUS),
    ],
)
def test_unsupported_and_ambiguous_questions_never_route_pue(control_plane, status, reason):
    _, _, service, resolver = control_plane
    stage4(service)
    decision = route(resolver, scope(), status=status)
    assert decision.route is Route.ROUTE_LEGACY
    assert reason in decision.reason_codes


@pytest.mark.parametrize(
    ("fallback", "legacy", "expected"),
    [
        (FallbackPolicy.LEGACY_AUTHORITATIVE, True, Route.ROUTE_LEGACY),
        (FallbackPolicy.PUE_IF_CERTIFIED_ELSE_LEGACY, True, Route.ROUTE_LEGACY),
        (FallbackPolicy.PUE_IF_CERTIFIED_ELSE_BLOCKED, True, Route.BLOCK),
        (FallbackPolicy.SHADOW_COMPARE_ONLY, True, Route.SHADOW_ONLY),
        (FallbackPolicy.LEGACY_AUTHORITATIVE, False, Route.BLOCK),
    ],
)
def test_failure_and_blocked_capability_apply_only_explicit_fallback(
    control_plane, fallback, legacy, expected
):
    _, _, service, resolver = control_plane
    stage4(service, fallback=fallback)
    failure = route(resolver, scope(), failed=True, legacy=legacy)
    blocked = route(resolver, scope(), supported=False, legacy=legacy)
    assert failure.route is expected
    assert blocked.route is expected
    assert not failure.pue_eligible and not blocked.pue_eligible


def test_failure_fallback_is_audited_without_values_or_session_state(control_plane):
    _, audit, service, resolver = control_plane
    stage4(service)
    router = PueQuestionRouter(audit_sink=audit, clock=lambda: NOW)
    decision = route(resolver, scope(), failed=True, router=router)
    event = audit.events[-1]
    assert decision.route is Route.ROUTE_LEGACY
    assert event.event_type == "PUE_ROUTE_FALLBACK"
    assert event.routing_id == decision.routing_id
    assert not hasattr(decision, "legacy_value")
    assert not hasattr(decision, "pue_value")


def test_routing_scope_mismatch_fails_closed(control_plane):
    _, _, service, resolver = control_plane
    stage4(service)
    activation = resolver.resolve(scope())
    decision = PueQuestionRouter().route(
        question_id="question-1",
        scope=scope(analysis="other"),
        activation=activation,
        question_type=AnalyticalIntentType.TOTAL_MEASURE,
        interpretation_status=InterpretationStatus.INTERPRETED,
        pue_capability_supported=True,
        pue_failed=False,
        legacy_available=True,
    )
    assert decision.route is Route.BLOCK
    assert decision.reason_codes == (RoutingReason.ROUTING_SCOPE_MISMATCH,)


def test_activation_and_routing_fingerprints_are_deterministic(control_plane):
    _, _, service, resolver = control_plane
    first = stage4(service)
    second = stage4(service)
    assert first is second
    assert resolver.resolve(scope()).fingerprint == resolver.resolve(scope()).fingerprint
    assert route(resolver, scope()).fingerprint == route(resolver, scope()).fingerprint


def test_activation_policy_drift_changes_resolution_identity(control_plane):
    repository, _, service, _ = control_plane
    stage4(service)
    first = PueActivationResolver(repository=repository, clock=lambda: NOW).resolve(scope())
    from universal_evidence.activation import PueActivationPolicy

    changed = PueActivationResolver(
        repository=repository,
        clock=lambda: NOW,
        policy=PueActivationPolicy(version="pue-activation-policy-2"),
    ).resolve(scope())
    assert first.fingerprint != changed.fingerprint


def test_184_row_stage_one_and_two_never_authorize_numeric_answer(control_plane):
    _, _, service, resolver = control_plane
    config_scope = ActivationScope(ScopeLevel.ANALYSIS, analysis_id="analysis-1")
    stage1 = configure(service, config_scope, ActivationStage.EVIDENCE_DISCOVERY_VISIBLE)
    resolution = resolver.resolve(scope())
    assert resolution.features.show_evidence_discovery
    assert not resolution.features.allow_selected_answers
    stage2 = configure(service, config_scope, ActivationStage.CAPABILITY_VISIBLE)
    resolution = resolver.resolve(scope())
    assert resolution.features.show_capability_matrix
    assert not resolution.features.allow_selected_answers
    assert "861828" not in repr((stage1, stage2, resolution))


def test_router_is_decision_only_and_has_no_result_blending_surface():
    assert not hasattr(PueQuestionRouter, "execute")
    assert not hasattr(PueQuestionRouter, "compose")
    decision_fields = {item.name for item in fields(RoutingDecision)}
    assert not {"legacy_value", "pue_value", "merged_result", "answer"} & decision_fields


@pytest.mark.parametrize(
    ("metrics", "expected"),
    [
        (ActivationMetrics(100, 90, 5, 1, 1, 0, 0.01, 0.05, 100), ActivationHealthState.HEALTHY),
        (ActivationMetrics(100, 70, 30, 2, 1, 1, 0.03, 0.30, 100), ActivationHealthState.DEGRADED),
        (
            ActivationMetrics(100, 50, 45, 5, 2, 5, 0.10, 0.45, 6000),
            ActivationHealthState.UNHEALTHY,
        ),
    ],
)
def test_health_is_objective_but_does_not_promote_stage(metrics, expected):
    health = evaluate_activation_health(metrics, clock=lambda: NOW)
    assert health.state is expected
    assert not hasattr(health, "promoted_stage")


def test_readiness_is_capped_at_stage_two_and_documents_blockers():
    report = build_activation_readiness_report()
    assert report.readiness is ReadinessState.READY_FOR_STAGE_2_PILOT
    assert "NO-GO for Stage 3/4" in report.recommendation
    assert report.blockers
    assert len(report.persistence_classification) == 9
    assert "PUE_ROUTE_FALLBACK" in report.audit_events
    assert "latency_per_stage" in report.observability_metrics


def test_activation_package_has_no_production_ui_database_or_execution_imports():
    import pathlib

    files = pathlib.Path("universal_evidence/activation").glob("*.py")
    text = "\n".join(item.read_text(encoding="utf-8") for item in files)
    for forbidden in (
        "streamlit",
        "pages.",
        "services.prospect",
        "supabase",
        "cloud_advisor.db",
        "AggregationExecutor",
        "GovernedAnswerComposer",
    ):
        assert forbidden not in text
