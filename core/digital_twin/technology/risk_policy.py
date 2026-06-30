from __future__ import annotations

from dataclasses import dataclass, field

from core.digital_twin.technology.risk_signal import RiskSignalType


@dataclass(frozen=True, slots=True)
class RiskPolicy:
    weights: dict[str, float] = field(default_factory=lambda: {
        RiskSignalType.SECURITY.value: 1.25,
        RiskSignalType.COMPLIANCE.value: 1.15,
        RiskSignalType.OPERATIONAL.value: 1.0,
        RiskSignalType.FINANCIAL.value: 0.9,
        RiskSignalType.BUSINESS_IMPACT.value: 1.2,
        RiskSignalType.TECHNICAL_DEBT.value: 0.85,
        RiskSignalType.DR_READINESS.value: 1.1,
        RiskSignalType.PATCH.value: 1.0,
        RiskSignalType.VENDOR.value: 0.8,
    })
    medium_threshold: float = 25.0
    high_threshold: float = 50.0
    critical_threshold: float = 75.0

    def weight_for(self, risk_type: str) -> float:
        return self.weights.get(risk_type, 1.0)

    def to_dict(self) -> dict:
        return {
            "weights": dict(self.weights),
            "medium_threshold": self.medium_threshold,
            "high_threshold": self.high_threshold,
            "critical_threshold": self.critical_threshold,
        }
