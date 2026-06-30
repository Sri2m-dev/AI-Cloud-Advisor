from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Any

from core.digital_twin.technology.cost_policy import CostPolicy
from core.digital_twin.technology.cost_signal import CostHealthStatus, CostSignal, cost_health_for_variance
from core.digital_twin.technology.technology_node import TechnologyNode


@dataclass(frozen=True, slots=True)
class CostCalculationResult:
    technology_id: str
    current_cost: float
    monthly_cost: float
    annual_cost: float
    forecast: float
    budget: float
    budget_variance: float
    budget_variance_percent: float
    cost_health: str
    optimization_opportunity: float
    potential_savings: float
    chargeback: dict[str, float]
    showback: dict[str, float]
    roi: float
    business_value: float
    dimensions: dict[str, float]
    signals: list[dict[str, Any]]
    policy: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "technology_id": self.technology_id,
            "current_cost": self.current_cost,
            "monthly_cost": self.monthly_cost,
            "annual_cost": self.annual_cost,
            "forecast": self.forecast,
            "budget": self.budget,
            "budget_variance": self.budget_variance,
            "budget_variance_percent": self.budget_variance_percent,
            "cost_health": self.cost_health,
            "optimization_opportunity": self.optimization_opportunity,
            "potential_savings": self.potential_savings,
            "chargeback": self.chargeback,
            "showback": self.showback,
            "roi": self.roi,
            "business_value": self.business_value,
            "dimensions": self.dimensions,
            "signals": self.signals,
            "policy": self.policy,
        }


class CostCalculator:
    def __init__(self, policy: CostPolicy | None = None):
        self.policy = policy or CostPolicy()

    def calculate(self, node: TechnologyNode, signals: list[CostSignal] | None = None) -> CostCalculationResult:
        explicit_signals = list(signals or [])
        all_signals = explicit_signals if explicit_signals else self._baseline_signals(node)
        dimensions = self._dimensions(node, all_signals)
        monthly_cost = round(sum(dimensions.values()), 2)
        current_cost = monthly_cost
        annual_cost = round(monthly_cost * 12, 2)
        trend = self._average([signal.trend for signal in all_signals], default=self.policy.forecast_growth_default)
        forecast = round(monthly_cost * (1 + trend), 2)
        budget = _number(node.metadata, "budget", "monthly_budget")
        variance = round(monthly_cost - budget, 2) if budget else 0.0
        variance_percent = round((variance / budget) * 100, 2) if budget else 0.0
        cost_health = cost_health_for_variance(variance_percent)
        utilization = _number(node.metadata, "utilization", "utilization_score", default=100.0) / 100
        utilization_gap = max(0.0, self.policy.utilization_savings_threshold - utilization)
        optimization = round(monthly_cost * self.policy.optimization_target_percent + monthly_cost * utilization_gap, 2)
        savings = round(max(0.0, optimization), 2)
        business_value = _number(
            node.metadata,
            "business_value",
            default=annual_cost * self.policy.roi_default_business_value_multiplier,
        )
        roi = round(((business_value - annual_cost) / annual_cost) * 100, 2) if annual_cost else 0.0
        return CostCalculationResult(
            technology_id=str(node.technology_id),
            current_cost=current_cost,
            monthly_cost=monthly_cost,
            annual_cost=annual_cost,
            forecast=forecast,
            budget=budget,
            budget_variance=variance,
            budget_variance_percent=variance_percent,
            cost_health=cost_health,
            optimization_opportunity=optimization,
            potential_savings=savings,
            chargeback=self._group_amounts(all_signals, "cost_center"),
            showback=self._group_amounts(all_signals, "business_unit"),
            roi=roi,
            business_value=round(business_value, 2),
            dimensions=dimensions,
            signals=[signal.to_dict() for signal in all_signals],
            policy=self.policy.to_dict(),
        )

    def apply_to_node(self, node: TechnologyNode, signals: list[CostSignal] | None = None) -> CostCalculationResult:
        result = self.calculate(node, signals)
        node.cost = result.current_cost
        node.monthly_cost = result.monthly_cost
        node.annual_cost = result.annual_cost
        node.metadata["cost_breakdown"] = result.to_dict()
        node.metadata["forecast_cost"] = result.forecast
        node.metadata["optimization_opportunity"] = result.optimization_opportunity
        node.metadata["savings_opportunity"] = result.potential_savings
        node.metadata["roi"] = result.roi
        node.refresh_state()
        return result

    def _baseline_signals(self, node: TechnologyNode) -> list[CostSignal]:
        signals = []
        if node.infrastructure_layer:
            for resource in node.infrastructure_layer.resources.values():
                if resource.cost <= 0:
                    continue
                signals.append(
                    CostSignal.create(
                        node.technology_id,
                        provider=resource.provider,
                        service=resource.resource_type,
                        amount=resource.cost,
                        signal_type=resource.resource_type,
                        account=resource.account_id,
                        environment=resource.environment,
                        usage=float(resource.metadata.get("usage", 0) or 0),
                        trend=float(resource.metadata.get("trend", self.policy.forecast_growth_default) or 0),
                        confidence_score=1.0,
                        metadata={
                            "resource_id": resource.resource_id,
                            "resource_entity_id": str(resource.entity_id) if resource.entity_id else "",
                        },
                    )
                )
        if not signals and node.monthly_cost:
            signals.append(
                CostSignal.create(
                    node.technology_id,
                    provider=node.cloud_provider or node.vendor,
                    service=node.technology_type,
                    amount=node.monthly_cost,
                    signal_type=node.technology_type,
                    environment=node.environment,
                    confidence_score=1.0,
                )
            )
        return signals

    @staticmethod
    def _dimensions(node: TechnologyNode, signals: list[CostSignal]) -> dict[str, float]:
        dimensions: dict[str, float] = defaultdict(float)
        for signal in signals:
            dimensions[signal.signal_type] += signal.effective_amount()
        return {key: round(value, 2) for key, value in sorted(dimensions.items())}

    @staticmethod
    def _group_amounts(signals: list[CostSignal], attribute: str) -> dict[str, float]:
        grouped: dict[str, float] = defaultdict(float)
        for signal in signals:
            key = getattr(signal, attribute) or "Unassigned"
            grouped[key] += signal.effective_amount()
        return {key: round(value, 2) for key, value in sorted(grouped.items())}

    @staticmethod
    def _average(values: list[float], default: float) -> float:
        return round(sum(values) / len(values), 4) if values else default


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
