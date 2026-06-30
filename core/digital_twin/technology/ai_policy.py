from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True, slots=True)
class AIPolicy:
    high_confidence_threshold: float = 0.85
    medium_confidence_threshold: float = 0.65
    automation_confidence_threshold: float = 0.8
    automation_readiness_threshold: float = 75.0
    minimum_business_impact_for_priority: float = 10000.0
    recommendation_weight: float = 1.0
    prediction_weight: float = 0.9
    root_cause_weight: float = 1.1
    optimization_weight: float = 1.0
    forecast_weight: float = 0.8
    business_impact_weight: float = 1.0

    def weight_for(self, signal_type: str) -> float:
        normalized = signal_type.strip().lower()
        if normalized == "prediction":
            return self.prediction_weight
        if normalized == "root cause":
            return self.root_cause_weight
        if normalized == "optimization":
            return self.optimization_weight
        if normalized == "forecast":
            return self.forecast_weight
        if normalized == "business impact":
            return self.business_impact_weight
        return self.recommendation_weight

    def confidence_band(self, confidence: float) -> str:
        if confidence >= self.high_confidence_threshold:
            return "High"
        if confidence >= self.medium_confidence_threshold:
            return "Medium"
        return "Low"

    def to_dict(self) -> dict:
        return asdict(self)
