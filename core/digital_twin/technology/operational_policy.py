from __future__ import annotations

from dataclasses import asdict, dataclass

from core.digital_twin.technology.operational_signal import OperationalSeverity


@dataclass(frozen=True, slots=True)
class OperationalPolicy:
    base_health: float = 100.0
    incident_penalty: float = 12.0
    alert_penalty: float = 6.0
    performance_penalty: float = 8.0
    change_penalty: float = 2.0
    maintenance_penalty: float = 3.0
    deployment_window_days: int = 14
    change_window_days: int = 30
    mttr_target_minutes: float = 120.0
    mtbf_target_minutes: float = 10080.0
    healthy_threshold: float = 90.0
    watch_threshold: float = 75.0
    degraded_threshold: float = 60.0

    def severity_multiplier(self, severity: str) -> float:
        return {
            OperationalSeverity.CRITICAL.value: 2.0,
            OperationalSeverity.HIGH.value: 1.5,
            OperationalSeverity.MEDIUM.value: 1.0,
            OperationalSeverity.LOW.value: 0.5,
            OperationalSeverity.INFO.value: 0.25,
        }.get(severity, 1.0)

    def status_for_health(self, health: float) -> str:
        if health >= self.healthy_threshold:
            return "Healthy"
        if health >= self.watch_threshold:
            return "Watch"
        if health >= self.degraded_threshold:
            return "Degraded"
        return "Critical"

    def to_dict(self) -> dict:
        return asdict(self)
