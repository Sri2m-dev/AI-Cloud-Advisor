from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from connectors.common.tenant_guard import resolve_organization_id
from services.ai_context_service import AIContextService
from services.ai_recommendation_service import AIRecommendationService
from services.supabase_client import supabase


class AIDecisionService:
    HISTORY_TABLE = "ai_decision_history"
    PRIORITY_ORDER = {"Critical": 0, "High": 1, "Medium": 2, "Low": 3}

    @staticmethod
    def get_decisions(organization_id: str | None = None, persist: bool = True) -> list[dict[str, Any]]:
        result = AIDecisionService._build_decision_result(organization_id, persist)
        return result["decisions"]

    @staticmethod
    def get_decision_summary(organization_id: str | None = None, persist: bool = True) -> dict[str, Any]:
        return AIDecisionService._build_decision_result(organization_id, persist)["summary"]

    @staticmethod
    def get_pending_approvals(organization_id: str | None = None) -> list[dict[str, Any]]:
        return [
            row
            for row in AIDecisionService.get_decisions(organization_id, persist=False)
            if row.get("approval_required") not in {"None", None, ""}
        ]

    @staticmethod
    def get_auto_remediation_candidates(organization_id: str | None = None) -> list[dict[str, Any]]:
        return [
            row
            for row in AIDecisionService.get_decisions(organization_id, persist=False)
            if row.get("automation_eligible") and row.get("approval_required") == "None"
        ]

    @staticmethod
    def get_business_decisions(organization_id: str | None = None) -> list[dict[str, Any]]:
        return [
            row
            for row in AIDecisionService.get_decisions(organization_id, persist=False)
            if row.get("business_impact") in {"High", "Critical"}
            or row.get("classification") in {"Business Approval", "Executive Approval"}
        ]

    @staticmethod
    def get_executive_decisions(organization_id: str | None = None) -> list[dict[str, Any]]:
        return [
            row
            for row in AIDecisionService.get_decisions(organization_id, persist=False)
            if row.get("approval_required") == "Executive" or row.get("priority") == "Critical"
        ]

    @staticmethod
    def get_decision(decision_id: str, organization_id: str | None = None) -> dict[str, Any] | None:
        target = str(decision_id or "").strip()
        for row in AIDecisionService.get_decisions(organization_id, persist=False):
            if row.get("decision_id") == target:
                return row
        return None

    @staticmethod
    def persist_decisions(organization_id: str | None = None) -> dict[str, Any]:
        result = AIDecisionService._build_decision_result(organization_id, persist=False)
        return AIDecisionService._persist_decisions(result["organization_id"], result["decisions"])

    @staticmethod
    def get_dashboard(organization_id: str | None = None, persist: bool = True) -> dict[str, Any]:
        return AIDecisionService._build_decision_result(organization_id, persist)

    @staticmethod
    def _build_decision_result(organization_id: str | None = None, persist: bool = True) -> dict[str, Any]:
        org_id = resolve_organization_id(organization_id)
        context = AIContextService.build_enterprise_context(org_id)
        recommendation_result = AIRecommendationService.get_all_recommendations(org_id, persist=False)
        recommendations = recommendation_result.get("recommendations", [])
        decisions = [
            AIDecisionService._decision_from_recommendation(index, recommendation, context)
            for index, recommendation in enumerate(recommendations, start=1)
        ]
        decisions = sorted(
            decisions,
            key=lambda row: (
                AIDecisionService.PRIORITY_ORDER.get(row.get("priority"), 99),
                -float(row.get("overall_score") or 0),
                -int(row.get("confidence") or 0),
            ),
        )
        for index, row in enumerate(decisions, start=1):
            row["decision_id"] = f"DEC-{index:06d}"

        persistence = {"status": "SKIPPED", "rows": 0}
        if persist:
            persistence = AIDecisionService._persist_decisions(org_id, decisions)
        return {
            "organization_id": org_id,
            "summary": AIDecisionService._summary(decisions),
            "decisions": decisions,
            "pending_approvals": [
                row for row in decisions if row.get("approval_required") not in {"None", None, ""}
            ],
            "auto_remediation_candidates": [
                row for row in decisions if row.get("automation_eligible") and row.get("approval_required") == "None"
            ],
            "business_decisions": [
                row
                for row in decisions
                if row.get("business_impact") in {"High", "Critical"}
                or row.get("classification") in {"Business Approval", "Executive Approval"}
            ],
            "executive_decisions": [
                row for row in decisions if row.get("approval_required") == "Executive" or row.get("priority") == "Critical"
            ],
            "persistence": persistence,
        }

    @staticmethod
    def _decision_from_recommendation(
        index: int,
        recommendation: dict[str, Any],
        context: dict[str, Any],
    ) -> dict[str, Any]:
        scores = AIDecisionService._score_recommendation(recommendation, context)
        classification = AIDecisionService._classification(recommendation, scores)
        automation = AIDecisionService._automation(recommendation, scores, classification)
        approval = AIDecisionService._approval_required(recommendation, scores, automation)
        priority = AIDecisionService._priority(recommendation, scores)
        confidence = min(100, round((float(recommendation.get("confidence") or 0) * 0.7) + (scores["expected_success"] * 0.3)))
        risk = AIDecisionService._risk_label(scores["risk_score"])
        status = AIDecisionService._status(classification, automation, approval)
        now = datetime.now(timezone.utc).isoformat()
        return {
            "decision_id": f"DEC-{index:06d}",
            "recommendation_id": recommendation.get("recommendation_id"),
            "recommendation": recommendation.get("title"),
            "recommended_action": recommendation.get("recommendation"),
            "decision": AIDecisionService._decision_label(classification, automation, approval),
            "classification": classification,
            "automation": "Eligible" if automation["eligible"] else "Manual",
            "automation_eligible": automation["eligible"],
            "approval_required": approval,
            "expected_success": automation["expected_success"],
            "rollback_available": automation["rollback_available"],
            "confidence": confidence,
            "priority": priority,
            "business_impact": AIDecisionService._impact_label(scores["business_score"]),
            "financial_impact": AIDecisionService._impact_label(scores["financial_score"]),
            "operational_impact": AIDecisionService._impact_label(scores["operational_score"]),
            "security_impact": AIDecisionService._impact_label(scores["security_score"]),
            "compliance_impact": AIDecisionService._impact_label(scores["compliance_score"]),
            "governance_impact": AIDecisionService._impact_label(scores["governance_score"]),
            "customer_impact": AIDecisionService._impact_label(scores["customer_score"]),
            "risk": risk,
            "owner": recommendation.get("owner"),
            "status": status,
            "expected_savings": recommendation.get("estimated_savings") or 0,
            "expected_risk_reduction": recommendation.get("estimated_risk_reduction") or 0,
            "estimated_downtime": AIDecisionService._estimated_downtime(recommendation, automation),
            "estimated_cost_if_ignored": AIDecisionService._estimated_cost_if_ignored(recommendation),
            "overall_score": scores["overall_score"],
            "scores": scores,
            "explanation": AIDecisionService._explanation(recommendation, scores, automation, approval, classification),
            "related_assets": recommendation.get("related_assets", []),
            "related_applications": recommendation.get("related_applications", []),
            "related_capabilities": recommendation.get("related_capabilities", []),
            "created_at": now,
        }

    @staticmethod
    def _score_recommendation(recommendation: dict[str, Any], context: dict[str, Any]) -> dict[str, float]:
        category = str(recommendation.get("category") or "")
        priority = str(recommendation.get("priority") or "Medium")
        severity = str(recommendation.get("severity") or priority)
        base = {"Critical": 95, "High": 82, "Medium": 62, "Low": 35}.get(priority, 55)
        severity_boost = {"Critical": 8, "High": 5, "Medium": 0, "Low": -8}.get(severity, 0)
        confidence = float(recommendation.get("confidence") or 0)
        financial = min(100, 35 + (float(recommendation.get("estimated_savings") or 0) / 100))
        if "Cost" in category:
            financial = max(financial, 80 if recommendation.get("estimated_savings") else 60)
        operational = 90 if category in {"Cloud Discovery", "Operations"} else 55
        security = 88 if category == "Security" else 35
        governance = 82 if category == "Governance" else 45
        compliance = 75 if category in {"Governance", "Security"} else 35
        customer = 80 if category == "Business Continuity" else 45
        business = min(100, base + severity_boost)
        technical = min(100, float(recommendation.get("overall_score") or base) + (10 if category in {"Cloud Discovery", "Security"} else 0))
        complexity = AIDecisionService._technical_complexity(recommendation)
        urgency = {"Critical": 95, "High": 80, "Medium": 55, "Low": 25}.get(priority, 55)
        risk_score = round((business * 0.35) + (operational * 0.25) + (security * 0.15) + (compliance * 0.15) - (complexity * 0.10), 1)
        expected_success = max(40, min(99, round(confidence - (complexity * 0.15) + (10 if category in {"Cloud Discovery", "Operations"} else 0), 1)))
        overall = round(
            (business * 0.25)
            + (technical * 0.18)
            + (financial * 0.15)
            + (operational * 0.14)
            + (security * 0.08)
            + (governance * 0.08)
            + (urgency * 0.07)
            + (confidence * 0.05),
            1,
        )
        return {
            "business_score": round(business, 1),
            "financial_score": round(financial, 1),
            "operational_score": round(operational, 1),
            "security_score": round(security, 1),
            "compliance_score": round(compliance, 1),
            "governance_score": round(governance, 1),
            "customer_score": round(customer, 1),
            "technical_score": round(technical, 1),
            "complexity_score": round(complexity, 1),
            "confidence_score": round(confidence, 1),
            "urgency_score": round(urgency, 1),
            "risk_score": max(0, min(100, risk_score)),
            "expected_success": expected_success,
            "overall_score": overall,
        }

    @staticmethod
    def _classification(recommendation: dict[str, Any], scores: dict[str, float]) -> str:
        category = recommendation.get("category")
        if category in {"Cloud Discovery", "Operations"} and scores["expected_success"] >= 85 and scores["complexity_score"] <= 45:
            return "Auto Remediate"
        if recommendation.get("priority") == "Critical" and scores["business_score"] >= 90:
            return "Immediate"
        if scores["business_score"] >= 85 and scores["financial_score"] >= 80:
            return "Business Approval"
        if category in {"Business Continuity"} and scores["customer_score"] >= 75:
            return "Executive Approval"
        if scores["overall_score"] >= 70:
            return "Planned"
        if scores["overall_score"] >= 45:
            return "Monitor"
        return "Ignore"

    @staticmethod
    def _automation(
        recommendation: dict[str, Any],
        scores: dict[str, float],
        classification: str,
    ) -> dict[str, Any]:
        category = recommendation.get("category")
        eligible = classification == "Auto Remediate" or (
            category in {"Cloud Discovery", "Operations"}
            and scores["expected_success"] >= 85
            and scores["complexity_score"] <= 45
        )
        return {
            "eligible": bool(eligible),
            "expected_success": scores["expected_success"],
            "rollback_available": category in {"Cloud Discovery", "Operations", "Cost Optimization", "Governance"},
        }

    @staticmethod
    def _approval_required(
        recommendation: dict[str, Any],
        scores: dict[str, float],
        automation: dict[str, Any],
    ) -> str:
        if automation["eligible"] and scores["risk_score"] < 80 and recommendation.get("category") in {"Cloud Discovery", "Operations"}:
            return "None"
        if recommendation.get("category") == "Business Continuity" or scores["business_score"] >= 90:
            return "Executive"
        if recommendation.get("category") in {"Cost Optimization"} and float(recommendation.get("estimated_savings") or 0) > 1000:
            return "Business"
        if recommendation.get("category") in {"Security", "Governance"}:
            return "Manual"
        return "None"

    @staticmethod
    def _priority(recommendation: dict[str, Any], scores: dict[str, float]) -> str:
        if recommendation.get("priority") == "Critical" or scores["overall_score"] >= 85:
            return "Critical"
        if scores["overall_score"] >= 70:
            return "High"
        if scores["overall_score"] >= 50:
            return "Medium"
        return "Low"

    @staticmethod
    def _persist_decisions(organization_id: str, decisions: list[dict[str, Any]]) -> dict[str, Any]:
        if not decisions:
            return {"status": "SUCCESS", "rows": 0}
        rows = [
            {
                "decision_id": row.get("decision_id"),
                "recommendation_id": row.get("recommendation_id"),
                "organization_id": organization_id,
                "decision": row.get("decision"),
                "priority": row.get("priority"),
                "confidence": row.get("confidence"),
                "automation_eligible": row.get("automation_eligible"),
                "approval_required": row.get("approval_required"),
                "owner": row.get("owner"),
                "risk_score": row.get("scores", {}).get("risk_score") or 0,
                "business_score": row.get("scores", {}).get("business_score") or 0,
                "technical_score": row.get("scores", {}).get("technical_score") or 0,
                "financial_score": row.get("scores", {}).get("financial_score") or 0,
                "operational_score": row.get("scores", {}).get("operational_score") or 0,
                "security_score": row.get("scores", {}).get("security_score") or 0,
                "compliance_score": row.get("scores", {}).get("compliance_score") or 0,
                "governance_score": row.get("scores", {}).get("governance_score") or 0,
                "customer_score": row.get("scores", {}).get("customer_score") or 0,
                "complexity_score": row.get("scores", {}).get("complexity_score") or 0,
                "urgency_score": row.get("scores", {}).get("urgency_score") or 0,
                "overall_score": row.get("overall_score") or 0,
                "expected_savings": row.get("expected_savings") or 0,
                "expected_risk_reduction": row.get("expected_risk_reduction") or 0,
                "expected_success": row.get("expected_success") or 0,
                "rollback_available": row.get("rollback_available"),
                "status": row.get("status"),
                "explanation": row.get("explanation") or {},
                "created_at": row.get("created_at") or datetime.now(timezone.utc).isoformat(),
            }
            for row in decisions
        ]
        try:
            supabase.table(AIDecisionService.HISTORY_TABLE).upsert(rows).execute()
            return {"status": "SUCCESS", "rows": len(rows)}
        except Exception as exc:
            return {"status": "SKIPPED", "rows": 0, "error": str(exc)}

    @staticmethod
    def _summary(decisions: list[dict[str, Any]]) -> dict[str, Any]:
        priorities = {key: 0 for key in ["Critical", "High", "Medium", "Low"]}
        classifications: dict[str, int] = {}
        owners: dict[str, int] = {}
        approvals: dict[str, int] = {}
        for row in decisions:
            priorities[row.get("priority") or "Medium"] = priorities.get(row.get("priority") or "Medium", 0) + 1
            classifications[row.get("classification") or "Unclassified"] = classifications.get(row.get("classification") or "Unclassified", 0) + 1
            owners[row.get("owner") or "Unassigned"] = owners.get(row.get("owner") or "Unassigned", 0) + 1
            approvals[row.get("approval_required") or "None"] = approvals.get(row.get("approval_required") or "None", 0) + 1
        confidence = [float(row.get("confidence") or 0) for row in decisions]
        return {
            "total_decisions": len(decisions),
            "auto_approved": len([row for row in decisions if row.get("automation_eligible") and row.get("approval_required") == "None"]),
            "pending_approval": len([row for row in decisions if row.get("approval_required") not in {"None", None, ""}]),
            "automated": len([row for row in decisions if row.get("automation_eligible")]),
            "manual": len([row for row in decisions if not row.get("automation_eligible")]),
            "critical": priorities.get("Critical", 0),
            "average_confidence": round(sum(confidence) / len(confidence), 1) if confidence else 0,
            "estimated_savings": round(sum(float(row.get("expected_savings") or 0) for row in decisions), 2),
            "estimated_risk_reduction": round(AIDecisionService._average([row.get("expected_risk_reduction") for row in decisions]), 1),
            "decision_distribution": [{"Decision": key, "Count": value} for key, value in sorted(classifications.items())],
            "automation_readiness": [
                {"Automation": "Eligible", "Count": len([row for row in decisions if row.get("automation_eligible")])},
                {"Automation": "Manual", "Count": len([row for row in decisions if not row.get("automation_eligible")])},
            ],
            "risk_reduction": [
                {"Priority": key, "Count": value}
                for key, value in priorities.items()
            ],
            "business_impact": AIDecisionService._distribution(decisions, "business_impact", "Business Impact"),
            "owner_workload": [{"Owner": key, "Decisions": value} for key, value in sorted(owners.items(), key=lambda item: item[1], reverse=True)],
            "approval_distribution": [{"Approval": key, "Decisions": value} for key, value in sorted(approvals.items())],
            "decision_timeline": AIDecisionService._decision_timeline(decisions),
        }

    @staticmethod
    def _explanation(
        recommendation: dict[str, Any],
        scores: dict[str, float],
        automation: dict[str, Any],
        approval: str,
        classification: str,
    ) -> dict[str, Any]:
        return {
            "why": [
                f"Recommendation priority is {recommendation.get('priority')}.",
                f"Business impact score is {scores['business_score']}.",
                f"Operational impact score is {scores['operational_score']}.",
                f"Expected automation success is {automation['expected_success']}%.",
                f"Approval requirement is {approval}.",
            ],
            "if_ignored": {
                "financial_impact": AIDecisionService._impact_label(scores["financial_score"]),
                "operational_impact": AIDecisionService._impact_label(scores["operational_score"]),
                "business_impact": AIDecisionService._impact_label(scores["business_score"]),
                "compliance_impact": AIDecisionService._impact_label(scores["compliance_score"]),
                "customer_impact": AIDecisionService._impact_label(scores["customer_score"]),
                "estimated_cost": AIDecisionService._estimated_cost_if_ignored(recommendation),
            },
            "decision_basis": {
                "classification": classification,
                "automation_eligible": automation["eligible"],
                "rollback_available": automation["rollback_available"],
                "evidence": recommendation.get("evidence") or {},
            },
        }

    @staticmethod
    def _decision_label(classification: str, automation: dict[str, Any], approval: str) -> str:
        if automation["eligible"] and approval == "None":
            return "Approve Auto Remediation"
        if approval != "None":
            return "Request Approval"
        if classification == "Monitor":
            return "Monitor"
        if classification == "Ignore":
            return "Ignore"
        return "Approve"

    @staticmethod
    def _status(classification: str, automation: dict[str, Any], approval: str) -> str:
        if approval != "None":
            return "Pending Approval"
        if automation["eligible"]:
            return "Pending Execution"
        if classification in {"Monitor", "Ignore"}:
            return classification
        return "Ready"

    @staticmethod
    def _technical_complexity(recommendation: dict[str, Any]) -> float:
        category = recommendation.get("category")
        if category in {"Cloud Discovery", "Operations"}:
            return 30
        if category in {"Governance", "Cost Optimization"}:
            return 55
        if category == "Security":
            return 60
        if category == "Business Continuity":
            return 70
        return 50

    @staticmethod
    def _estimated_downtime(recommendation: dict[str, Any], automation: dict[str, Any]) -> str:
        if automation["eligible"]:
            return "0-5 minutes"
        if recommendation.get("category") == "Business Continuity":
            return "Depends on application recovery posture"
        return "No direct downtime expected"

    @staticmethod
    def _estimated_cost_if_ignored(recommendation: dict[str, Any]) -> float:
        return round(float(recommendation.get("estimated_savings") or 0) + (float(recommendation.get("expected_risk_reduction") or 0) * 100), 2)

    @staticmethod
    def _impact_label(score: float) -> str:
        if score >= 85:
            return "Critical"
        if score >= 70:
            return "High"
        if score >= 45:
            return "Medium"
        return "Low"

    @staticmethod
    def _risk_label(score: float) -> str:
        if score >= 85:
            return "Critical"
        if score >= 70:
            return "High"
        if score >= 45:
            return "Medium"
        return "Low"

    @staticmethod
    def _distribution(rows: list[dict[str, Any]], field: str, label: str) -> list[dict[str, Any]]:
        counts: dict[str, int] = {}
        for row in rows:
            value = row.get(field) or "Unassigned"
            counts[str(value)] = counts.get(str(value), 0) + 1
        return [{label: key, "Count": value} for key, value in sorted(counts.items(), key=lambda item: item[1], reverse=True)]

    @staticmethod
    def _decision_timeline(decisions: list[dict[str, Any]]) -> list[dict[str, Any]]:
        counts: dict[str, int] = {}
        for row in decisions:
            date_key = str(row.get("created_at") or "")[:10]
            counts[date_key] = counts.get(date_key, 0) + 1
        return [{"Date": key, "Decisions": value} for key, value in sorted(counts.items()) if key]

    @staticmethod
    def _average(values: list[Any]) -> float:
        numeric = [float(value) for value in values if value not in (None, "")]
        if not numeric:
            return 0.0
        return sum(numeric) / len(numeric)
