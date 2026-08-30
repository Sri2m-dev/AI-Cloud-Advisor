"""Liveness, readiness, and bounded operations status for ACT-011."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Callable, Iterable

from universal_evidence.persistence import LifecycleScope


class HealthState(str, Enum):
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    UNHEALTHY = "UNHEALTHY"


@dataclass(frozen=True, slots=True)
class ComponentHealth:
    component: str
    state: HealthState
    reason: str


@dataclass(frozen=True, slots=True)
class OperationsStatus:
    live: bool
    ready: bool
    state: HealthState
    components: tuple[ComponentHealth, ...]
    kill_switch_enabled: bool
    activation_state: str
    recent_failures: int
    recent_security_rejections: int
    recent_blocks: int


class GovernedOperationsHealthService:
    def __init__(self, probes: Iterable[tuple[str, Callable[[], object]]]):
        self.probes = tuple(probes)

    def status(
        self,
        *,
        telemetry=(),
        kill_switch_enabled=False,
        activation_state="UNKNOWN",
    ) -> OperationsStatus:
        components = tuple(self._probe(name, probe) for name, probe in self.probes)
        ready = bool(components) and all(
            item.state is not HealthState.UNHEALTHY for item in components
        )
        state = (
            HealthState.UNHEALTHY
            if not components or any(item.state is HealthState.UNHEALTHY for item in components)
            else HealthState.DEGRADED
            if kill_switch_enabled or any(item.state is HealthState.DEGRADED for item in components)
            else HealthState.HEALTHY
        )
        events = tuple(telemetry)
        return OperationsStatus(
            True,
            ready and not kill_switch_enabled,
            state,
            components,
            bool(kill_switch_enabled),
            activation_state,
            sum(item.severity.value == "ERROR" for item in events),
            sum(item.severity.value == "SECURITY" for item in events),
            sum(item.outcome == "BLOCKED" for item in events),
        )

    @staticmethod
    def _probe(name, probe):
        try:
            result = probe()
            if result is False:
                return ComponentHealth(name, HealthState.UNHEALTHY, "probe failed")
            if isinstance(result, HealthState):
                return ComponentHealth(name, result, "probe completed")
            return ComponentHealth(name, HealthState.HEALTHY, "probe completed")
        except Exception as exc:
            return ComponentHealth(name, HealthState.UNHEALTHY, type(exc).__name__)


def standard_runtime_probes(runtime, scope: LifecycleScope, *, registry=None, ask_service=None):
    """Build non-sensitive probes for the governed workflow composition."""

    def lifecycle_ready():
        runtime.lifecycle.list_scope(scope, include_purged=True)
        return True

    return (
        ("application_runtime", lambda: True),
        ("durable_lifecycle_db", lifecycle_ready),
        ("migration_schema", lifecycle_ready),
        ("audit_repository", lifecycle_ready),
        ("canonical_registry", lambda: registry is not None),
        ("universal_evidence_runtime", lambda: runtime is not None),
        ("ask_governed_service", lambda: ask_service is not None),
    )
