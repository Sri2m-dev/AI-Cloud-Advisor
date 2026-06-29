from __future__ import annotations

from datetime import datetime
from typing import Any

from connectors.common.tenant_guard import resolve_organization_id
from services.financial_intelligence_service import FinancialIntelligenceService
from services.forecasting_service import ForecastingService
from services.risk_prediction_service import RiskPredictionService
from services.simulation_service import SimulationService


class PredictiveAIService:
    @staticmethod
    def get_predictive_recommendations(organization_id: str | None = None) -> dict[str, Any]:
        org_id = resolve_organization_id(organization_id)
        forecast = ForecastingService.forecast_enterprise_metrics(org_id)
        financial = FinancialIntelligenceService.get_financial_forecast(org_id)
        risks = RiskPredictionService.predict_risks(org_id)
        top_forecast = max(
            [row for row in forecast["forecasts"] if row["Horizon Days"] == 30],
            key=lambda row: row["Forecast"],
            default={"Metric": "Cloud Spend", "Forecast": 0},
        )
        simulation = SimulationService.run_simulation(
            asset="AWS" if "Cloud" in top_forecast["Metric"] else "Oracle",
            scenario_type="Financial",
            scenario="Reserved Instance purchase",
            organization_id=org_id,
            persist=False,
        )
        risk_label = simulation["risk_analysis"]["level"]
        reasoning_decision = (
            "Proceed with approval gates"
            if risk_label in {"Critical", "High", "Medium"}
            else "Proceed"
        )
        recommendation = {
            "Prediction": f"{top_forecast['Metric']} forecast is {top_forecast['Forecast']:,.0f}",
            "Impact": "Budget Exceeded" if financial["summary"]["Can Achieve 15% Savings"] == "At Risk" else "Savings opportunity",
            "Simulation": simulation["simulation_name"],
            "Reasoning": reasoning_decision,
            "Recommendation": "Purchase Reserved Instances" if top_forecast["Metric"] == "Cloud Spend" else "Execute highest ROI optimization",
            "Confidence": min(top_forecast["Confidence"], simulation["ai_recommendation"]["Confidence"]),
        }
        return {
            "organization_id": org_id,
            "generated_at": datetime.utcnow().isoformat(),
            "recommendations": [recommendation],
            "forecast": forecast,
            "financial": financial,
            "risks": risks,
        }
