from __future__ import annotations

from dataclasses import dataclass, field

from core.digital_twin.technology.health_signal import HealthSignalType


@dataclass(frozen=True, slots=True)
class HealthPolicy:
    weights: dict[str, float] = field(default_factory=lambda: {
        HealthSignalType.AVAILABILITY.value: 0.18,
        HealthSignalType.PERFORMANCE.value: 0.14,
        HealthSignalType.CAPACITY.value: 0.12,
        HealthSignalType.UTILIZATION.value: 0.10,
        HealthSignalType.RELIABILITY.value: 0.14,
        HealthSignalType.SECURITY.value: 0.12,
        HealthSignalType.OPERATIONAL_STABILITY.value: 0.10,
        HealthSignalType.COST_EFFICIENCY.value: 0.10,
    })
    degraded_threshold: float = 70.0
    warning_threshold: float = 85.0
    incident_penalty: float = 4.0
    risk_penalty_factor: float = 0.2
    cost_efficiency_budget_overrun_penalty: float = 0.5

    def weight_for(self, signal_type: str) -> float:
        return self.weights.get(signal_type, 0.05)

    def to_dict(self) -> dict:
        return {
            "weights": dict(self.weights),
            "degraded_threshold": self.degraded_threshold,
            "warning_threshold": self.warning_threshold,
            "incident_penalty": self.incident_penalty,
            "risk_penalty_factor": self.risk_penalty_factor,
            "cost_efficiency_budget_overrun_penalty": self.cost_efficiency_budget_overrun_penalty,
        }
