"""Bounded process-local Stage 1/2 pilot telemetry."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PilotMetricEvent:
    name: str
    scope_key: tuple[str | None, ...]
    value: int


class InMemoryPilotTelemetry:
    ALLOWED = frozenset(
        {
            "stage_1_views",
            "stage_2_views",
            "shadow_runs",
            "shadow_failures",
            "blocked_capabilities_visible",
            "activation_resolutions",
            "kill_switch_suppressions",
            "rollback_events",
            "shadow_reuse",
        }
    )

    def __init__(self) -> None:
        self._events = []

    def increment(self, name, scope_key, value=1):
        if name not in self.ALLOWED:
            raise ValueError("unregistered pilot metric")
        event = PilotMetricEvent(name, tuple(scope_key), int(value))
        self._events.append(event)
        return event

    @property
    def events(self):
        return tuple(self._events)

    def count(self, name):
        return sum(item.value for item in self._events if item.name == name)
