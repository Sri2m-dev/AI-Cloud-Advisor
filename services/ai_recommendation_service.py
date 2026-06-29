from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from connectors.common.tenant_guard import resolve_organization_id
from services.ai_context_service import AIContextService
from services.ai_insight_service import AIInsightService
from services.supabase_client import supabase


class AIRecommendationService:
    HISTORY_TABLE = "ai_recommendation_history"
    PRIORITY_ORDER = {"Critical": 0, "High": 1, "Medium": 2, "Low": 3}
    SEVERITY_TO_PRIORITY = {
        "Critical": "Critical",
        "High": "High",
        "Medium": "Medium",
        "Low": "Low",
    }

    @staticmethod
    def get_cost_recommendations(organization_id: str | None = None) -> list[dict[str, Any]]:
        context = AIRecommendationService._context(organization_id)
        recommendations = []
        for insight in AIInsightService.get_cost_insights(context["organization"]["organization_id"]):
            title = insight.get("title", "")
            if "Unattributed spend" in title:
                recommendations.append(
                    AIRecommendationService._from_insight(
                        insight,
                        category="Cost Optimization",
                        recommendation=(
                            "Approve deterministic provider/account/category mappings for the unattributed cost queue, "
                            "then require resource-level asset IDs in future imports."
                        ),
                        technical_impact="Increases cost attribution completeness and improves chargeback data quality.",
                        estimated_savings=AIRecommendationService._estimated_unattributed_opportunity(context),
                        owner="FinOps",
                        expected_completion="4 hours",
                        context=context,
                        scoring={"business": 85, "technical": 80, "financial": 90, "urgency": 80},
                    )
                )
            elif "highest-cost business capability" in title:
                recommendations.append(
                    AIRecommendationService._from_insight(
                        insight,
                        category="Cost Optimization",
                        recommendation="Review the top capability for savings opportunities, reservation coverage, and architecture optimization.",
                        technical_impact="Targets the largest cost pool for rightsizing and service-level optimization.",
                        estimated_savings=AIRecommendationService._percent_of_evidence_cost(insight, 0.08),
                        owner="FinOps",
                        expected_completion="1 week",
                        context=context,
                        scoring={"business": 75, "technical": 65, "financial": 75, "urgency": 55},
                    )
                )
            elif "highest-spend application" in title:
                recommendations.append(
                    AIRecommendationService._from_insight(
                        insight,
                        category="Cost Optimization",
                        recommendation="Run an application-level cost review for usage spikes, idle capacity, and managed service configuration.",
                        technical_impact="Improves application-level cost efficiency and aligns spend with ownership.",
                        estimated_savings=AIRecommendationService._percent_of_evidence_cost(insight, 0.05),
                        owner="Application Owner",
                        expected_completion="3 days",
                        context=context,
                        scoring={"business": 70, "technical": 70, "financial": 70, "urgency": 50},
                    )
                )
            elif "cost center" in title:
                recommendations.append(
                    AIRecommendationService._from_insight(
                        insight,
                        category="Cost Optimization",
                        recommendation="Attach monthly budget targets and variance thresholds to the top cost center.",
                        technical_impact="Enables budget overrun detection and chargeback automation.",
                        estimated_savings=0,
                        owner="Finance",
                        expected_completion="2 days",
                        context=context,
                        scoring={"business": 60, "technical": 45, "financial": 55, "urgency": 35},
                    )
                )
        return AIRecommendationService._assign_ids(recommendations)

    @staticmethod
    def get_governance_recommendations(organization_id: str | None = None) -> list[dict[str, Any]]:
        context = AIRecommendationService._context(organization_id)
        recommendations = []
        for insight in AIInsightService.get_governance_insights(context["organization"]["organization_id"]):
            if "low governance score" in insight.get("title", ""):
                recommendations.append(
                    AIRecommendationService._from_insight(
                        insight,
                        category="Governance",
                        recommendation="Complete capability governance remediation: confirm executive owner, validate relationship graph, and review cost mappings.",
                        technical_impact="Raises capability governance score and improves auditability of the Digital Twin.",
                        estimated_savings=0,
                        estimated_risk_reduction=12,
                        owner="Governance Lead",
                        expected_completion="2 days",
                        context=context,
                        scoring={"business": 72, "technical": 65, "financial": 30, "urgency": 55},
                    )
                )
            elif "without owners" in insight.get("title", ""):
                recommendations.append(
                    AIRecommendationService._from_insight(
                        insight,
                        category="Governance",
                        recommendation="Assign technical, business, and executive owners to unowned enterprise assets.",
                        technical_impact="Closes accountability gaps in ownership intelligence.",
                        estimated_savings=0,
                        estimated_risk_reduction=25,
                        owner="Client Administrator",
                        expected_completion="1 day",
                        context=context,
                        scoring={"business": 90, "technical": 75, "financial": 30, "urgency": 85},
                    )
                )
        return AIRecommendationService._assign_ids(recommendations)

    @staticmethod
    def get_operational_recommendations(organization_id: str | None = None) -> list[dict[str, Any]]:
        context = AIRecommendationService._context(organization_id)
        recommendations = []
        for insight in AIInsightService.get_operational_insights(context["organization"]["organization_id"]):
            if "connectors are failing" in insight.get("description", "") or "connector is currently failed" in insight.get("description", ""):
                recommendations.append(
                    AIRecommendationService._from_insight(
                        insight,
                        category="Cloud Discovery",
                        recommendation=AIRecommendationService._connector_repair_steps(insight),
                        technical_impact="Restores connector sync and increases discovery, cost, and relationship freshness.",
                        estimated_savings=0,
                        estimated_risk_reduction=18,
                        owner="Client Cloud Administrator",
                        expected_completion="2 hours",
                        context=context,
                        scoring={"business": 88, "technical": 92, "financial": 40, "urgency": 95},
                    )
                )
            elif "Discovery coverage is incomplete" in insight.get("title", ""):
                recommendations.append(
                    AIRecommendationService._from_insight(
                        insight,
                        category="Operations",
                        recommendation="Complete onboarding for unconfigured connectors and rerun scheduled discovery.",
                        technical_impact="Increases enterprise inventory coverage across cloud, SaaS, and AI platforms.",
                        estimated_savings=0,
                        estimated_risk_reduction=15,
                        owner="Platform Administrator",
                        expected_completion="1 day",
                        context=context,
                        scoring={"business": 78, "technical": 85, "financial": 35, "urgency": 70},
                    )
                )
            elif "not refreshed" in insight.get("title", ""):
                recommendations.append(
                    AIRecommendationService._from_insight(
                        insight,
                        category="Operations",
                        recommendation="Run discovery scheduler now and verify connector cadence.",
                        technical_impact="Refreshes stale enterprise assets and improves AI context freshness.",
                        estimated_savings=0,
                        estimated_risk_reduction=10,
                        owner="Operations",
                        expected_completion="2 hours",
                        context=context,
                        scoring={"business": 65, "technical": 75, "financial": 20, "urgency": 65},
                    )
                )
        return AIRecommendationService._assign_ids(recommendations)

    @staticmethod
    def get_security_recommendations(organization_id: str | None = None) -> list[dict[str, Any]]:
        context = AIRecommendationService._context(organization_id)
        recommendations = []
        for insight in AIInsightService.get_operational_insights(context["organization"]["organization_id"]):
            evidence = insight.get("evidence") or {}
            if any(AIRecommendationService._looks_like_permission_issue(row) for row in evidence.values() if isinstance(row, dict)):
                recommendations.append(
                    AIRecommendationService._from_insight(
                        insight,
                        category="Security",
                        recommendation="Review cloud connector IAM permissions and credential expiry; grant least-privilege read permissions required for discovery.",
                        technical_impact="Reduces credential drift and restores secure discovery access.",
                        estimated_savings=0,
                        estimated_risk_reduction=20,
                        owner="Security Administrator",
                        expected_completion="2 hours",
                        context=context,
                        scoring={"business": 82, "technical": 88, "financial": 25, "urgency": 90},
                    )
                )
        return AIRecommendationService._assign_ids(recommendations)

    @staticmethod
    def get_business_recommendations(organization_id: str | None = None) -> list[dict[str, Any]]:
        context = AIRecommendationService._context(organization_id)
        recommendations = []
        for insight in AIInsightService.get_business_insights(context["organization"]["organization_id"]):
            if "blast radius" in insight.get("title", ""):
                recommendations.append(
                    AIRecommendationService._from_insight(
                        insight,
                        category="Business Continuity",
                        recommendation="Validate recovery objectives, dependency mapping, and continuity controls for the highest-blast-radius application.",
                        technical_impact="Improves resilience planning for the most cost-exposed application path.",
                        estimated_savings=0,
                        estimated_risk_reduction=22,
                        owner="Business Service Owner",
                        expected_completion="1 week",
                        context=context,
                        scoring={"business": 88, "technical": 76, "financial": 55, "urgency": 70},
                    )
                )
            elif "highest operational risk capability" in insight.get("title", ""):
                recommendations.append(
                    AIRecommendationService._from_insight(
                        insight,
                        category="Business Continuity",
                        recommendation="Review capability health, governance score, and dependency chain with the executive owner.",
                        technical_impact="Improves capability-level risk visibility and resilience planning.",
                        estimated_savings=0,
                        estimated_risk_reduction=16,
                        owner="Executive Owner",
                        expected_completion="3 days",
                        context=context,
                        scoring={"business": 80, "technical": 65, "financial": 40, "urgency": 60},
                    )
                )
        return AIRecommendationService._assign_ids(recommendations)

    @staticmethod
    def get_priority_actions(organization_id: str | None = None) -> list[dict[str, Any]]:
        recommendations = AIRecommendationService.get_all_recommendations(organization_id, persist=False)["recommendations"]
        return recommendations[:10]

    @staticmethod
    def get_all_recommendations(
        organization_id: str | None = None,
        persist: bool = True,
    ) -> dict[str, Any]:
        org_id = resolve_organization_id(organization_id)
        recommendations = (
            AIRecommendationService.get_cost_recommendations(org_id)
            + AIRecommendationService.get_governance_recommendations(org_id)
            + AIRecommendationService.get_operational_recommendations(org_id)
            + AIRecommendationService.get_security_recommendations(org_id)
            + AIRecommendationService.get_business_recommendations(org_id)
        )
        recommendations = AIRecommendationService._assign_ids(
            sorted(
                recommendations,
                key=lambda row: (
                    AIRecommendationService.PRIORITY_ORDER.get(row.get("priority"), 99),
                    -float(row.get("overall_score") or 0),
                    -int(row.get("confidence") or 0),
                ),
            )
        )
        persistence = {"status": "SKIPPED", "rows": 0}
        if persist:
            persistence = AIRecommendationService._persist_recommendations(org_id, recommendations)
        return {
            "organization_id": org_id,
            "summary": AIRecommendationService._summary(recommendations),
            "recommendations": recommendations,
            "priority_actions": recommendations[:10],
            "persistence": persistence,
        }

    @staticmethod
    def _from_insight(
        insight: dict[str, Any],
        category: str,
        recommendation: str,
        technical_impact: str,
        estimated_savings: float,
        owner: str,
        expected_completion: str,
        context: dict[str, Any],
        scoring: dict[str, float],
        estimated_risk_reduction: float = 0,
    ) -> dict[str, Any]:
        confidence = int(insight.get("confidence") or 0)
        score = AIRecommendationService._score(scoring, confidence)
        priority = AIRecommendationService._priority(score, insight.get("severity"))
        evidence = insight.get("evidence") or {}
        return {
            "recommendation_id": "",
            "category": category,
            "priority": priority,
            "severity": insight.get("severity") or "Medium",
            "title": insight.get("title"),
            "problem": insight.get("description"),
            "description": insight.get("description"),
            "recommendation": recommendation,
            "business_impact": insight.get("business_impact"),
            "technical_impact": technical_impact,
            "estimated_savings": round(float(estimated_savings or 0), 2),
            "estimated_risk_reduction": round(float(estimated_risk_reduction or 0), 1),
            "owner": owner,
            "confidence": confidence,
            "overall_score": score,
            "source": "AI Insight Engine",
            "evidence": evidence,
            "explainability": {
                "why_generated": insight.get("description"),
                "expected_benefit": insight.get("business_impact"),
                "confidence_basis": "Deterministic AI insight evidence from the enterprise context builder.",
                "scoring": {
                    "business_impact": scoring.get("business", 0),
                    "technical_impact": scoring.get("technical", 0),
                    "financial_impact": scoring.get("financial", 0),
                    "urgency": scoring.get("urgency", 0),
                    "confidence": confidence,
                },
            },
            "related_assets": AIRecommendationService._related_assets(evidence, context),
            "related_applications": AIRecommendationService._related_applications(evidence, context),
            "related_capabilities": AIRecommendationService._related_capabilities(evidence, context),
            "status": "Open",
            "expected_completion": expected_completion,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

    @staticmethod
    def _score(scoring: dict[str, float], confidence: float) -> float:
        return round(
            (float(scoring.get("business") or 0) * 0.35)
            + (float(scoring.get("technical") or 0) * 0.25)
            + (float(scoring.get("financial") or 0) * 0.20)
            + (float(scoring.get("urgency") or 0) * 0.10)
            + (float(confidence or 0) * 0.10),
            1,
        )

    @staticmethod
    def _priority(score: float, severity: str | None) -> str:
        if severity == "Critical" or score >= 85:
            return "Critical"
        if severity == "High" or score >= 70:
            return "High"
        if score >= 50:
            return "Medium"
        return "Low"

    @staticmethod
    def _persist_recommendations(organization_id: str, recommendations: list[dict[str, Any]]) -> dict[str, Any]:
        if not recommendations:
            return {"status": "SUCCESS", "rows": 0}
        now = datetime.now(timezone.utc).isoformat()
        rows = [
            {
                "recommendation_id": row.get("recommendation_id"),
                "organization_id": organization_id,
                "category": row.get("category"),
                "priority": row.get("priority"),
                "severity": row.get("severity"),
                "title": row.get("title"),
                "description": row.get("description"),
                "recommendation": row.get("recommendation"),
                "business_impact": row.get("business_impact"),
                "technical_impact": row.get("technical_impact"),
                "estimated_savings": row.get("estimated_savings") or 0,
                "estimated_risk_reduction": row.get("estimated_risk_reduction") or 0,
                "owner": row.get("owner"),
                "confidence": row.get("confidence") or 0,
                "overall_score": row.get("overall_score") or 0,
                "source": row.get("source"),
                "evidence": {
                    "raw": row.get("evidence") or {},
                    "explainability": row.get("explainability") or {},
                    "expected_completion": row.get("expected_completion"),
                },
                "related_assets": row.get("related_assets") or [],
                "related_applications": row.get("related_applications") or [],
                "related_capabilities": row.get("related_capabilities") or [],
                "status": row.get("status") or "Open",
                "created_at": row.get("created_at") or now,
                "updated_at": now,
            }
            for row in recommendations
        ]
        try:
            supabase.table(AIRecommendationService.HISTORY_TABLE).upsert(rows).execute()
            return {"status": "SUCCESS", "rows": len(rows)}
        except Exception as exc:
            return {"status": "SKIPPED", "rows": 0, "error": str(exc)}

    @staticmethod
    def _assign_ids(recommendations: list[dict[str, Any]]) -> list[dict[str, Any]]:
        for index, row in enumerate(recommendations, start=1):
            row["recommendation_id"] = f"AI-{index:06d}"
        return recommendations

    @staticmethod
    def _summary(recommendations: list[dict[str, Any]]) -> dict[str, Any]:
        priorities = {priority: 0 for priority in ["Critical", "High", "Medium", "Low"]}
        categories: dict[str, int] = {}
        owners: dict[str, int] = {}
        for row in recommendations:
            priorities[row.get("priority") or "Medium"] = priorities.get(row.get("priority") or "Medium", 0) + 1
            categories[row.get("category") or "Uncategorized"] = categories.get(row.get("category") or "Uncategorized", 0) + 1
            owners[row.get("owner") or "Unassigned"] = owners.get(row.get("owner") or "Unassigned", 0) + 1
        confidence_values = [float(row.get("confidence") or 0) for row in recommendations]
        risk_values = [float(row.get("estimated_risk_reduction") or 0) for row in recommendations if row.get("estimated_risk_reduction")]
        return {
            "total_recommendations": len(recommendations),
            "critical": priorities.get("Critical", 0),
            "high": priorities.get("High", 0),
            "medium": priorities.get("Medium", 0),
            "low": priorities.get("Low", 0),
            "estimated_savings": round(sum(float(row.get("estimated_savings") or 0) for row in recommendations), 2),
            "estimated_risk_reduction": round(sum(risk_values) / len(risk_values), 1) if risk_values else 0,
            "average_confidence": round(sum(confidence_values) / len(confidence_values), 1) if confidence_values else 0,
            "priority_distribution": [{"Priority": key, "Recommendations": value} for key, value in priorities.items()],
            "category_distribution": [
                {"Category": key, "Recommendations": value}
                for key, value in sorted(categories.items(), key=lambda item: item[1], reverse=True)
            ],
            "owner_workload": [
                {"Owner": key, "Recommendations": value}
                for key, value in sorted(owners.items(), key=lambda item: item[1], reverse=True)
            ],
        }

    @staticmethod
    def _context(organization_id: str | None = None) -> dict[str, Any]:
        return AIContextService.build_enterprise_context(organization_id)

    @staticmethod
    def _estimated_unattributed_opportunity(context: dict[str, Any]) -> float:
        unattributed = float(context.get("cost", {}).get("summary", {}).get("unattributed_cost") or 0)
        return round(unattributed * 0.08, 2)

    @staticmethod
    def _percent_of_evidence_cost(insight: dict[str, Any], percent: float) -> float:
        return round(float((insight.get("evidence") or {}).get("cost") or 0) * percent, 2)

    @staticmethod
    def _connector_repair_steps(insight: dict[str, Any]) -> str:
        evidence = insight.get("evidence") or {}
        connectors = ", ".join(sorted(evidence.keys())) or "failed connector"
        if "AWS" in evidence:
            return (
                "Grant ec2:DescribeInstances, rds:DescribeDBInstances, s3:ListAllMyBuckets, "
                "and rerun AWS discovery."
            )
        if "Azure" in evidence:
            return "Grant Azure Reader access, validate tenant/client credentials, and rerun Azure discovery."
        return f"Validate credentials and required read permissions for {connectors}, then rerun discovery."

    @staticmethod
    def _looks_like_permission_issue(row: dict[str, Any]) -> bool:
        text = " ".join(str(row.get(key) or "") for key in ["last_error", "recommended_action"]).lower()
        return any(token in text for token in ["permission", "credential", "access", "iam", "token"])

    @staticmethod
    def _related_assets(evidence: dict[str, Any], context: dict[str, Any]) -> list[str]:
        values = AIRecommendationService._extract_named_values(evidence)
        assets = []
        for asset in context.get("assets", []):
            if asset.get("enterprise_asset_id") in values or asset.get("application") in values or asset.get("business_capability") in values:
                assets.append(asset.get("enterprise_asset_id"))
        return sorted({item for item in assets if item})

    @staticmethod
    def _related_applications(evidence: dict[str, Any], context: dict[str, Any]) -> list[str]:
        values = AIRecommendationService._extract_named_values(evidence)
        apps = []
        for app in context.get("applications", []):
            if app.get("name") in values or app.get("business_capability") in values:
                apps.append(app.get("name"))
        return sorted({item for item in apps if item})

    @staticmethod
    def _related_capabilities(evidence: dict[str, Any], context: dict[str, Any]) -> list[str]:
        values = AIRecommendationService._extract_named_values(evidence)
        capabilities = []
        for capability in context.get("capabilities", []):
            if capability.get("name") in values:
                capabilities.append(capability.get("name"))
        return sorted({item for item in capabilities if item})

    @staticmethod
    def _extract_named_values(value: Any) -> set[str]:
        values = set()
        if isinstance(value, dict):
            for key, item in value.items():
                if key in {"name", "Application", "application", "business_capability", "Business Capability", "enterprise_asset_id"}:
                    values.add(str(item))
                values.update(AIRecommendationService._extract_named_values(item))
        elif isinstance(value, list):
            for item in value:
                values.update(AIRecommendationService._extract_named_values(item))
        return values
