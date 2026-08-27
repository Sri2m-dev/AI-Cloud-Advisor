"""Decision-only PUE question router; it never interprets or executes."""

from universal_evidence.activation.fingerprint import fingerprint
from universal_evidence.activation.models import (
    ActivationStage,
    FallbackPolicy,
    Route,
    RoutingDecision,
    RoutingReason,
)
from universal_evidence.activation.policy import PueActivationPolicy
from universal_evidence.interpretation import InterpretationStatus


class PueQuestionRouter:
    def __init__(self, *, policy=None, audit_sink=None, clock=None):
        self.policy = policy or PueActivationPolicy()
        self.audit_sink = audit_sink
        self.clock = clock

    def route(
        self,
        *,
        question_id,
        scope,
        activation,
        question_type,
        interpretation_status,
        pue_capability_supported,
        pue_failed,
        legacy_available,
    ):
        if scope != activation.scope:
            return self._decision(
                question_id,
                scope,
                activation,
                question_type,
                False,
                legacy_available,
                Route.BLOCK,
                (RoutingReason.ROUTING_SCOPE_MISMATCH,),
            )
        if activation.kill_switch is not None and activation.kill_switch.enabled:
            return self._fallback(
                question_id,
                scope,
                activation,
                question_type,
                False,
                legacy_available,
                (RoutingReason.KILL_SWITCH_ACTIVE,),
            )
        if activation.stage < ActivationStage.ASK_NEXORA_SELECTED_ROUTING:
            return self._decision(
                question_id,
                scope,
                activation,
                question_type,
                False,
                legacy_available,
                Route.SHADOW_ONLY,
                (RoutingReason.SHADOW_ONLY,),
            )
        allowed = bool(
            activation.config and question_type in activation.config.allowed_question_types
        )
        if not allowed:
            return self._fallback(
                question_id,
                scope,
                activation,
                question_type,
                False,
                legacy_available,
                (RoutingReason.QUESTION_TYPE_NOT_ALLOWED,),
            )
        if interpretation_status is InterpretationStatus.AMBIGUOUS:
            return self._fallback(
                question_id,
                scope,
                activation,
                question_type,
                False,
                legacy_available,
                (RoutingReason.PUE_INTERPRETATION_AMBIGUOUS,),
            )
        if interpretation_status is not InterpretationStatus.INTERPRETED:
            return self._fallback(
                question_id,
                scope,
                activation,
                question_type,
                False,
                legacy_available,
                (RoutingReason.PUE_INTERPRETATION_UNSUPPORTED,),
            )
        if pue_failed:
            return self._fallback(
                question_id,
                scope,
                activation,
                question_type,
                False,
                legacy_available,
                (RoutingReason.PUE_FAILURE,),
            )
        if not pue_capability_supported:
            return self._fallback(
                question_id,
                scope,
                activation,
                question_type,
                False,
                legacy_available,
                (RoutingReason.PUE_CAPABILITY_BLOCKED,),
            )
        return self._decision(
            question_id,
            scope,
            activation,
            question_type,
            True,
            legacy_available,
            Route.ROUTE_PUE,
            (RoutingReason.PUE_CAPABILITY_SUPPORTED, RoutingReason.PUE_ROUTE_SELECTED),
        )

    def _fallback(
        self,
        question_id,
        scope,
        activation,
        question_type,
        pue_eligible,
        legacy_available,
        reasons,
    ):
        fallback = activation.fallback_policy
        if fallback is FallbackPolicy.SHADOW_COMPARE_ONLY:
            route = Route.SHADOW_ONLY
        elif fallback is FallbackPolicy.PUE_IF_CERTIFIED_ELSE_BLOCKED:
            route = Route.BLOCK
        elif legacy_available:
            route = Route.ROUTE_LEGACY
            reasons = (*reasons, RoutingReason.LEGACY_FALLBACK_SELECTED)
        else:
            route = Route.BLOCK
        return self._decision(
            question_id,
            scope,
            activation,
            question_type,
            pue_eligible,
            legacy_available,
            route,
            reasons,
        )

    def _decision(
        self,
        question_id,
        scope,
        activation,
        question_type,
        pue_eligible,
        legacy_eligible,
        route,
        reasons,
    ):
        config_id = activation.config.activation_id if activation.config else None
        identity = fingerprint(
            question_id,
            scope,
            activation.fingerprint,
            question_type,
            pue_eligible,
            legacy_eligible,
            route,
            reasons,
            self.policy.routing_policy_version,
        )
        decision = RoutingDecision(
            "pue-routing-" + identity[:24],
            question_id,
            scope,
            activation.stage,
            question_type,
            pue_eligible,
            legacy_eligible,
            route,
            tuple(reasons),
            config_id,
            self.policy.routing_policy_version,
            identity,
        )
        if self.audit_sink is not None and self.clock is not None:
            event_type = (
                "PUE_ROUTE_FALLBACK"
                if route in {Route.ROUTE_LEGACY, Route.BLOCK}
                else "PUE_ROUTE_SELECTED"
            )
            self.audit_sink.record(
                event_type=event_type,
                actor_id="pue-routing-policy",
                timestamp=self.clock(),
                reason=",".join(item.value for item in reasons),
                routing_id=decision.routing_id,
            )
        return decision
