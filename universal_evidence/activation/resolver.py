"""Deterministic activation precedence and default-deny resolution."""

from universal_evidence.activation.fingerprint import fingerprint
from universal_evidence.activation.models import (
    ActivationResolution,
    ActivationStage,
    FallbackPolicy,
    RoutingReason,
)
from universal_evidence.activation.policy import PueActivationPolicy


class PueActivationResolver:
    def __init__(self, *, repository, policy=None, clock):
        self.repository = repository
        self.policy = policy or PueActivationPolicy()
        self.clock = clock

    def resolve(self, scope):
        now = self.clock()
        kill_switch = self.repository.current_kill_switch()
        if kill_switch is not None and kill_switch.enabled:
            return self._resolution(
                scope,
                None,
                ActivationStage.SHADOW_ONLY,
                kill_switch.fallback_policy,
                kill_switch,
                (RoutingReason.KILL_SWITCH_ACTIVE,),
            )
        candidates = []
        expired_match = False
        for config in self.repository.active_configs():
            if not config.scope.matches(scope) or config.effective_from > now:
                continue
            if config.expires_at is not None and config.expires_at <= now:
                expired_match = True
                continue
            candidates.append(config)
        config = max(candidates, key=lambda item: item.scope.level, default=None)
        if config is None:
            reasons = (
                (RoutingReason.ACTIVATION_EXPIRED, RoutingReason.SHADOW_ONLY)
                if expired_match
                else (RoutingReason.PUE_DISABLED, RoutingReason.SHADOW_ONLY)
            )
            return self._resolution(
                scope,
                None,
                ActivationStage.SHADOW_ONLY,
                FallbackPolicy.LEGACY_AUTHORITATIVE,
                kill_switch,
                reasons,
            )
        return self._resolution(
            scope,
            config,
            config.activation_stage,
            config.fallback_policy,
            kill_switch,
            (),
        )

    def _resolution(self, scope, config, stage, fallback, kill_switch, reasons):
        features = self.policy.features_for(stage)
        identity = fingerprint(
            scope,
            config.fingerprint if config else None,
            stage,
            features,
            kill_switch.fingerprint if kill_switch else None,
            fallback,
            reasons,
            self.policy.version,
        )
        return ActivationResolution(
            scope,
            config,
            stage,
            features,
            kill_switch,
            fallback,
            tuple(reasons),
            identity,
        )
