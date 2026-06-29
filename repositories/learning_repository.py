from __future__ import annotations

import uuid
from typing import Any

from connectors.common.tenant_guard import resolve_organization_id
from services.supabase_client import supabase


class LearningRepository:
    TABLES = (
        "learning_outcome",
        "learning_insight",
        "recommendation_feedback",
        "workflow_feedback",
        "agent_feedback",
        "confidence_history",
        "template_improvement",
        "learning_summary",
        "execution_metrics",
    )

    @staticmethod
    def save_learning_package(package: dict[str, Any]) -> bool:
        org_id = resolve_organization_id(package.get("organization_id"))
        learning_id = package.get("id") or str(uuid.uuid4())
        ok = True
        ok = LearningRepository.insert_row(
            "learning_outcome",
            {
                "id": learning_id,
                "organization_id": org_id,
                "execution_id": package.get("execution_id"),
                "workflow_id": package.get("workflow_id"),
                "goal_text": package.get("goal"),
                "expected_savings": package.get("expected_savings", 0),
                "actual_savings": package.get("actual_savings", 0),
                "variance": package.get("variance", 0),
                "prediction_accuracy": package.get("prediction_accuracy", 0),
                "recommendation_quality": package.get("recommendation_quality", 0),
                "business_impact": package.get("business_impact"),
                "operational_success": package.get("operational_success", 0),
                "status": package.get("status"),
                "outcome_payload": package,
            },
        ) and ok
        for row in package.get("recommendation_feedback", []):
            ok = LearningRepository.insert_row("recommendation_feedback", {**row, "organization_id": org_id}) and ok
        for row in package.get("agent_feedback", []):
            ok = LearningRepository.insert_row("agent_feedback", {**row, "organization_id": org_id}) and ok
        for row in package.get("workflow_feedback", []):
            ok = LearningRepository.insert_row("workflow_feedback", {**row, "organization_id": org_id}) and ok
        for row in package.get("confidence_history", []):
            ok = LearningRepository.insert_row("confidence_history", {**row, "organization_id": org_id}) and ok
        for row in package.get("template_improvements", []):
            ok = LearningRepository.insert_row("template_improvement", {**row, "organization_id": org_id}) and ok
        for row in package.get("learning_insights", []):
            ok = LearningRepository.insert_row("learning_insight", {**row, "organization_id": org_id}) and ok
        for row in package.get("execution_metrics", []):
            ok = LearningRepository.insert_row("execution_metrics", {**row, "organization_id": org_id}) and ok
        ok = LearningRepository.insert_row(
            "learning_summary",
            {
                "id": str(uuid.uuid4()),
                "organization_id": org_id,
                "learning_id": learning_id,
                "summary": package.get("executive_summary"),
                "learning_score": package.get("learning_score", 0),
                "knowledge_memory": package.get("knowledge_memory", []),
                "summary_payload": package.get("summary", {}),
            },
        ) and ok
        return ok

    @staticmethod
    def insert_row(table_name: str, payload: dict[str, Any]) -> bool:
        row = dict(payload)
        row.setdefault("id", str(uuid.uuid4()))
        try:
            supabase.table(table_name).insert(row).execute()
            return True
        except Exception:
            return False

    @staticmethod
    def list_rows(table_name: str, organization_id: str | None = None, limit: int = 200) -> list[dict[str, Any]]:
        org_id = resolve_organization_id(organization_id)
        try:
            return (
                supabase.table(table_name)
                .select("*")
                .eq("organization_id", org_id)
                .order("created_at", desc=True)
                .limit(limit)
                .execute()
                .data
                or []
            )
        except Exception:
            return []
