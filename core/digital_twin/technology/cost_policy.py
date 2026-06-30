from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CostPolicy:
    forecast_growth_default: float = 0.08
    optimization_target_percent: float = 0.12
    utilization_savings_threshold: float = 0.35
    roi_default_business_value_multiplier: float = 1.5
    healthy_variance_threshold: float = 5.0
    watch_variance_threshold: float = 15.0
    warning_variance_threshold: float = 30.0

    def to_dict(self) -> dict:
        return {
            "forecast_growth_default": self.forecast_growth_default,
            "optimization_target_percent": self.optimization_target_percent,
            "utilization_savings_threshold": self.utilization_savings_threshold,
            "roi_default_business_value_multiplier": self.roi_default_business_value_multiplier,
            "healthy_variance_threshold": self.healthy_variance_threshold,
            "watch_variance_threshold": self.watch_variance_threshold,
            "warning_variance_threshold": self.warning_variance_threshold,
        }
