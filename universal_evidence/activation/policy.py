"""Versioned default-deny activation and administration policy."""

from dataclasses import dataclass

from universal_evidence.activation.models import (
    ActivationFeatureSet,
    ActivationPermission,
    ActivationStage,
)


@dataclass(frozen=True, slots=True)
class PueActivationPolicy:
    version: str = "pue-activation-policy-1"
    routing_policy_version: str = "pue-routing-policy-1"
    health_policy_version: str = "pue-activation-health-policy-1"
    maximum_config_days: int = 30
    degraded_error_rate: float = 0.02
    unhealthy_error_rate: float = 0.05
    degraded_fallback_rate: float = 0.25
    maximum_p95_latency_ms: float = 5000.0

    def features_for(self, stage: ActivationStage) -> ActivationFeatureSet:
        return ActivationFeatureSet(
            show_evidence_discovery=stage >= ActivationStage.EVIDENCE_DISCOVERY_VISIBLE,
            show_capability_matrix=stage >= ActivationStage.CAPABILITY_VISIBLE,
            allow_selected_answers=stage >= ActivationStage.SELECTED_ANSWERS,
            route_selected_questions=stage >= ActivationStage.ASK_NEXORA_SELECTED_ROUTING,
            enable_confirmation_ui=False,
        )

    @staticmethod
    def authorize(actor, permission: ActivationPermission) -> None:
        if permission not in actor.permissions:
            raise PermissionError(f"actor lacks {permission.value}")
        if actor.actor_type not in {"HUMAN_ADMIN", "CONTROL_PLANE"}:
            raise PermissionError("activation changes require an administrative actor")
