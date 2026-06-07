from __future__ import annotations

from typing import Any


def approval_roi(monthly_savings: float, yearly_impact: float) -> float:
    monthly = float(monthly_savings or 0)
    yearly = float(yearly_impact or 0)
    if monthly <= 0:
        return 0.0
    return yearly / monthly


def savings_projection(items: list[dict[str, Any]]) -> dict[str, float]:
    monthly = sum(float(item.get("monthly_savings") or 0) for item in items)
    yearly = monthly * 12
    return {
        "monthly_savings": monthly,
        "yearly_impact": yearly,
        "approval_roi": approval_roi(monthly, yearly),
    }

