from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Any

from core.digital_twin.technology.risk_policy import RiskPolicy
from core.digital_twin.technology.risk_signal import RiskSeverity, RiskSignal, RiskSignalType
from core.digital_twin.technology.technology_node import TechnologyNode


@dataclass(frozen=True, slots=True)
class RiskCalculationResult:
    technology_id: str
    risk_score: float
    risk_posture: str
    dimensions: dict[str, float]
    critical_risks: list[dict[str, Any]]
    mitigations: list[dict[str, Any]]
    signals: list[dict[str, Any]]
    policy: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "technology_id": self.technology_id,
            "risk_score": self.risk_score,
            "risk_posture": self.risk_posture,
            "dimensions": self.dimensions,
            "critical_risks": self.critical_risks,
            "mitigations": self.mitigations,
            "signals": self.signals,
            "policy": self.policy,
        }


class RiskCalculator:
    def __init__(self, policy: RiskPolicy | None = None):
        self.policy = policy or RiskPolicy()

    def calculate(self, node: TechnologyNode, signals: list[RiskSignal] | None = None) -> RiskCalculationResult:
        explicit_signals = list(signals or [])
        all_signals = explicit_signals if explicit_signals else self._baseline_signals(node)
        dimensions = self._dimensions(all_signals)
        risk_score = round(max(dimensions.values(), default=0.0), 2)
        posture = self.posture_for_score(risk_score)
        critical = [
            signal.to_dict()
            for signal in all_signals
            if signal.severity == RiskSeverity.CRITICAL.value or signal.score >= self.policy.critical_threshold
        ]
        mitigations = [
            {
                "risk_type": signal.risk_type,
                "severity": signal.severity,
                "mitigation": signal.mitigation,
                "owner": signal.owner,
                "status": signal.status,
                "affected_entity": signal.affected_entity,
            }
            for signal in all_signals
            if signal.mitigation
        ]
        return RiskCalculationResult(
            technology_id=str(node.technology_id),
            risk_score=risk_score,
            risk_posture=posture,
            dimensions=dimensions,
            critical_risks=critical,
            mitigations=mitigations,
            signals=[signal.to_dict() for signal in all_signals],
            policy=self.policy.to_dict(),
        )

    def apply_to_node(self, node: TechnologyNode, signals: list[RiskSignal] | None = None) -> RiskCalculationResult:
        result = self.calculate(node, signals)
        node.risk = result.risk_score
        node.metadata["risk_breakdown"] = result.to_dict()
        node.metadata["risk_posture"] = result.risk_posture
        node.refresh_state()
        return result

    def posture_for_score(self, score: float) -> str:
        if score >= self.policy.critical_threshold:
            return RiskSeverity.CRITICAL.value
        if score >= self.policy.high_threshold:
            return RiskSeverity.HIGH.value
        if score >= self.policy.medium_threshold:
            return RiskSeverity.MEDIUM.value
        return RiskSeverity.LOW.value

    def _baseline_signals(self, node: TechnologyNode) -> list[RiskSignal]:
        baseline = []
        if node.risk:
            baseline.append(
                RiskSignal.create(
                    node.technology_id,
                    RiskSignalType.OPERATIONAL.value,
                    severity="",
                    probability=node.risk,
                    impact=100.0,
                    source_system="technology_twin",
                    affected_entity=node.name,
                    mitigation=str(node.metadata.get("mitigation", "")),
                    owner=str(node.owner_id or ""),
                    metadata={"baseline": True},
                )
            )
        patch_score = _number(node.metadata, "patch_risk", "patch_score")
        if patch_score:
            baseline.append(
                RiskSignal.create(
                    node.technology_id,
                    RiskSignalType.PATCH.value,
                    severity="",
                    probability=patch_score,
                    impact=80.0,
                    source_system="technology_twin",
                    affected_entity=node.name,
                    mitigation=str(node.metadata.get("patch_mitigation", "")),
                    owner=str(node.owner_id or ""),
                    metadata={"baseline": True},
                )
            )
        return baseline

    def _dimensions(self, signals: list[RiskSignal]) -> dict[str, float]:
        grouped: dict[str, list[RiskSignal]] = defaultdict(list)
        for signal in signals:
            grouped[signal.risk_type].append(signal)
        dimensions = {}
        for risk_type, items in grouped.items():
            weighted = [signal.weighted_score(self.policy.weight_for(risk_type)) for signal in items]
            dimensions[risk_type] = round(min(100.0, max(weighted, default=0.0)), 2)
        for risk_type in self.policy.weights:
            dimensions.setdefault(risk_type, 0.0)
        return dict(sorted(dimensions.items()))


def _number(metadata: dict[str, Any], *keys: str, default: float = 0.0) -> float:
    for key in keys:
        value = metadata.get(key)
        if value is None:
            continue
        try:
            return float(value)
        except (TypeError, ValueError):
            continue
    return default
