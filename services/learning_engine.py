from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from statistics import mean
from typing import Any

from connectors.common.tenant_guard import resolve_organization_id
from repositories.learning_repository import LearningRepository


def _safe_float(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _average(values: list[float], fallback: float = 0.0) -> float:
    clean = [value for value in values if value > 0]
    return round(mean(clean), 1) if clean else fallback


class LearningEngine:
    @staticmethod
    def learn_from_execution(
        execution: dict[str, Any],
        actual_savings: float | None = None,
        recommendation_status: str = "Accepted",
        persist: bool = True,
    ) -> dict[str, Any]:
        org_id = resolve_organization_id(execution.get("organization_id"))
        blueprint = execution.get("blueprint") or {}
        expected = LearningEngine._expected_savings(execution)
        actual = LearningEngine._actual_savings(expected, execution, actual_savings)
        variance = actual - expected
        accuracy = LearningEngine._accuracy(expected, actual)
        operational_success = LearningEngine._operational_success(execution)
        recommendation_quality = round((accuracy * 0.55) + (operational_success * 0.35) + (LearningEngine._confidence(execution) * 0.10), 1)
        learning_score = round((accuracy * 0.35) + (recommendation_quality * 0.25) + (operational_success * 0.25) + (LearningEngine._confidence(execution) * 0.15), 1)
        package = {
            "id": str(uuid.uuid4()),
            "organization_id": org_id,
            "execution_id": execution.get("id"),
            "workflow_id": execution.get("workflow_id"),
            "goal": execution.get("goal"),
            "status": execution.get("status"),
            "created_at": datetime.utcnow().isoformat(),
            "expected_savings": round(expected, 2),
            "actual_savings": round(actual, 2),
            "variance": round(variance, 2),
            "prediction_accuracy": accuracy,
            "recommendation_quality": recommendation_quality,
            "business_impact": LearningEngine._business_impact(accuracy, actual, execution),
            "operational_success": operational_success,
            "learning_score": learning_score,
            "confidence_update": LearningEngine._confidence_update(execution, accuracy, operational_success),
            "recommendation_feedback": LearningEngine._recommendation_feedback(
                execution,
                expected,
                actual,
                accuracy,
                recommendation_quality,
                recommendation_status,
            ),
            "agent_feedback": LearningEngine._agent_feedback(execution, accuracy, operational_success),
            "workflow_feedback": LearningEngine._workflow_feedback(execution, accuracy, operational_success),
            "template_improvements": LearningEngine._template_improvements(blueprint, accuracy, execution),
            "confidence_history": LearningEngine._confidence_history(execution, accuracy),
            "learning_insights": LearningEngine._learning_insights(execution, accuracy, actual, operational_success),
            "execution_metrics": LearningEngine._execution_metrics(execution, accuracy, operational_success),
            "knowledge_memory": LearningEngine._knowledge_memory(execution, accuracy, operational_success),
        }
        package["summary"] = LearningEngine._summary(package)
        package["executive_summary"] = LearningEngine._executive_summary(package)
        if persist:
            LearningRepository.save_learning_package(package)
        return package

    @staticmethod
    def get_learning_dashboard(organization_id: str | None = None) -> dict[str, Any]:
        org_id = resolve_organization_id(organization_id)
        outcomes = LearningRepository.list_rows("learning_outcome", org_id)
        recommendations = LearningRepository.list_rows("recommendation_feedback", org_id)
        agents = LearningRepository.list_rows("agent_feedback", org_id)
        workflows = LearningRepository.list_rows("workflow_feedback", org_id)
        insights = LearningRepository.list_rows("learning_insight", org_id)
        confidence = LearningRepository.list_rows("confidence_history", org_id)
        template_improvements = LearningRepository.list_rows("template_improvement", org_id)
        summaries = LearningRepository.list_rows("learning_summary", org_id)
        if not outcomes:
            demo = LearningEngine._demo_dashboard(org_id)
            outcomes = demo["outcomes"]
            recommendations = demo["recommendation_feedback"]
            agents = demo["agent_feedback"]
            workflows = demo["workflow_feedback"]
            insights = demo["learning_insights"]
            confidence = demo["confidence_history"]
            template_improvements = demo["template_improvements"]
            summaries = demo["summaries"]
        kpis = LearningEngine._kpis(outcomes, recommendations, workflows, confidence, agents)
        return {
            "organization_id": org_id,
            "generated_at": datetime.utcnow().isoformat(),
            "kpis": kpis,
            "learning_score": LearningEngine._learning_health_score(kpis),
            "outcomes": LearningEngine._normalize_outcomes(outcomes),
            "recommendation_feedback": LearningEngine._normalize_recommendations(recommendations),
            "agent_scorecards": LearningEngine._agent_scorecards(agents),
            "workflow_feedback": LearningEngine._normalize_workflows(workflows),
            "template_improvements": LearningEngine._normalize_template_improvements(template_improvements),
            "confidence_trend": LearningEngine._normalize_confidence(confidence),
            "learning_insights": LearningEngine._normalize_insights(insights),
            "knowledge_memory": LearningEngine._knowledge_memory_from_summaries(summaries, insights),
            "executive_summary": LearningEngine._dashboard_summary(kpis),
        }

    @staticmethod
    def _expected_savings(execution: dict[str, Any]) -> float:
        blueprint = execution.get("blueprint") or {}
        summary = execution.get("summary") or {}
        consensus = blueprint.get("source_consensus") or {}
        for value in [
            summary.get("Expected Savings"),
            consensus.get("Expected Savings"),
            (blueprint.get("unified_enterprise_plan") or {}).get("Expected Savings"),
        ]:
            amount = _safe_float(value)
            if amount:
                return amount
        template = (blueprint.get("template") or {}).get("Name", "")
        if "Oracle" in template:
            return 240000.0
        if "SaaS" in template:
            return 180000.0
        if "Kubernetes" in template:
            return 125000.0
        if "Recovery" in template:
            return 90000.0
        return 120000.0

    @staticmethod
    def _actual_savings(expected: float, execution: dict[str, Any], actual_savings: float | None) -> float:
        if actual_savings is not None:
            return float(actual_savings)
        status = execution.get("status")
        if status == "Completed":
            return expected * 0.983
        if status == "Rolled Back":
            return expected * 0.42
        if status == "Blocked":
            return 0.0
        return expected * 0.88

    @staticmethod
    def _accuracy(expected: float, actual: float) -> float:
        if expected <= 0 and actual <= 0:
            return 100.0
        base = max(expected, actual, 1.0)
        return round(max(0.0, 100.0 - abs(actual - expected) / base * 100.0), 1)

    @staticmethod
    def _operational_success(execution: dict[str, Any]) -> float:
        validations = execution.get("validation_results") or []
        if not validations:
            return 0.0 if execution.get("status") == "Blocked" else 90.0
        passed = sum(1 for row in validations if str(row.get("Status", "")).lower() in {"passed", "complete", "completed"})
        base = passed / len(validations) * 100
        if execution.get("status") == "Rolled Back":
            base -= 25
        if execution.get("status") == "Blocked":
            base = 0
        return round(max(0.0, min(100.0, base)), 1)

    @staticmethod
    def _confidence(execution: dict[str, Any]) -> float:
        return _safe_float((execution.get("blueprint") or {}).get("confidence")) or 92.0

    @staticmethod
    def _confidence_update(execution: dict[str, Any], accuracy: float, operational_success: float) -> dict[str, Any]:
        before = LearningEngine._confidence(execution)
        delta = 1.0 if accuracy >= 96 and operational_success >= 95 else -2.5 if accuracy < 80 or operational_success < 80 else 0.4
        return {
            "Before": round(before, 1),
            "After": round(max(40.0, min(99.0, before + delta)), 1),
            "Delta": round(delta, 1),
            "Reason": "Execution outcome matched forecast" if delta > 0 else "Execution variance requires confidence calibration",
        }

    @staticmethod
    def _business_impact(accuracy: float, actual: float, execution: dict[str, Any]) -> str:
        if execution.get("status") == "Blocked":
            return "No business impact because execution remained locked."
        if accuracy >= 96:
            return f"High positive impact with {actual:,.0f} realized savings and forecast accuracy above threshold."
        if accuracy >= 85:
            return f"Positive impact with {actual:,.0f} realized savings and manageable variance."
        return "Outcome requires review before similar recommendations are reused."

    @staticmethod
    def _recommendation_feedback(
        execution: dict[str, Any],
        expected: float,
        actual: float,
        accuracy: float,
        quality: float,
        recommendation_status: str,
    ) -> list[dict[str, Any]]:
        update = LearningEngine._confidence_update(execution, accuracy, LearningEngine._operational_success(execution))
        return [
            {
                "id": str(uuid.uuid4()),
                "recommendation_id": f"REC-{str(execution.get('id') or uuid.uuid4())[:8]}",
                "execution_id": execution.get("id"),
                "workflow_id": execution.get("workflow_id"),
                "goal_text": execution.get("goal"),
                "status": recommendation_status,
                "successful": execution.get("status") == "Completed",
                "expected_savings": round(expected, 2),
                "actual_savings": round(actual, 2),
                "rollback_required": bool(execution.get("rollback_execution")),
                "confidence_before": update["Before"],
                "confidence_after": update["After"],
                "recommendation_quality": quality,
                "feedback_payload": {"Prediction Accuracy": accuracy, "Execution Status": execution.get("status")},
            },
        ]

    @staticmethod
    def _agent_feedback(execution: dict[str, Any], accuracy: float, operational_success: float) -> list[dict[str, Any]]:
        agents = [
            ("Planner Agent", 1.0),
            ("Cost Agent", 0.98),
            ("Simulation Agent", 1.01),
            ("Governance Agent", 1.02),
            ("Reasoning Agent", 0.99),
            ("Operations Agent", 0.97),
        ]
        rows = []
        for name, factor in agents:
            score = round(max(60.0, min(99.0, ((accuracy * 0.45) + (operational_success * 0.40) + (LearningEngine._confidence(execution) * 0.15)) * factor)), 1)
            rows.append(
                {
                    "id": str(uuid.uuid4()),
                    "agent_name": name,
                    "execution_id": execution.get("id"),
                    "plans_generated": 1 if name == "Planner Agent" else 0,
                    "accepted": execution.get("status") == "Completed",
                    "rejected": execution.get("status") in {"Blocked", "Rolled Back"},
                    "execution_success": operational_success,
                    "average_confidence": LearningEngine._confidence(execution),
                    "learning_score": score,
                    "feedback_payload": {
                        "Prediction Accuracy": round(accuracy * factor, 1),
                        "Improvement": "Increase confidence" if score >= 95 else "Monitor next outcome",
                    },
                },
            )
        return rows

    @staticmethod
    def _workflow_feedback(execution: dict[str, Any], accuracy: float, operational_success: float) -> list[dict[str, Any]]:
        blueprint = execution.get("blueprint") or {}
        template = (blueprint.get("template") or {}).get("Name", "Enterprise Workflow")
        return [
            {
                "id": str(uuid.uuid4()),
                "workflow_id": execution.get("workflow_id"),
                "template_name": template,
                "version_before": "1.0",
                "version_after": "1.1" if accuracy >= 90 else "1.0-review",
                "execution_success": operational_success,
                "prediction_accuracy": accuracy,
                "lessons_learned": LearningEngine._lessons(template, accuracy, execution),
                "feedback_payload": {
                    "Stages": len(blueprint.get("stages", [])),
                    "Tasks": len(blueprint.get("tasks", [])),
                    "Rollback": bool(execution.get("rollback_execution")),
                },
            },
        ]

    @staticmethod
    def _template_improvements(blueprint: dict[str, Any], accuracy: float, execution: dict[str, Any]) -> list[dict[str, Any]]:
        template = (blueprint.get("template") or {}).get("Name", "Enterprise Workflow")
        return [
            {
                "id": str(uuid.uuid4()),
                "template_name": template,
                "version": "1.1",
                "improvement_type": "Confidence Calibration" if accuracy >= 90 else "Risk Control",
                "lesson": LearningEngine._lessons(template, accuracy, execution)[0],
                "recommended_change": "Promote this workflow pattern for similar goals." if accuracy >= 90 else "Add additional validation and approval checkpoints.",
                "source_execution_id": execution.get("id"),
                "status": "Recommended",
            },
        ]

    @staticmethod
    def _confidence_history(execution: dict[str, Any], accuracy: float) -> list[dict[str, Any]]:
        update = LearningEngine._confidence_update(execution, accuracy, LearningEngine._operational_success(execution))
        return [
            {
                "id": str(uuid.uuid4()),
                "execution_id": execution.get("id"),
                "metric_name": "Agentic Execution Confidence",
                "confidence_before": update["Before"],
                "confidence_after": update["After"],
                "confidence_delta": update["Delta"],
                "reason": update["Reason"],
            },
        ]

    @staticmethod
    def _learning_insights(execution: dict[str, Any], accuracy: float, actual: float, operational_success: float) -> list[dict[str, Any]]:
        template = ((execution.get("blueprint") or {}).get("template") or {}).get("Name", "Enterprise Workflow")
        return [
            {
                "id": str(uuid.uuid4()),
                "insight_type": "Outcome",
                "title": f"{template} outcome accuracy",
                "insight": f"{template} delivered {accuracy:.1f}% savings accuracy and {operational_success:.1f}% operational success.",
                "severity": "Positive" if accuracy >= 90 else "Review",
                "recommended_action": "Reuse this workflow pattern for comparable goals." if accuracy >= 90 else "Review assumptions before reusing this workflow.",
            },
            {
                "id": str(uuid.uuid4()),
                "insight_type": "Savings",
                "title": "Realized savings feedback",
                "insight": f"Actual savings were ${actual:,.0f}.",
                "severity": "Positive" if actual > 0 else "Neutral",
                "recommended_action": "Update recommendation confidence using realized savings.",
            },
        ]

    @staticmethod
    def _execution_metrics(execution: dict[str, Any], accuracy: float, operational_success: float) -> list[dict[str, Any]]:
        return [
            {
                "id": str(uuid.uuid4()),
                "execution_id": execution.get("id"),
                "metric_name": "Prediction Accuracy",
                "metric_value": accuracy,
                "metric_unit": "%",
            },
            {
                "id": str(uuid.uuid4()),
                "execution_id": execution.get("id"),
                "metric_name": "Operational Success",
                "metric_value": operational_success,
                "metric_unit": "%",
            },
        ]

    @staticmethod
    def _knowledge_memory(execution: dict[str, Any], accuracy: float, operational_success: float) -> list[str]:
        template = ((execution.get("blueprint") or {}).get("template") or {}).get("Name", "Enterprise Workflow")
        if "Oracle" in template:
            return [
                "Oracle migrations are most successful when executed through phased validation environments.",
                "Database migration recommendations should preserve rollback evidence before CAB approval.",
            ]
        if "Kubernetes" in template:
            return [
                "Kubernetes rightsizing produces higher savings when storage and network growth are reviewed together.",
                "Weekend maintenance windows reduce rollback risk for cluster optimization workflows.",
            ]
        if "SaaS" in template:
            return [
                "SaaS license reductions are safest when business owners validate inactive users before removal.",
                "License recommendations should include renewal date and usage confidence.",
            ]
        if accuracy >= 95 and operational_success >= 95:
            return ["High-confidence mock executions can raise future recommendation confidence for similar workflows."]
        return ["Similar future workflows should include additional validation evidence before execution."]

    @staticmethod
    def _lessons(template: str, accuracy: float, execution: dict[str, Any]) -> list[str]:
        if execution.get("status") == "Blocked":
            return ["Execution gates prevented an unauthorized workflow from proceeding."]
        if accuracy >= 96:
            return [f"{template} assumptions closely matched execution outcome.", "Validation evidence was sufficient for future planning confidence."]
        return [f"{template} requires tighter actual-vs-forecast calibration.", "Add more pre-execution validation to reduce variance."]

    @staticmethod
    def _summary(package: dict[str, Any]) -> dict[str, Any]:
        return {
            "Expected Savings": package["expected_savings"],
            "Actual Savings": package["actual_savings"],
            "Variance": package["variance"],
            "Prediction Accuracy": package["prediction_accuracy"],
            "Recommendation Quality": package["recommendation_quality"],
            "Operational Success": package["operational_success"],
            "Learning Score": package["learning_score"],
            "Confidence Update": package["confidence_update"],
        }

    @staticmethod
    def _executive_summary(package: dict[str, Any]) -> str:
        return (
            f"Learning complete for {package.get('goal')}. "
            f"Expected savings were ${package['expected_savings']:,.0f}, actual savings were ${package['actual_savings']:,.0f}, "
            f"prediction accuracy was {package['prediction_accuracy']:.1f}%, and confidence moved "
            f"{package['confidence_update']['Delta']:+.1f} points."
        )

    @staticmethod
    def _demo_dashboard(org_id: str) -> dict[str, Any]:
        today = datetime.utcnow().date()
        outcomes = [
            {
                "organization_id": org_id,
                "goal_text": "Reserved Instance Optimization",
                "expected_savings": 240000,
                "actual_savings": 236500,
                "variance": -3500,
                "prediction_accuracy": 98.5,
                "recommendation_quality": 97.8,
                "business_impact": "High positive impact",
                "operational_success": 100,
                "status": "Completed",
                "created_at": today.isoformat(),
            },
            {
                "organization_id": org_id,
                "goal_text": "Oracle Migration Mock Execution",
                "expected_savings": 120000,
                "actual_savings": 118000,
                "variance": -2000,
                "prediction_accuracy": 98.3,
                "recommendation_quality": 97.1,
                "business_impact": "Positive impact",
                "operational_success": 100,
                "status": "Completed",
                "created_at": (today - timedelta(days=7)).isoformat(),
            },
            {
                "organization_id": org_id,
                "goal_text": "SaaS License Optimization",
                "expected_savings": 180000,
                "actual_savings": 171400,
                "variance": -8600,
                "prediction_accuracy": 95.2,
                "recommendation_quality": 94.6,
                "business_impact": "Positive impact",
                "operational_success": 96,
                "status": "Completed",
                "created_at": (today - timedelta(days=14)).isoformat(),
            },
        ]
        agents = [
            {"agent_name": "Simulation Agent", "learning_score": 98, "execution_success": 100, "average_confidence": 97, "accepted": True, "rejected": False},
            {"agent_name": "Planner Agent", "learning_score": 97, "execution_success": 98, "average_confidence": 96, "accepted": True, "rejected": False},
            {"agent_name": "Governance Agent", "learning_score": 96, "execution_success": 99, "average_confidence": 95, "accepted": True, "rejected": False},
            {"agent_name": "Cost Agent", "learning_score": 95, "execution_success": 96, "average_confidence": 94, "accepted": True, "rejected": False},
            {"agent_name": "Reasoning Agent", "learning_score": 95, "execution_success": 96, "average_confidence": 95, "accepted": True, "rejected": False},
        ]
        recommendations = [
            {"status": "Accepted", "successful": True, "expected_savings": 240000, "actual_savings": 236500, "rollback_required": False, "recommendation_quality": 97.8},
            {"status": "Accepted", "successful": True, "expected_savings": 120000, "actual_savings": 118000, "rollback_required": False, "recommendation_quality": 97.1},
            {"status": "Modified", "successful": True, "expected_savings": 180000, "actual_savings": 171400, "rollback_required": False, "recommendation_quality": 94.6},
            {"status": "Rejected", "successful": False, "expected_savings": 90000, "actual_savings": 0, "rollback_required": False, "recommendation_quality": 70.0},
        ]
        workflows = [
            {"template_name": "Oracle to PostgreSQL Migration", "version_before": "1.0", "version_after": "1.1", "execution_success": 97, "prediction_accuracy": 98.3, "lessons_learned": ["Phased validation improved migration confidence."]},
            {"template_name": "Kubernetes Rightsizing", "version_before": "1.0", "version_after": "1.1", "execution_success": 96, "prediction_accuracy": 94.4, "lessons_learned": ["Storage growth review improved forecast accuracy."]},
            {"template_name": "Cloud Cost Optimization", "version_before": "1.0", "version_after": "1.2", "execution_success": 99, "prediction_accuracy": 98.5, "lessons_learned": ["Reserved commitment analysis improved savings accuracy."]},
        ]
        insights = [
            {"title": "Oracle migrations have a 97% success rate", "insight": "Phased environments improved migration outcomes.", "severity": "Positive", "recommended_action": "Reuse phased validation."},
            {"title": "Kubernetes rightsizing beats forecast by 12%", "insight": "Cluster storage and network review improved savings.", "severity": "Positive", "recommended_action": "Promote rightsizing workflow."},
            {"title": "Simulation accuracy improved to 98%", "insight": "Mock validation outcomes are closely matching forecast assumptions.", "severity": "Positive", "recommended_action": "Use simulation outputs in CAB packets."},
        ]
        confidence = [
            {"metric_name": "Oracle Migration", "confidence_before": 92, "confidence_after": 96, "confidence_delta": 4, "created_at": (today - timedelta(days=20)).isoformat()},
            {"metric_name": "Reserved Instance Optimization", "confidence_before": 94, "confidence_after": 97, "confidence_delta": 3, "created_at": (today - timedelta(days=10)).isoformat()},
            {"metric_name": "SaaS Optimization", "confidence_before": 91, "confidence_after": 93, "confidence_delta": 2, "created_at": today.isoformat()},
        ]
        improvements = [
            {"template_name": "Oracle to PostgreSQL Migration", "version": "1.1", "improvement_type": "Template Evolution", "lesson": "Use phased validation.", "recommended_change": "Add explicit rollback evidence collection.", "status": "Recommended"},
            {"template_name": "Cloud Cost Optimization", "version": "1.2", "improvement_type": "Confidence Calibration", "lesson": "RI utilization is strongest ROI signal.", "recommended_change": "Prioritize commitments above 30% utilization.", "status": "Recommended"},
        ]
        summaries = [
            {
                "summary": "Monthly learning baseline",
                "learning_score": 96,
                "knowledge_memory": [
                    "Oracle migrations are most successful when executed in phased environments.",
                    "Weekend maintenance windows reduced rollback events by 40%.",
                    "Reserved Instance purchases above 30% utilization achieved the best ROI.",
                    "Security approvals are the most common cause of CAB delays.",
                ],
            },
        ]
        return {
            "outcomes": outcomes,
            "recommendation_feedback": recommendations,
            "agent_feedback": agents,
            "workflow_feedback": workflows,
            "learning_insights": insights,
            "confidence_history": confidence,
            "template_improvements": improvements,
            "summaries": summaries,
        }

    @staticmethod
    def _kpis(
        outcomes: list[dict[str, Any]],
        recommendations: list[dict[str, Any]],
        workflows: list[dict[str, Any]],
        confidence: list[dict[str, Any]],
        agents: list[dict[str, Any]],
    ) -> dict[str, Any]:
        accepted = sum(1 for row in recommendations if str(row.get("status", "")).lower() == "accepted")
        rejected = sum(1 for row in recommendations if str(row.get("status", "")).lower() == "rejected")
        rollback_count = sum(1 for row in recommendations if row.get("rollback_required"))
        completed = sum(1 for row in outcomes if row.get("status") == "Completed")
        return {
            "Recommendations Accepted": accepted,
            "Recommendations Rejected": rejected,
            "Average Savings Accuracy": _average([_safe_float(row.get("prediction_accuracy")) for row in outcomes], 97.0),
            "Agent Learning Score": _average([_safe_float(row.get("learning_score")) for row in agents], 96.0),
            "Workflow Success Rate": round(completed / max(len(outcomes), 1) * 100, 1),
            "Rollback Rate": round(rollback_count / max(len(recommendations), 1) * 100, 1),
            "Prediction Improvement": _average([_safe_float(row.get("prediction_accuracy")) for row in workflows], 96.0),
            "Confidence Improvement": round(sum(_safe_float(row.get("confidence_delta")) for row in confidence), 1),
        }

    @staticmethod
    def _learning_health_score(kpis: dict[str, Any]) -> float:
        return round(
            _safe_float(kpis["Average Savings Accuracy"]) * 0.30
            + _safe_float(kpis["Workflow Success Rate"]) * 0.25
            + (100 - _safe_float(kpis["Rollback Rate"])) * 0.20
            + _safe_float(kpis["Prediction Improvement"]) * 0.15
            + min(100.0, 90.0 + _safe_float(kpis["Confidence Improvement"])) * 0.10,
            1,
        )

    @staticmethod
    def _normalize_outcomes(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [
            {
                "Goal": row.get("goal_text") or row.get("goal"),
                "Expected Savings": _safe_float(row.get("expected_savings")),
                "Actual Savings": _safe_float(row.get("actual_savings")),
                "Variance": _safe_float(row.get("variance")),
                "Prediction Accuracy": _safe_float(row.get("prediction_accuracy")),
                "Recommendation Quality": _safe_float(row.get("recommendation_quality")),
                "Business Impact": row.get("business_impact"),
                "Operational Success": _safe_float(row.get("operational_success")),
                "Status": row.get("status"),
            }
            for row in rows
        ]

    @staticmethod
    def _normalize_recommendations(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [
            {
                "Status": row.get("status"),
                "Successful": row.get("successful"),
                "Expected Savings": _safe_float(row.get("expected_savings")),
                "Actual Savings": _safe_float(row.get("actual_savings")),
                "Rollback": bool(row.get("rollback_required")),
                "Quality": _safe_float(row.get("recommendation_quality")),
            }
            for row in rows
        ]

    @staticmethod
    def _agent_scorecards(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        grouped: dict[str, list[dict[str, Any]]] = {}
        for row in rows:
            grouped.setdefault(row.get("agent_name", "Unknown Agent"), []).append(row)
        scorecards = []
        for agent, agent_rows in grouped.items():
            scorecards.append(
                {
                    "Agent": agent,
                    "Plans Generated": sum(int(_safe_float(row.get("plans_generated"))) for row in agent_rows),
                    "Accepted": sum(1 for row in agent_rows if row.get("accepted")),
                    "Rejected": sum(1 for row in agent_rows if row.get("rejected")),
                    "Execution Success": _average([_safe_float(row.get("execution_success")) for row in agent_rows], 95.0),
                    "Average Confidence": _average([_safe_float(row.get("average_confidence")) for row in agent_rows], 95.0),
                    "Learning Score": _average([_safe_float(row.get("learning_score")) for row in agent_rows], 95.0),
                },
            )
        return sorted(scorecards, key=lambda row: row["Learning Score"], reverse=True)

    @staticmethod
    def _normalize_workflows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [
            {
                "Template": row.get("template_name"),
                "Version Before": row.get("version_before"),
                "Version After": row.get("version_after"),
                "Execution Success": _safe_float(row.get("execution_success")),
                "Prediction Accuracy": _safe_float(row.get("prediction_accuracy")),
                "Lessons Learned": "; ".join(row.get("lessons_learned") or []),
            }
            for row in rows
        ]

    @staticmethod
    def _normalize_template_improvements(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [
            {
                "Template": row.get("template_name"),
                "Version": row.get("version"),
                "Improvement": row.get("improvement_type"),
                "Lesson": row.get("lesson"),
                "Recommended Change": row.get("recommended_change"),
                "Status": row.get("status"),
            }
            for row in rows
        ]

    @staticmethod
    def _normalize_confidence(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [
            {
                "Metric": row.get("metric_name"),
                "Before": _safe_float(row.get("confidence_before")),
                "After": _safe_float(row.get("confidence_after")),
                "Delta": _safe_float(row.get("confidence_delta")),
                "Measured At": row.get("created_at"),
            }
            for row in rows
        ]

    @staticmethod
    def _normalize_insights(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [
            {
                "Title": row.get("title"),
                "Insight": row.get("insight"),
                "Severity": row.get("severity"),
                "Recommended Action": row.get("recommended_action"),
            }
            for row in rows
        ]

    @staticmethod
    def _knowledge_memory_from_summaries(summaries: list[dict[str, Any]], insights: list[dict[str, Any]]) -> list[str]:
        memory: list[str] = []
        for row in summaries:
            values = row.get("knowledge_memory") or []
            if isinstance(values, list):
                memory.extend(str(value) for value in values)
        if not memory:
            memory.extend(str(row.get("insight")) for row in insights[:4] if row.get("insight"))
        return list(dict.fromkeys(memory))[:8]

    @staticmethod
    def _dashboard_summary(kpis: dict[str, Any]) -> str:
        return (
            f"This month Nexora accepted {kpis['Recommendations Accepted']} recommendations, "
            f"kept savings accuracy at {kpis['Average Savings Accuracy']:.1f}%, "
            f"held rollback rate to {kpis['Rollback Rate']:.1f}%, and improved confidence by "
            f"{kpis['Confidence Improvement']:+.1f} points."
        )
