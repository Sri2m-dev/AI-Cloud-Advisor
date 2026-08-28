"""Failure-isolated Stage 1/2 pilot orchestration and visibility service."""

from __future__ import annotations

from dataclasses import fields

from universal_evidence.activation import (
    ActivationScope,
    ActivationStage,
    RoutingReason,
    ScopeLevel,
)
from universal_evidence.activation.audit import InMemoryActivationAuditSink
from universal_evidence.activation.fingerprint import fingerprint
from universal_evidence.pilot.models import PilotVisibility
from universal_evidence.pilot.telemetry import InMemoryPilotTelemetry
from universal_evidence.pilot.view_models import (
    build_upload_admission_view_model,
    build_view_model,
    unavailable_view_model,
)
from universal_evidence.shadow import ShadowStatus


class PueStage12PilotService:
    def __init__(
        self,
        *,
        activation_resolver,
        shadow_orchestrator,
        telemetry=None,
        audit_sink=None,
        clock,
    ):
        self.activation_resolver = activation_resolver
        self.shadow_orchestrator = shadow_orchestrator
        self.telemetry = telemetry or InMemoryPilotTelemetry()
        self.audit_sink = audit_sink or InMemoryActivationAuditSink()
        self.clock = clock
        self._shadow_cache = {}

    @staticmethod
    def prospect_fingerprint(prospect_analysis):
        allowed = (
            "tenant_id",
            "audit_id",
            "analysis_timestamp",
            "row_count",
            "currency_source",
            "currency_resolution_required",
        )
        values = tuple((name, getattr(prospect_analysis, name, None)) for name in allowed)
        return fingerprint(values)

    def run_or_reuse_shadow(self, request):
        request_identity = fingerprint(
            request.source.context,
            request.filename,
            request.content,
            tuple(
                (
                    item.mapping.decision_id,
                    tuple(value.row_reference for value in item.values),
                )
                for item in request.normalization_bindings
            ),
        )
        existing = self._shadow_cache.get(request_identity)
        scope_key = (
            request.source.context.analysis_id,
            request.source.context.prospect_id,
            request.source.context.organization_id,
            request.source.context.tenant_id,
        )
        if existing is not None:
            self.telemetry.increment("shadow_reuse", scope_key)
            return existing
        try:
            result = self.shadow_orchestrator.run_shadow_analysis(request)
        except Exception:  # noqa: BLE001 - pilot boundary protects prospect flow
            self.telemetry.increment("shadow_failures", scope_key)
            return None
        self._shadow_cache[request_identity] = result
        self.telemetry.increment("shadow_runs", scope_key)
        return result

    def experience(self, *, prospect_analysis, context, shadow_result):
        activation = self.activation_resolver.resolve(
            ActivationScope(
                ScopeLevel.ANALYSIS,
                organization_id=context.scope.organization_id,
                tenant_id=context.scope.tenant_id,
                prospect_id=context.scope.prospect_id,
                analysis_id=context.scope.analysis_id,
            )
        )
        self.telemetry.increment("activation_resolutions", context.scope.key)
        if RoutingReason.KILL_SWITCH_ACTIVE in activation.reason_codes:
            self.telemetry.increment("kill_switch_suppressions", context.scope.key)
            self.audit_sink.record(
                event_type="PUE_VISIBILITY_SUPPRESSED",
                actor_id="pue-stage12-pilot",
                timestamp=self.clock(),
                reason=RoutingReason.KILL_SWITCH_ACTIVE.value,
                scope_key=context.scope.key,
            )
        stage = min(activation.stage, ActivationStage.CAPABILITY_VISIBLE)
        if stage is ActivationStage.SHADOW_ONLY:
            return None
        if context.prospect_analysis_fingerprint != self.prospect_fingerprint(
            prospect_analysis
        ):
            return None
        if shadow_result is None:
            self.telemetry.increment("shadow_failures", context.scope.key)
            self._audit_shadow_failure(context.scope.key, activation)
            return unavailable_view_model(activation=activation, scope=context.scope)
        if context.shadow_fingerprint != shadow_result.fingerprint:
            return None
        if shadow_result.capability_assessment is None:
            return unavailable_view_model(
                activation=activation,
                scope=context.scope,
                shadow_fingerprint=shadow_result.fingerprint,
            )
        if shadow_result.capability_assessment.scope != context.scope:
            return None
        if shadow_result.shadow_status in {ShadowStatus.SHADOW_FAILED, ShadowStatus.SHADOW_BLOCKED}:
            self.telemetry.increment("shadow_failures", context.scope.key)
            self._audit_shadow_failure(context.scope.key, activation)
            return unavailable_view_model(
                activation=activation,
                scope=context.scope,
                shadow_fingerprint=shadow_result.fingerprint,
            )
        visibility = (
            PilotVisibility.DISCOVERY
            if stage is ActivationStage.EVIDENCE_DISCOVERY_VISIBLE
            else PilotVisibility.DISCOVERY_AND_CAPABILITY
        )
        model = build_view_model(
            activation=activation,
            shadow=shadow_result,
            visibility=visibility,
        )
        metric = "stage_1_views" if visibility is PilotVisibility.DISCOVERY else "stage_2_views"
        self.telemetry.increment(metric, context.scope.key)
        blocked = sum(item.state == "BLOCKED" for item in model.capability_items)
        if blocked:
            self.telemetry.increment(
                "blocked_capabilities_visible", context.scope.key, blocked
            )
        event_type = (
            "PUE_EVIDENCE_SURFACED"
            if visibility is PilotVisibility.DISCOVERY
            else "PUE_CAPABILITY_SURFACED"
        )
        self.audit_sink.record(
            event_type=event_type,
            actor_id="pue-stage12-pilot",
            timestamp=self.clock(),
            reason=visibility.value,
            scope_key=context.scope.key,
            activation_id=activation.config.activation_id if activation.config else None,
        )
        return model

    def experience_upload(self, admission):
        activation = self.activation_resolver.resolve(
            ActivationScope(
                ScopeLevel.ANALYSIS,
                organization_id=admission.scope.organization_id,
                tenant_id=admission.scope.tenant_id,
                prospect_id=admission.scope.prospect_id,
                analysis_id=admission.scope.analysis_id,
            )
        )
        self.telemetry.increment("activation_resolutions", admission.scope.key)
        if RoutingReason.KILL_SWITCH_ACTIVE in activation.reason_codes:
            self.telemetry.increment("kill_switch_suppressions", admission.scope.key)
            return None
        stage = min(activation.stage, ActivationStage.CAPABILITY_VISIBLE)
        if stage is ActivationStage.SHADOW_ONLY:
            return None
        visibility = (
            PilotVisibility.DISCOVERY
            if stage is ActivationStage.EVIDENCE_DISCOVERY_VISIBLE
            else PilotVisibility.DISCOVERY_AND_CAPABILITY
        )
        model = build_upload_admission_view_model(
            activation=activation, admission=admission, visibility=visibility
        )
        self.telemetry.increment(
            "stage_1_views" if visibility is PilotVisibility.DISCOVERY else "stage_2_views",
            admission.scope.key,
        )
        return model

    def _audit_shadow_failure(self, scope_key, activation):
        self.audit_sink.record(
            event_type="PUE_SHADOW_FAILURE",
            actor_id="pue-stage12-pilot",
            timestamp=self.clock(),
            reason="shadow result unavailable for pilot display",
            scope_key=scope_key,
            activation_id=activation.config.activation_id if activation.config else None,
        )


def assert_no_analytical_value_surface():
    forbidden = {"amount", "value", "answer", "result", "currency_amount"}
    from universal_evidence.pilot.models import PuePilotViewModel

    names = {item.name for item in fields(PuePilotViewModel)}
    return not names & forbidden
