"""Authorized append-only activation, rollback, and kill-switch administration."""

from universal_evidence.activation.fingerprint import fingerprint
from universal_evidence.activation.models import (
    ActivationPermission,
    ActivationStage,
    ConfigState,
    FallbackPolicy,
    KillSwitchConfig,
    PueActivationConfig,
    RollbackPolicy,
)
from universal_evidence.activation.policy import PueActivationPolicy


class PueActivationService:
    def __init__(
        self,
        *,
        repository,
        audit_sink,
        policy=None,
        clock,
        operations=None,
        operation_context=None,
    ):
        self.repository = repository
        self.audit_sink = audit_sink
        self.policy = policy or PueActivationPolicy()
        self.clock = clock
        self.operations = operations
        self.operation_context = operation_context

    def configure(
        self,
        *,
        scope,
        stage,
        actor,
        reason,
        allowed_question_types=(),
        enabled_capabilities=(),
        visible_surfaces=(),
        fallback_policy=FallbackPolicy.LEGACY_AUTHORITATIVE,
        rollback_policy=RollbackPolicy.SHADOW_ONLY,
        effective_from=None,
        expires_at=None,
    ):
        self.policy.authorize(actor, ActivationPermission.CHANGE_PUE_STAGE)
        if stage is ActivationStage.BROADER_AUTHORITY_REVIEW:
            raise PermissionError("Stage 5 is definition-only in PUE-ACT-001")
        if not str(reason).strip():
            raise ValueError("activation reason is required")
        configured_at = self.clock()
        effective_from = effective_from or configured_at
        if expires_at is not None and expires_at <= effective_from:
            raise ValueError("activation expiry must follow effective time")
        previous = self.repository.history(scope)
        identity = fingerprint(
            scope,
            stage,
            tuple(enabled_capabilities),
            tuple(visible_surfaces),
            tuple(allowed_question_types),
            fallback_policy,
            rollback_policy,
            effective_from,
            expires_at,
            actor,
            reason,
            self.policy.version,
        )
        config = PueActivationConfig(
            "pue-activation-" + identity[:24],
            scope,
            stage,
            tuple(enabled_capabilities),
            tuple(visible_surfaces),
            tuple(allowed_question_types),
            fallback_policy,
            rollback_policy,
            effective_from,
            expires_at,
            actor,
            configured_at,
            reason,
            self.policy.version,
            ConfigState.ACTIVE,
            previous[-1].activation_id if previous else None,
            identity,
        )
        self._operation(
            "ACTIVATION_CHANGED",
            actor,
            scope,
            reason,
            attributes={
                "old_state": previous[-1].activation_stage.value if previous else None,
                "new_state": stage.value,
                "phase": "AUTHORIZED",
            },
        )
        stored = self.repository.store(config)
        self.audit_sink.record(
            event_type="PUE_ACTIVATION_CHANGED",
            actor_id=actor.actor_id,
            timestamp=configured_at,
            reason=reason,
            scope_key=scope.key,
            activation_id=stored.activation_id,
        )
        return stored

    def configure_authorized(self, *, authorization, scope, **values):
        from universal_evidence.activation.models import ActivationPermission

        authorization.authorize_scope(scope)
        actor = authorization.activation_actor(ActivationPermission.CHANGE_PUE_STAGE)
        return self.configure(scope=scope, actor=actor, **values)

    def rollback(self, config, *, target_stage, actor, reason):
        self.policy.authorize(actor, ActivationPermission.TRIGGER_PUE_ROLLBACK)
        self.policy.authorize(actor, ActivationPermission.CHANGE_PUE_STAGE)
        if target_stage >= config.activation_stage:
            raise ValueError("rollback must reduce activation stage")
        rolled = self.configure(
            scope=config.scope,
            stage=target_stage,
            actor=actor,
            reason=reason,
            fallback_policy=config.fallback_policy,
            rollback_policy=config.rollback_policy,
        )
        self.audit_sink.record(
            event_type="PUE_ROLLBACK_TRIGGERED",
            actor_id=actor.actor_id,
            timestamp=self.clock(),
            reason=reason,
            scope_key=config.scope.key,
            activation_id=rolled.activation_id,
        )
        return rolled

    def set_kill_switch(
        self,
        *,
        enabled,
        actor,
        reason,
        allow_shadow_execution=True,
        fallback_policy=FallbackPolicy.LEGACY_AUTHORITATIVE,
    ):
        self.policy.authorize(actor, ActivationPermission.TRIGGER_PUE_KILL_SWITCH)
        if not str(reason).strip():
            raise ValueError("kill-switch reason is required")
        now = self.clock()
        identity = fingerprint(
            enabled,
            allow_shadow_execution,
            fallback_policy,
            actor,
            reason,
            now,
            self.policy.version,
        )
        config = KillSwitchConfig(
            "pue-kill-switch-" + identity[:24],
            enabled,
            allow_shadow_execution,
            fallback_policy,
            actor,
            reason,
            now,
            self.policy.version,
            identity,
        )
        self._operation(
            "KILL_SWITCH_ENABLED" if enabled else "KILL_SWITCH_DISABLED",
            actor,
            None,
            reason,
            attributes={"enabled": bool(enabled), "phase": "AUTHORIZED"},
        )
        stored = self.repository.store_kill_switch(config)
        self.audit_sink.record(
            event_type="PUE_KILL_SWITCH_CHANGED",
            actor_id=actor.actor_id,
            timestamp=now,
            reason=reason,
            activation_id=stored.kill_switch_id,
        )
        return stored

    def set_kill_switch_authorized(self, *, authorization, enabled, reason, **values):
        from universal_evidence.activation.models import ActivationPermission

        actor = authorization.activation_actor(
            ActivationPermission.TRIGGER_PUE_KILL_SWITCH
        )
        return self.set_kill_switch(
            enabled=enabled,
            actor=actor,
            reason=reason,
            **values,
        )

    def _operation(self, event_type, actor, scope, reason, *, attributes):
        from universal_evidence.operations import GovernedEventType, observe, workflow_context

        observe(
            self.operations,
            GovernedEventType(event_type),
            workflow_context(self.operation_context, scope, actor=actor),
            attributes={"reason": reason, **attributes},
        )
