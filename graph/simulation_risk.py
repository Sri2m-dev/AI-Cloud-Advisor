from __future__ import annotations

from typing import Any


WEIGHTS = {
    "technical": 0.25,
    "business": 0.25,
    "financial": 0.15,
    "security": 0.10,
    "compliance": 0.10,
    "customer_impact": 0.10,
    "operational": 0.05,
}


def calculate_simulation_risk(factors: dict[str, Any]) -> dict[str, Any]:
    breakdown = {key: _bounded(factors.get(key)) for key in WEIGHTS}
    score = round(sum(breakdown[key] * weight for key, weight in WEIGHTS.items()), 1)
    return {
        "risk_score": min(score, 100.0),
        "risk_level": risk_level(score),
        "breakdown": breakdown,
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
