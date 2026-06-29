from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from connectors.common.tenant_guard import resolve_organization_id
from services.ai_decision_service import AIDecisionService
from services.supabase_client import supabase


class AIWorkflowService:
    TABLE_NAME = "ai_workflow_actions"

    @staticmethod
    def generate_workflow_actions(organization_id: str | None = None) -> dict[str, Any]:
        org_id = resolve_organization_id(organization_id)
        decisions = AIDecisionService.get_decisions(org_id, persist=False)
        existing_actions = {row.get("action_id"): row for row in AIWorkflowService._load_actions(org_id)}
        actions = [
            AIWorkflowService._merge_existing_state(
                AIWorkflowService._action_from_decision(index, decision, org_id),
                existing_actions,
            )
            for index, decision in enumerate(decisions, start=1)
        ]
        persistence = AIWorkflowService._persist_actions(actions)
        return {
            "status": "SUCCESS",
            "organization_id": org_id,
            "workflow_actions": len(actions),
            "pending_approval": len([row for row in actions if row["approval_status"] == "Pending"]),
            "automation_eligible": len([row for row in actions if row["automation_eligible"]]),
            "expected_savings": round(sum(float(row.get("expected_savings") or 0) for row in actions), 2),
            "expected_risk_reduction": round(AIWorkflowService._average([row.get("expected_risk_reduction") for row in actions]), 1),
            "audit_safe": True,
            "persistence": persistence,
            "actions": actions,
        }

    @staticmethod
    def get_action_queue(organization_id: str | None = None) -> list[dict[str, Any]]:
        rows = AIWorkflowService._load_actions(resolve_organization_id(organization_id))
        if not rows:
            rows = AIWorkflowService.generate_workflow_actions(organization_id).get("actions", [])
        return rows

    @staticmethod
    def get_pending_approvals(organization_id: str | None = None) -> list[dict[str, Any]]:
        return [row for row in AIWorkflowService.get_action_queue(organization_id) if row.get("approval_status") == "Pending"]

    @staticmethod
    def approve_action(action_id: str, organization_id: str | None = None) -> dict[str, Any]:
        return AIWorkflowService._transition_action(action_id, organization_id, "Approved", None)

    @staticmethod
    def reject_action(action_id: str, reason: str | None = None, organization_id: str | None = None) -> dict[str, Any]:
        return AIWorkflowService._transition_action(action_id, organization_id, "Rejected", reason)

    @staticmethod
    def execute_action(action_id: str, organization_id: str | None = None) -> dict[str, Any]:
        org_id = resolve_organization_id(organization_id)
        action = AIWorkflowService._find_action(action_id, org_id)
        if not action:
            return {"status": "FAILED", "message": "Action not found"}
        if action.get("approval_status") not in {"Approved", "Auto-Approved"}:
            return {"status": "FAILED", "message": "Action must be approved before execution"}
        if AIWorkflowService._never_auto_execute(action):
            return {"status": "FAILED", "message": "Action is blocked by execution guardrails"}

        status = "Executed"
        message = "Safe placeholder execution recorded"
        payload = {
            "execution_status": status,
            "updated_at": AIWorkflowService._now(),
            "audit_trail": AIWorkflowService._append_audit(action, "EXECUTE", message),
        }
        return AIWorkflowService._update_action(action_id, org_id, payload, {"status": "SUCCESS", "message": message})

    @staticmethod
    def get_workflow_summary(organization_id: str | None = None) -> dict[str, Any]:
        return AIWorkflowService.get_dashboard(organization_id)["summary"]

    @staticmethod
    def get_dashboard(organization_id: str | None = None) -> dict[str, Any]:
        actions = AIWorkflowService.get_action_queue(organization_id)
        summary = AIWorkflowService._summary(actions)
        return {
            "summary": summary,
            "actions": actions,
            "pending_approval_queue": [row for row in actions if row.get("approval_status") == "Pending"],
            "auto_remediation_candidates": [row for row in actions if row.get("automation_eligible")],
            "executed_actions": [
                row for row in actions if str(row.get("execution_status") or "").upper() in {"EXECUTED", "COMPLETED", "CLOSED"}
            ],
            "failed_actions": [row for row in actions if str(row.get("execution_status") or "").upper() in {"FAILED", "EXECUTION_FAILED"}],
            "audit_trail": AIWorkflowService._audit_rows(actions),
        }

    @staticmethod
    def _action_from_decision(index: int, decision: dict[str, Any], organization_id: str) -> dict[str, Any]:
        action_type = AIWorkflowService._action_type(decision)
        approval_required = AIWorkflowService._requires_approval(decision, action_type)
        auto_approved = decision.get("automation_eligible") and not approval_required
        if auto_approved:
            approval_status = "Auto-Approved"
        elif approval_required:
            approval_status = "Pending"
        else:
            approval_status = "Approved"
        now = AIWorkflowService._now()
        action_id = f"WF-{index:06d}"
        return {
            "organization_id": organization_id,
            "action_id": action_id,
            "decision_id": decision.get("decision_id"),
            "recommendation_id": decision.get("recommendation_id"),
            "action_type": action_type,
            "title": decision.get("recommendation") or decision.get("decision"),
            "description": decision.get("recommended_action"),
            "owner": decision.get("owner"),
            "approval_required": approval_required,
            "approval_status": approval_status,
            "execution_status": "Not Started",
            "automation_eligible": bool(decision.get("automation_eligible")),
            "risk_level": decision.get("risk") or "Medium",
            "confidence": int(decision.get("confidence") or 0),
            "expected_savings": float(decision.get("expected_savings") or 0),
            "expected_risk_reduction": float(decision.get("expected_risk_reduction") or 0),
            "payload": {
                "decision": decision,
                "guardrails": AIWorkflowService._guardrail_notes(decision, action_type, approval_required),
                "audit_safe": True,
            },
            "audit_trail": [
                {
                    "timestamp": now,
                    "event": "CREATE_ACTION",
                    "message": "Workflow action generated from AI decision",
                    "actor": "AIWorkflowService",
                },
                {
                    "timestamp": now,
                    "event": AIWorkflowService._initial_audit_event(auto_approved, approval_required),
                    "message": AIWorkflowService._initial_audit_message(auto_approved, approval_required),
                    "actor": "AIWorkflowService",
                },
            ],
            "created_at": now,
            "updated_at": now,
        }

    @staticmethod
    def _action_type(decision: dict[str, Any]) -> str:
        action = str(decision.get("recommended_action") or "").lower()
        category_text = " ".join(str(decision.get(key) or "") for key in ["classification", "automation", "decision", "recommendation"]).lower()
        if "connector" in action or "discovery" in action or "sync" in action or "connector" in category_text:
            return "RUN_CONNECTOR_SYNC"
        if "approval" in str(decision.get("status") or "").lower() or decision.get("approval_required") not in {"None", None, ""}:
            return "CREATE_APPROVAL"
        if decision.get("decision") == "Approve":
            return "MARK_DECISION_APPROVED"
        return "CREATE_TASK"

    @staticmethod
    def _requires_approval(decision: dict[str, Any], action_type: str) -> bool:
        if action_type == "RUN_CONNECTOR_SYNC" and decision.get("automation_eligible"):
            return False
        if decision.get("priority") == "Critical" and float(decision.get("expected_savings") or 0) > 0:
            return True
        if str(decision.get("security_impact") or "") in {"High", "Critical"}:
            return True
        if decision.get("approval_required") not in {"None", None, ""}:
            return True
        return False

    @staticmethod
    def _transition_action(
        action_id: str,
        organization_id: str | None,
        approval_status: str,
        reason: str | None,
    ) -> dict[str, Any]:
        org_id = resolve_organization_id(organization_id)
        action = AIWorkflowService._find_action(action_id, org_id)
        if not action:
            return {"status": "FAILED", "message": "Action not found"}
        message = f"Action {approval_status.lower()}"
        if reason:
            message = f"{message}: {reason}"
        payload = {
            "approval_status": approval_status,
            "execution_status": "READY" if approval_status == "Approved" else "FAILED" if approval_status == "Rejected" else action.get("execution_status"),
            "updated_at": AIWorkflowService._now(),
            "audit_trail": AIWorkflowService._append_audit(action, approval_status.upper(), message),
        }
        return AIWorkflowService._update_action(action_id, org_id, payload, {"status": "SUCCESS", "message": message})

    @staticmethod
    def _merge_existing_state(
        action: dict[str, Any],
        existing_actions: dict[str, dict[str, Any]],
    ) -> dict[str, Any]:
        existing = existing_actions.get(action.get("action_id"))
        if not existing:
            return action
        preserve_fields = [
            "approval_status",
            "execution_status",
            "assigned_to",
            "assigned_team",
            "assigned_role",
            "execution_started_at",
            "execution_completed_at",
            "validated_by",
            "validated_at",
            "evidence_url",
            "implementation_notes",
            "rollback_notes",
            "actual_savings",
            "actual_risk_reduction",
            "execution_duration_minutes",
            "last_status_change",
            "execution_progress",
            "automation_readiness",
            "audit_trail",
        ]
        for field in preserve_fields:
            if field in existing and existing.get(field) not in (None, ""):
                action[field] = existing.get(field)
        return action

    @staticmethod
    def _persist_actions(actions: list[dict[str, Any]]) -> dict[str, Any]:
        if not actions:
            return {"status": "SUCCESS", "rows": 0}
        try:
            supabase.table(AIWorkflowService.TABLE_NAME).upsert(actions, on_conflict="action_id").execute()
            return {"status": "SUCCESS", "rows": len(actions)}
        except Exception as exc:
            return {"status": "SKIPPED", "rows": 0, "error": str(exc)}

    @staticmethod
    def _load_actions(organization_id: str) -> list[dict[str, Any]]:
        try:
            return (
                supabase.table(AIWorkflowService.TABLE_NAME)
                .select("*")
                .eq("organization_id", organization_id)
                .order("created_at", desc=True)
                .limit(500)
                .execute()
                .data
                or []
            )
        except Exception:
            return []

    @staticmethod
    def _find_action(action_id: str, organization_id: str) -> dict[str, Any] | None:
        target = str(action_id or "").strip()
        for row in AIWorkflowService.get_action_queue(organization_id):
            if row.get("action_id") == target:
                return row
        return None

    @staticmethod
    def _update_action(
        action_id: str,
        organization_id: str,
        payload: dict[str, Any],
        result: dict[str, Any],
    ) -> dict[str, Any]:
        try:
            supabase.table(AIWorkflowService.TABLE_NAME).update(payload).eq("organization_id", organization_id).eq(
                "action_id",
                action_id,
            ).execute()
            return result
        except Exception as exc:
            return {"status": "FAILED", "message": str(exc)}

    @staticmethod
    def _summary(actions: list[dict[str, Any]]) -> dict[str, Any]:
        return {
            "total_actions": len(actions),
            "pending_approval": len([row for row in actions if row.get("approval_status") == "Pending"]),
            "approved": len([row for row in actions if row.get("approval_status") in {"Approved", "Auto-Approved"}]),
            "rejected": len([row for row in actions if row.get("approval_status") == "Rejected"]),
            "executed": len(
                [row for row in actions if str(row.get("execution_status") or "").upper() in {"EXECUTED", "COMPLETED", "CLOSED"}]
            ),
            "failed": len([row for row in actions if str(row.get("execution_status") or "").upper() in {"FAILED", "EXECUTION_FAILED"}]),
            "automation_eligible": len([row for row in actions if row.get("automation_eligible")]),
            "expected_savings": round(sum(float(row.get("expected_savings") or 0) for row in actions), 2),
            "expected_risk_reduction": round(AIWorkflowService._average([row.get("expected_risk_reduction") for row in actions]), 1),
            "audit_safe": True,
        }

    @staticmethod
    def _audit_rows(actions: list[dict[str, Any]]) -> list[dict[str, Any]]:
        rows = []
        for action in actions:
            trail = action.get("audit_trail") or []
            if isinstance(trail, str):
                trail = []
            for item in trail:
                rows.append(
                    {
                        "Action ID": action.get("action_id"),
                        "Event": item.get("event"),
                        "Message": item.get("message"),
                        "Actor": item.get("actor"),
                        "Timestamp": item.get("timestamp"),
                    }
                )
        return rows

    @staticmethod
    def _append_audit(action: dict[str, Any], event: str, message: str) -> list[dict[str, Any]]:
        trail = action.get("audit_trail") or []
        if isinstance(trail, str):
            trail = []
        return [
            *trail,
            {
                "timestamp": AIWorkflowService._now(),
                "event": event,
                "message": message,
                "actor": "AIWorkflowService",
            },
        ]

    @staticmethod
    def _guardrail_notes(decision: dict[str, Any], action_type: str, approval_required: bool) -> list[str]:
        notes = ["Approval-first workflow enabled", "No destructive execution allowed in A.6.6"]
        if decision.get("priority") == "Critical" and float(decision.get("expected_savings") or 0) > 0:
            notes.append("Critical financial action requires approval")
        if action_type == "RUN_CONNECTOR_SYNC":
            notes.append("Connector sync can be auto-approved but remains audit logged")
        if str(decision.get("security_impact") or "") in {"High", "Critical"}:
            notes.append("Security/IAM action requires manual approval")
        if approval_required:
            notes.append("Approval required before execution")
        return notes

    @staticmethod
    def _initial_audit_event(auto_approved: bool, approval_required: bool) -> str:
        if auto_approved:
            return "AUTO_APPROVE"
        if approval_required:
            return "ROUTE_APPROVAL"
        return "RECORD_ACTION"

    @staticmethod
    def _initial_audit_message(auto_approved: bool, approval_required: bool) -> str:
        if auto_approved:
            return "Connector sync action auto-approved"
        if approval_required:
            return "Approval required by guardrails"
        return "Action recorded with no approval requirement"

    @staticmethod
    def _never_auto_execute(action: dict[str, Any]) -> bool:
        text = " ".join(str(action.get(key) or "") for key in ["title", "description", "action_type"]).lower()
        return any(token in text for token in ["delete", "remove", "terminate", "modify", "write"])

    @staticmethod
    def _average(values: list[Any]) -> float:
        numeric = [float(value) for value in values if value not in (None, "")]
        if not numeric:
            return 0.0
        return sum(numeric) / len(numeric)

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()
