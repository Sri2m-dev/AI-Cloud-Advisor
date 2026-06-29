from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from connectors.common.tenant_guard import resolve_organization_id
from services.enterprise_intelligence_service import EnterpriseIntelligenceService
from services.financial_intelligence_service import FinancialIntelligenceService
from services.forecasting_service import ForecastingService
from services.predictive_accuracy_service import PredictiveAccuracyService
from services.risk_prediction_service import RiskPredictionService


@dataclass
class EnterpriseContext:
    goal: str
    organization_id: str
    knowledge_graph: dict[str, Any]
    impact: dict[str, Any]
    simulation: dict[str, Any]
    forecast: dict[str, Any]
    policies: dict[str, Any]
    approvals: dict[str, Any]
    workflow: dict[str, Any]
    historical_decisions: dict[str, Any]
    current_risks: dict[str, Any]
    business_context: dict[str, Any]
    prediction_performance: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["prediction"] = data["forecast"]
        data["financial"] = data["business_context"].get("financial", {})
        data["risk"] = data["current_risks"]
        data["reasoning"] = {"mode": "explainable_planning"}
        return data


class AgentContextManager:
    @staticmethod
    def build_context(goal: str, organization_id: str | None = None) -> dict[str, Any]:
        org_id = resolve_organization_id(organization_id)
        assets = AgentContextManager._safe_call(EnterpriseIntelligenceService.get_assets, org_id, fallback=[])
        forecast = AgentContextManager._safe_call(ForecastingService.forecast_enterprise_metrics, org_id, fallback={})
        financial = AgentContextManager._safe_call(FinancialIntelligenceService.get_financial_forecast, org_id, fallback={})
        risks = AgentContextManager._safe_call(RiskPredictionService.predict_risks, org_id, fallback={})
        performance = AgentContextManager._safe_call(PredictiveAccuracyService.get_prediction_performance, org_id, fallback={})
        enterprise_context = EnterpriseContext(
            goal=goal,
            organization_id=org_id,
            knowledge_graph={"assets": assets[:25], "asset_count": len(assets)},
            impact={"target_asset": AgentContextManager.extract_asset(goal, assets)},
            simulation={"mode": "planning_preview", "production_execution": False},
            forecast=forecast,
            policies={"requires_approval": True, "production_actions_blocked": True},
            approvals={"approval_first": True, "required": ["Business Owner", "Technology Owner"]},
            workflow={"execution_allowed": False, "approval_first": True},
            historical_decisions={"source": "agent_history", "available": True},
            current_risks=risks,
            business_context={"financial": financial, "target_asset": AgentContextManager.extract_asset(goal, assets)},
            prediction_performance=performance,
        )
        return enterprise_context.to_dict()

    @staticmethod
    def extract_asset(goal: str, assets: list[dict[str, Any]] | None = None) -> str:
        text = str(goal or "").lower()
        known = {
            "aws": "AWS",
            "azure": "Azure",
            "oracle": "Oracle",
            "datadog": "Datadog",
            "kubernetes": "Kubernetes",
            "microsoft 365": "Microsoft 365",
            "saas": "SaaS Portfolio",
        }
        for token, label in known.items():
            if token in text:
                return label
        for row in assets or []:
            name = str(row.get("name") or "")
            if name and name.lower() in text:
                return name
        return "Enterprise Portfolio"

    @staticmethod
    def _safe_call(func: Any, *args: Any, fallback: Any) -> Any:
        try:
            return func(*args)
        except Exception:
            return fallback
