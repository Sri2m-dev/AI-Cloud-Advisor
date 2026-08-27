"""Objective PUE activation health classification without auto-promotion."""

from universal_evidence.activation.models import (
    ActivationHealthState,
    PueActivationHealth,
)
from universal_evidence.activation.policy import PueActivationPolicy


def evaluate_activation_health(metrics, *, clock, policy=None, paused=False):
    policy = policy or PueActivationPolicy()
    reasons = []
    if paused:
        state = ActivationHealthState.PAUSED
        reasons.append("activation is administratively paused")
    elif metrics.error_rate >= policy.unhealthy_error_rate:
        state = ActivationHealthState.UNHEALTHY
        reasons.append("error rate exceeds unhealthy threshold")
    elif (
        metrics.error_rate >= policy.degraded_error_rate
        or metrics.fallback_rate >= policy.degraded_fallback_rate
        or metrics.p95_latency_ms > policy.maximum_p95_latency_ms
    ):
        state = ActivationHealthState.DEGRADED
        reasons.append("one or more pilot health thresholds are degraded")
    else:
        state = ActivationHealthState.HEALTHY
        reasons.append("observed metrics are within readiness thresholds")
    return PueActivationHealth(
        state,
        metrics,
        tuple(reasons),
        clock(),
        policy.health_policy_version,
    )
