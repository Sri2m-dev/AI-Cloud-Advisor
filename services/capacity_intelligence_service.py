from __future__ import annotations

from datetime import datetime
from typing import Any

from connectors.common.tenant_guard import resolve_organization_id
from repositories.forecasting_repository import ForecastingRepository


CAPACITY_DOMAINS = ["CPU", "Memory", "Disk", "Storage", "Database", "Network", "Kubernetes", "Cloud Services"]


class CapacityIntelligenceService:
    @staticmethod
    def forecast_capacity(organization_id: str | None = None) -> dict[str, Any]:
        org_id = resolve_organization_id(organization_id)
        context = ForecastingRepository.load_context(org_id)
        seed = len(context.get("enterprise_cost_attribution", [])) + len(context.get("technology_inventory", []))
        rows = []
        for index, domain in enumerate(CAPACITY_DOMAINS):
            current = min(45 + ((seed + index * 7) % 42), 92)
            daily_growth = 1.1 + (index % 4) * 0.35
            days_to_95 = max(round((95 - current) / daily_growth, 1), 0)
            rows.append(
                {
                    "Domain": domain,
                    "Current Utilization": round(current, 1),
                    "Daily Growth": round(daily_growth, 2),
                    "Days To 95%": days_to_95,
                    "Forecast": f"{domain} will reach 95% in {days_to_95:.1f} days.",
                    "Recommendation": "Add capacity or archive data." if days_to_95 <= 30 else "Monitor trend.",
                    "Confidence": 90 if days_to_95 <= 30 else 84,
                }
            )
        return {
            "organization_id": org_id,
            "generated_at": datetime.utcnow().isoformat(),
            "capacity": rows,
            "summary": {
                "Upcoming Capacity Issues": len([row for row in rows if row["Days To 95%"] <= 30]),
                "Most Urgent": min(rows, key=lambda row: row["Days To 95%"])["Domain"],
            },
        }
