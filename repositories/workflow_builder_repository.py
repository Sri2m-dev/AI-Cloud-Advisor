from __future__ import annotations

import uuid
from typing import Any

from connectors.common.tenant_guard import resolve_organization_id
from services.supabase_client import supabase


class WorkflowBuilderRepository:
    @staticmethod
    def save_blueprint(blueprint: dict[str, Any]) -> bool:
        org_id = resolve_organization_id(blueprint.get("organization_id"))
        workflow_id = blueprint.get("id") or str(uuid.uuid4())
        ok = True
        ok = WorkflowBuilderRepository._insert(
            "workflow_blueprint",
            {
                "id": workflow_id,
                "organization_id": org_id,
                "goal_id": blueprint.get("goal_id"),
                "goal_text": blueprint.get("goal"),
                "template_name": blueprint.get("template", {}).get("Name"),
                "status": blueprint.get("status", "Blueprint Ready"),
                "stage_count": len(blueprint.get("stages", [])),
                "task_count": len(blueprint.get("tasks", [])),
                "approval_count": len(blueprint.get("approvals", [])),
                "estimated_duration": blueprint.get("estimated_duration"),
                "business_risk": blueprint.get("business_risk"),
                "confidence": blueprint.get("confidence", 0),
                "execution_enabled": False,
                "executive_summary": blueprint.get("executive_summary"),
                "blueprint_payload": blueprint,
            },
        ) and ok
        for stage in blueprint.get("stages", []):
            ok = WorkflowBuilderRepository._insert(
                "workflow_stage",
                {
                    "id": str(uuid.uuid4()),
                    "organization_id": org_id,
                    "workflow_id": workflow_id,
                    "stage_number": stage.get("Stage"),
                    "stage_name": stage.get("Name"),
                    "description": stage.get("Description"),
                    "owner": stage.get("Owner"),
                    "status": "Planned",
                },
            ) and ok
        for task in blueprint.get("tasks", []):
            ok = WorkflowBuilderRepository._insert(
                "workflow_task",
                {
                    "id": task.get("id") or str(uuid.uuid4()),
                    "organization_id": org_id,
                    "workflow_id": workflow_id,
                    "stage_name": task.get("Stage"),
                    "task_number": task.get("Task"),
                    "task_name": task.get("Name"),
                    "description": task.get("Description"),
                    "owner": task.get("Owner"),
                    "estimated_duration": task.get("Estimated Duration"),
                    "success_criteria": task.get("Success Criteria"),
                    "rollback_action": task.get("Rollback Action"),
                    "status": "Planned",
                },
            ) and ok
        for dependency in blueprint.get("dependencies", []):
            ok = WorkflowBuilderRepository._insert(
                "workflow_dependency",
                {
                    "id": str(uuid.uuid4()),
                    "organization_id": org_id,
                    "workflow_id": workflow_id,
                    "task_name": dependency.get("Task"),
                    "depends_on": dependency.get("Depends On"),
                    "dependency_type": dependency.get("Type", "Sequential"),
                },
            ) and ok
        for approval in blueprint.get("approvals", []):
            ok = WorkflowBuilderRepository._insert(
                "workflow_approval",
                {
                    "id": str(uuid.uuid4()),
                    "organization_id": org_id,
                    "workflow_id": workflow_id,
                    "approver_role": approval.get("Approver Role"),
                    "approver": approval.get("Approver"),
                    "approval_stage": approval.get("Stage"),
                    "required": approval.get("Required", True),
                    "policy_reason": approval.get("Policy Reason"),
                    "status": "Pending",
                },
            ) and ok
        for validation in blueprint.get("validation", []):
            ok = WorkflowBuilderRepository._insert(
                "workflow_validation",
                {
                    "id": str(uuid.uuid4()),
                    "organization_id": org_id,
                    "workflow_id": workflow_id,
                    "check_name": validation.get("Check"),
                    "metric": validation.get("Metric"),
                    "success_criteria": validation.get("Success Criteria"),
                    "owner": validation.get("Owner"),
                    "status": "Planned",
                },
            ) and ok
        for rollback in blueprint.get("rollback", []):
            ok = WorkflowBuilderRepository._insert(
                "workflow_rollback",
                {
                    "id": str(uuid.uuid4()),
                    "organization_id": org_id,
                    "workflow_id": workflow_id,
                    "trigger_name": rollback.get("Trigger"),
                    "rollback_task": rollback.get("Rollback Task"),
                    "verification": rollback.get("Verification"),
                    "business_validation": rollback.get("Business Validation"),
                    "closure": rollback.get("Closure"),
                },
            ) and ok
        return ok

    @staticmethod
    def list_blueprints(organization_id: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
        return WorkflowBuilderRepository._list("workflow_blueprint", organization_id, limit)

    @staticmethod
    def list_templates(organization_id: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        return WorkflowBuilderRepository._list("workflow_template", organization_id, limit)

    @staticmethod
    def _insert(table_name: str, payload: dict[str, Any]) -> bool:
        try:
            supabase.table(table_name).insert(payload).execute()
            return True
        except Exception:
            return False

    @staticmethod
    def _list(table_name: str, organization_id: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
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
