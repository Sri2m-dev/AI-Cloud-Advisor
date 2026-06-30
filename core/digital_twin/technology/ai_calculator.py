from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from core.digital_twin.technology.ai_insight import AIInsight
from core.digital_twin.technology.ai_policy import AIPolicy
from core.digital_twin.technology.ai_signal import AIInsightStatus, AISignal, AISignalType
from core.digital_twin.technology.technology_node import TechnologyNode


@dataclass(frozen=True, slots=True)
class AICalculationResult:
    technology_id: str
    ai_confidence: float
    confidence_band: str
    dimensions: dict[str, Any]
    recommendations: list[dict[str, Any]]
    predictions: list[dict[str, Any]]
    root_cause_summary: str
    optimization: list[dict[str, Any]]
    forecasts: list[dict[str, Any]]
    business_impact: list[dict[str, Any]]
    automation_candidates: list[dict[str, Any]]
    insights: list[dict[str, Any]]
    signals: list[dict[str, Any]]
    policy: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "technology_id": self.technology_id,
            "ai_confidence": self.ai_confidence,
            "confidence_band": self.confidence_band,
            "dimensions": self.dimensions,
            "recommendations": self.recommendations,
            "predictions": self.predictions,
            "root_cause_summary": self.root_cause_summary,
            "optimization": self.optimization,
            "forecasts": self.forecasts,
            "business_impact": self.business_impact,
            "automation_candidates": self.automation_candidates,
            "insights": self.insights,
            "signals": self.signals,
            "policy": self.policy,
        }


class AICalculator:
    def __init__(self, policy: AIPolicy | None = None):
        self.policy = policy or AIPolicy()

    def calculate(self, node: TechnologyNode, signals: list[AISignal] | None = None) -> AICalculationResult:
        all_signals = list(signals or [])
        recommendations = self._signals_for(all_signals, AISignalType.RECOMMENDATION.value)
        predictions = self._signals_for(all_signals, AISignalType.PREDICTION.value)
        root_causes = self._signals_for(all_signals, AISignalType.ROOT_CAUSE.value)
        optimization = self._signals_for(all_signals, AISignalType.OPTIMIZATION.value)
        forecasts = self._signals_for(all_signals, AISignalType.FORECAST.value)
        business_impact = self._signals_for(all_signals, AISignalType.BUSINESS_IMPACT.value)
        automation_candidates = self._automation_candidates(all_signals)
        ai_confidence = self._confidence(all_signals)
        insights = [self._insight(signal).to_dict() for signal in all_signals]
        dimensions = {
            "Recommendations": len(recommendations),
            "Predictions": len(predictions),
            "Root Cause": len(root_causes),
            "Optimization": len(optimization),
            "Forecast": len(forecasts),
            "Business Impact": len(business_impact),
            "Confidence": ai_confidence,
            "Automation Readiness": self._automation_readiness(all_signals),
        }
        return AICalculationResult(
            technology_id=str(node.technology_id),
            ai_confidence=ai_confidence,
            confidence_band=self.policy.confidence_band(ai_confidence),
            dimensions=dimensions,
            recommendations=[signal.to_dict() for signal in recommendations],
            predictions=[signal.to_dict() for signal in predictions],
            root_cause_summary=self._root_cause_summary(root_causes),
            optimization=[signal.to_dict() for signal in optimization],
            forecasts=[signal.to_dict() for signal in forecasts],
            business_impact=[signal.to_dict() for signal in business_impact],
            automation_candidates=[signal.to_dict() for signal in automation_candidates],
            insights=insights,
            signals=[signal.to_dict() for signal in all_signals],
            policy=self.policy.to_dict(),
        )

    def apply_to_node(self, node: TechnologyNode, signals: list[AISignal] | None = None) -> AICalculationResult:
        result = self.calculate(node, signals)
        node.metadata["ai_breakdown"] = result.to_dict()
        node.metadata["ai_confidence"] = result.ai_confidence
        node.metadata["ai_confidence_band"] = result.confidence_band
        node.metadata["recommendations"] = result.recommendations
        node.metadata["predictions"] = result.predictions
        node.metadata["root_cause"] = result.root_cause_summary
        node.metadata["business_impact"] = result.business_impact
        node.metadata["automation_candidates"] = result.automation_candidates
        node.refresh_state()
        return result

    def _signals_for(self, signals: list[AISignal], signal_type: str) -> list[AISignal]:
        return sorted(
            [signal for signal in signals if signal.signal_type == signal_type],
            key=lambda signal: (signal.confidence_score, abs(signal.predicted_impact)),
            reverse=True,
        )

    def _automation_candidates(self, signals: list[AISignal]) -> list[AISignal]:
        return [
            signal
            for signal in sorted(signals, key=lambda item: item.automation_score(), reverse=True)
            if signal.status in {AIInsightStatus.AUTOMATION_READY.value, AIInsightStatus.APPROVED.value}
            and signal.confidence_score >= self.policy.automation_confidence_threshold
            and _automation_readiness(signal) >= self.policy.automation_readiness_threshold
        ]

    def _confidence(self, signals: list[AISignal]) -> float:
        if not signals:
            return 0.0
        weighted = [
            signal.confidence_score * self.policy.weight_for(signal.signal_type)
            for signal in signals
        ]
        weights = [self.policy.weight_for(signal.signal_type) for signal in signals]
        return round(sum(weighted) / sum(weights), 4)

    def _automation_readiness(self, signals: list[AISignal]) -> float:
        readiness_values = [_automation_readiness(signal) for signal in signals if _automation_readiness(signal) > 0]
        return round(sum(readiness_values) / len(readiness_values), 2) if readiness_values else 0.0

    def _root_cause_summary(self, signals: list[AISignal]) -> str:
        if not signals:
            return ""
        strongest = sorted(signals, key=lambda signal: signal.confidence_score, reverse=True)[0]
        return strongest.description

    def _insight(self, signal: AISignal) -> AIInsight:
        return AIInsight(
            technology_id=signal.technology_id,
            insight_type=signal.insight_type,
            title=signal.title,
            description=signal.description,
            recommendation=signal.recommendation,
            confidence_score=signal.confidence_score,
            predicted_impact=signal.predicted_impact,
            business_impact=signal.business_impact,
            automation_readiness=_automation_readiness(signal),
            source_signal_ids=[signal.id],
            status=signal.status,
            owner=signal.owner,
            metadata={
                "signal_type": signal.signal_type,
                "model_name": signal.model_name,
                "source_context": signal.source_context,
                **signal.metadata,
            },
        )


def _automation_readiness(signal: AISignal) -> float:
    try:
        return round(max(0.0, min(100.0, float(signal.metadata.get("automation_readiness", 0.0) or 0.0))), 2)
    except (TypeError, ValueError):
        return 0.0
