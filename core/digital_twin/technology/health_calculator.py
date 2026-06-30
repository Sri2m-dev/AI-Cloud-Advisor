from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Any

from core.digital_twin.technology.health_policy import HealthPolicy
from core.digital_twin.technology.health_signal import HealthSignal, HealthSignalStatus, HealthSignalType, status_for_score
from core.digital_twin.technology.infrastructure_layer import InfrastructureLayer
from core.digital_twin.technology.technology_health import TechnologyHealth
from core.digital_twin.technology.technology_node import TechnologyNode
from core.digital_twin.technology.technology_state import TechnologyState


@dataclass(frozen=True, slots=True)
class HealthCalculationResult:
    technology_id: str
    health_score: float
    status: str
    dimensions: dict[str, float]
    signals: list[dict[str, Any]]
    policy: dict[str, Any]
    issues: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "technology_id": self.technology_id,
            "health_score": self.health_score,
            "status": self.status,
            "dimensions": self.dimensions,
            "signals": self.signals,
            "policy": self.policy,
            "issues": self.issues,
        }


class HealthCalculator:
    def __init__(self, policy: HealthPolicy | None = None):
        self.policy = policy or HealthPolicy()

    def calculate(
        self,
        node: TechnologyNode,
        signals: list[HealthSignal] | None = None,
    ) -> HealthCalculationResult:
        all_signals = self._baseline_signals(node) + list(signals or [])
        by_type: dict[str, list[HealthSignal]] = defaultdict(list)
        for signal in all_signals:
            by_type[signal.signal_type].append(signal)

        dimensions = {}
        for signal_type in self.policy.weights:
            dimensions[signal_type] = self._score_dimension(signal_type, by_type.get(signal_type, []))

        weighted_total = sum(dimensions[name] * self.policy.weight_for(name) for name in dimensions)
        weight_total = sum(self.policy.weight_for(name) for name in dimensions) or 1.0
        health_score = round(weighted_total / weight_total, 2)
        status = self.status_for_score(health_score)
        return HealthCalculationResult(
            technology_id=str(node.technology_id),
            health_score=health_score,
            status=status,
            dimensions=dimensions,
            signals=[signal.to_dict() for signal in all_signals],
            policy=self.policy.to_dict(),
            issues=self._issues(dimensions),
        )

    def apply_to_node(
        self,
        node: TechnologyNode,
        signals: list[HealthSignal] | None = None,
    ) -> HealthCalculationResult:
        result = self.calculate(node, signals)
        if node.health is None:
            node.health = TechnologyHealth(node.technology_id)
        node.health.availability = result.dimensions[HealthSignalType.AVAILABILITY.value]
        node.health.performance = result.dimensions[HealthSignalType.PERFORMANCE.value]
        node.health.capacity = result.dimensions[HealthSignalType.CAPACITY.value]
        node.health.utilization = result.dimensions[HealthSignalType.UTILIZATION.value]
        node.health.reliability = result.dimensions[HealthSignalType.RELIABILITY.value]
        node.health.operational_score = result.dimensions[HealthSignalType.OPERATIONAL_STABILITY.value]
        node.health.health_score = result.health_score
        node.health.metadata["health_breakdown"] = result.to_dict()
        if node.state is None:
            node.state = TechnologyState(node.technology_id)
        node.state.refresh(
            health_score=result.health_score,
            risk_score=node.risk,
            cost_score=100.0 - result.dimensions[HealthSignalType.COST_EFFICIENCY.value],
            security_score=result.dimensions[HealthSignalType.SECURITY.value],
            operations_score=result.dimensions[HealthSignalType.OPERATIONAL_STABILITY.value],
            business_impact_score=_number(node.metadata, "business_impact_score", "criticality", default=0.0),
        )
        node.status = node.state.status
        return result

    def calculate_layer_health(self, layer: InfrastructureLayer) -> float:
        layer.refresh()
        return layer.health_score

    def status_for_score(self, score: float) -> str:
        if score < self.policy.degraded_threshold:
            return HealthSignalStatus.DEGRADED.value
        if score < self.policy.warning_threshold:
            return HealthSignalStatus.WARNING.value
        return HealthSignalStatus.HEALTHY.value

    def _baseline_signals(self, node: TechnologyNode) -> list[HealthSignal]:
        health = node.health or TechnologyHealth(node.technology_id)
        layer_health = node.infrastructure_layer.health_score if node.infrastructure_layer else health.operational_score
        incident_count = _number(node.metadata, "incidents", "open_incidents")
        open_alerts = _number(node.metadata, "open_alerts")
        budget = _number(node.metadata, "budget")
        monthly_cost = node.monthly_cost or node.cost
        cost_efficiency = 100.0
        if budget > 0 and monthly_cost > budget:
            overrun = ((monthly_cost - budget) / budget) * 100
            cost_efficiency = max(0.0, 100.0 - overrun * self.policy.cost_efficiency_budget_overrun_penalty)
        operational_stability = max(0.0, layer_health - (incident_count + open_alerts) * self.policy.incident_penalty)
        risk_adjusted_security = max(0.0, _number(node.metadata, "security_score", "security", default=100.0) - node.risk * self.policy.risk_penalty_factor)
        return [
            HealthSignal.create(node.technology_id, HealthSignalType.AVAILABILITY.value, health.availability, self.policy.weight_for(HealthSignalType.AVAILABILITY.value), "technology_twin", 1.0),
            HealthSignal.create(node.technology_id, HealthSignalType.PERFORMANCE.value, health.performance, self.policy.weight_for(HealthSignalType.PERFORMANCE.value), "technology_twin", 1.0),
            HealthSignal.create(node.technology_id, HealthSignalType.CAPACITY.value, health.capacity, self.policy.weight_for(HealthSignalType.CAPACITY.value), "technology_twin", 1.0),
            HealthSignal.create(node.technology_id, HealthSignalType.UTILIZATION.value, health.utilization, self.policy.weight_for(HealthSignalType.UTILIZATION.value), "technology_twin", 1.0),
            HealthSignal.create(node.technology_id, HealthSignalType.RELIABILITY.value, health.reliability, self.policy.weight_for(HealthSignalType.RELIABILITY.value), "technology_twin", 1.0),
            HealthSignal.create(node.technology_id, HealthSignalType.SECURITY.value, risk_adjusted_security, self.policy.weight_for(HealthSignalType.SECURITY.value), "technology_twin", 1.0),
            HealthSignal.create(node.technology_id, HealthSignalType.OPERATIONAL_STABILITY.value, operational_stability, self.policy.weight_for(HealthSignalType.OPERATIONAL_STABILITY.value), "technology_twin", 1.0),
            HealthSignal.create(node.technology_id, HealthSignalType.COST_EFFICIENCY.value, cost_efficiency, self.policy.weight_for(HealthSignalType.COST_EFFICIENCY.value), "technology_twin", 1.0),
        ]

    @staticmethod
    def _score_dimension(signal_type: str, signals: list[HealthSignal]) -> float:
        if not signals:
            return 100.0
        weighted = sum(signal.weighted_score() for signal in signals)
        weights = sum(signal.effective_weight() for signal in signals)
        return round(weighted / weights, 2) if weights else 100.0

    @staticmethod
    def _issues(dimensions: dict[str, float]) -> list[str]:
        return [
            f"{name} is {status_for_score(score).lower()} at {score:.1f}%"
            for name, score in dimensions.items()
            if score < 85
        ]


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
