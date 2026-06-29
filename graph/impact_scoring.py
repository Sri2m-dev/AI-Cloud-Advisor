from __future__ import annotations

from typing import Any


WEIGHTS = {
    "business_criticality": 0.30,
    "dependency_count": 0.20,
    "revenue_impact": 0.15,
    "cost_exposure": 0.10,
    "operational_risk": 0.10,
    "security_risk": 0.05,
    "compliance": 0.05,
    "executive_visibility": 0.05,
}


def calculate_impact_score(metrics: dict[str, Any]) -> dict[str, Any]:
    component_scores = {
        "business_criticality": _bounded(metrics.get("business_criticality")),
        "dependency_count": _scale(metrics.get("dependency_count"), 30),
        "revenue_impact": _scale_currency(metrics.get("revenue_impact"), 10_000_000),
        "cost_exposure": _scale_currency(metrics.get("cost_exposure"), 2_000_000),
        "operational_risk": _bounded(metrics.get("operational_risk")),
        "security_risk": _bounded(metrics.get("security_risk")),
        "compliance": _bounded(metrics.get("compliance")),
        "executive_visibility": _bounded(metrics.get("executive_visibility")),
    }
    score = round(
        sum(component_scores[key] * weight for key, weight in WEIGHTS.items()),
        1,
    )
    return {
        "impact_score": min(score, 100.0),
        "risk_score": min(round(score * 0.92 + component_scores["operational_risk"] * 0.08, 1), 100.0),
        "risk_level": risk_level(score),
        "components": component_scores,
        "weights": WEIGHTS,
    }


def risk_level(score: float) -> str:
    if score >= 85:
        return "Critical"
    if score >= 70:
        return "High"
    if score >= 45:
        return "Medium"
    return "Low"


def _bounded(value: Any) -> float:
    try:
        return max(0.0, min(float(value or 0), 100.0))
    except (TypeError, ValueError):
        return 0.0


def _scale(value: Any, high_watermark: float) -> float:
    try:
        number = float(value or 0)
    except (TypeError, ValueError):
        number = 0.0
    if high_watermark <= 0:
        return 0.0
    return max(0.0, min((number / high_watermark) * 100, 100.0))


def _scale_currency(value: Any, high_watermark: float) -> float:
    return _scale(value, high_watermark)
