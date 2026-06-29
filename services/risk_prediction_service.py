from __future__ import annotations

from datetime import datetime
from typing import Any

from connectors.common.tenant_guard import resolve_organization_id
from repositories.forecasting_repository import ForecastingRepository
from services.technology_health_service import TechnologyHealthService


def _safe_float(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


class RiskPredictionService:
    @staticmethod
    def predict_risks(organization_id: str | None = None) -> dict[str, Any]:
        org_id = resolve_organization_id(organization_id)
        context = ForecastingRepository.load_context(org_id)
        health = TechnologyHealthService.get_health_matrix()
        predictions = []
        for row in health[:40]:
            probability = min(max(100 - _safe_float(row.get("Health Score")), 8) + row.get("Dependencies", 0) * 3, 96)
            predictions.append(
                {
                    "Entity": row["Technology"],
                    "Type": row.get("Type", "Technology"),
                    "Risk Category": "Technology failure",
                    "Failure Probability": round(probability, 1),
                    "Recommendation": "Upgrade within 21 days." if probability >= 70 else "Monitor and review next maintenance cycle.",
                    "Confidence": 92 if probability >= 70 else 86,
                }
            )
        predictions.extend(RiskPredictionService._budget_risks(context))
        predictions.extend(RiskPredictionService._renewal_risks(context))
        predictions.extend(RiskPredictionService._vendor_risks(context))
        return {
            "organization_id": org_id,
            "generated_at": datetime.utcnow().isoformat(),
            "predictions": sorted(predictions, key=lambda row: row["Failure Probability"], reverse=True),
            "summary": {
                "Predicted Risks": len(predictions),
                "Predicted Failures": len([row for row in predictions if row["Failure Probability"] >= 70]),
                "Highest Risk": max(predictions, key=lambda row: row["Failure Probability"], default={}).get("Entity", "Unknown"),
            },
        }

    @staticmethod
    def _budget_risks(context: dict[str, Any]) -> list[dict[str, Any]]:
        rows = []
        for row in context.get("mart_budget_vs_actual", []):
            budget = _safe_float(row.get("budget") or row.get("budget_amount") or row.get("planned_cost"))
            actual = _safe_float(row.get("actual") or row.get("actual_cost") or row.get("total_cost") or row.get("cost"))
            if not budget:
                continue
            probability = min((actual / budget) * 100, 98)
            rows.append(
                {
                    "Entity": row.get("department") or row.get("cost_center") or "Budget",
                    "Type": "Budget",
                    "Risk Category": "Budget overrun",
                    "Failure Probability": round(probability, 1),
                    "Recommendation": "Freeze discretionary spend and review forecast drivers." if probability >= 85 else "Monitor monthly variance.",
                    "Confidence": 90,
                }
            )
        return rows

    @staticmethod
    def _renewal_risks(context: dict[str, Any]) -> list[dict[str, Any]]:
        rows = []
        for row in context.get("vw_saas_renewal_risk", []):
            days = _safe_float(row.get("days_remaining") or row.get("days_until_renewal") or 999)
            probability = max(95 - days, 10) if days <= 90 else 12
            rows.append(
                {
                    "Entity": row.get("vendor") or row.get("vendor_name") or "SaaS Vendor",
                    "Type": "SaaS",
                    "Risk Category": "Unnecessary renewal",
                    "Failure Probability": round(min(probability, 95), 1),
                    "Recommendation": "Validate usage and reclaim inactive licenses before renewal.",
                    "Confidence": 88,
                }
            )
        return rows

    @staticmethod
    def _vendor_risks(context: dict[str, Any]) -> list[dict[str, Any]]:
        rows = []
        for row in context.get("vw_vendor_spend", [])[:15]:
            spend = _safe_float(row.get("annual_spend") or row.get("total_spend") or row.get("spend") or row.get("amount"))
            probability = min(spend / 50_000 * 15, 85)
            if probability < 20:
                continue
            rows.append(
                {
                    "Entity": row.get("vendor") or row.get("vendor_name") or "Vendor",
                    "Type": "Vendor",
                    "Risk Category": "Vendor concentration",
                    "Failure Probability": round(probability, 1),
                    "Recommendation": "Review contract leverage, exit options, and alternative suppliers.",
                    "Confidence": 84,
                }
            )
        return rows
