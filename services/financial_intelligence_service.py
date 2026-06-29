from __future__ import annotations

from datetime import datetime
from typing import Any

from connectors.common.tenant_guard import resolve_organization_id
from services.forecasting_service import ForecastingService
from services.risk_prediction_service import RiskPredictionService


class FinancialIntelligenceService:
    @staticmethod
    def get_financial_forecast(organization_id: str | None = None) -> dict[str, Any]:
        org_id = resolve_organization_id(organization_id)
        forecast = ForecastingService.forecast_enterprise_metrics(org_id)
        risks = RiskPredictionService.predict_risks(org_id)
        next_month = [row for row in forecast["forecasts"] if row["Horizon Days"] == 30]
        total_current = sum(row["Current"] for row in next_month)
        total_forecast = sum(row["Forecast"] for row in next_month)
        savings_target = total_current * 0.15
        savings_candidates = sorted(
            [
                {
                    "Opportunity": row["Metric"],
                    "Projected Spend": row["Forecast"],
                    "Savings Potential": round(row["Forecast"] * 0.12, 2),
                    "Action": "Review commitments, rightsizing, and usage policy.",
                }
                for row in next_month
            ],
            key=lambda row: row["Savings Potential"],
            reverse=True,
        )
        budget_risks = [row for row in risks["predictions"] if row["Risk Category"] == "Budget overrun"]
        return {
            "organization_id": org_id,
            "generated_at": datetime.utcnow().isoformat(),
            "summary": {
                "Predicted Spend": round(total_forecast, 2),
                "Current Spend": round(total_current, 2),
                "Savings Target 15%": round(savings_target, 2),
                "Can Achieve 15% Savings": "Yes" if sum(row["Savings Potential"] for row in savings_candidates) >= savings_target else "At Risk",
                "First Budget Breach": budget_risks[0]["Entity"] if budget_risks else "None forecasted",
                "Reserved Instance Focus": "Cloud Spend",
            },
            "savings_candidates": savings_candidates,
            "budget_risks": budget_risks,
        }
