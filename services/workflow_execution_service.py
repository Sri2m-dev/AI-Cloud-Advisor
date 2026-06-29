from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from connectors.common.tenant_guard import resolve_organization_id
from services.ai_workflow_service import AIWorkflowService
from services.supabase_client import supabase


class WorkflowExecutionService:
    ACTION_TABLE = "ai_workflow_actions"
    HISTORY_TABLE = "workflow_execution_history"

    STATUS_PENDING_APPROVAL = "PENDING_APPROVAL"
    STATUS_APPROVED = "APPROVED"
    STATUS_READY = "READY"
    STATUS_SIMULATING = "SIMULATING"
    STATUS_READY_FOR_EXECUTION = "READY_FOR_EXECUTION"
    STATUS_EXECUTING = "EXECUTING"
    STATUS_VALIDATING = "VALIDATING"
    STATUS_ASSIGNED = "ASSIGNED"
    STATUS_IN_PROGRESS = "IN_PROGRESS"
    STATUS_WAITING_VALIDATION = "WAITING_VALIDATION"
    STATUS_COMPLETED = "COMPLETED"
    STATUS_FAILED = "FAILED"
    STATUS_EXECUTION_FAILED = "EXECUTION_FAILED"
    STATUS_ROLLED_BACK = "ROLLED_BACK"
    STATUS_CLOSED = "CLOSED"

    ALLOWED_TRANSITIONS = {
        STATUS_PENDING_APPROVAL: {STATUS_APPROVED, STATUS_FAILED},
        STATUS_APPROVED: {STATUS_READY, STATUS_ASSIGNED, STATUS_FAILED},
        STATUS_READY: {STATUS_ASSIGNED, STATUS_IN_PROGRESS, STATUS_SIMULATING, STATUS_FAILED, STATUS_EXECUTION_FAILED},
        STATUS_SIMULATING: {STATUS_READY_FOR_EXECUTION, STATUS_READY, STATUS_FAILED, STATUS_EXECUTION_FAILED},
        STATUS_READY_FOR_EXECUTION: {STATUS_EXECUTING, STATUS_ASSIGNED, STATUS_ROLLED_BACK, STATUS_EXECUTION_FAILED},
        STATUS_EXECUTING: {STATUS_VALIDATING, STATUS_EXECUTION_FAILED, STATUS_ROLLED_BACK},
        STATUS_VALIDATING: {STATUS_COMPLETED, STATUS_EXECUTION_FAILED, STATUS_ROLLED_BACK},
        STATUS_ASSIGNED: {STATUS_IN_PROGRESS, STATUS_READY, STATUS_SIMULATING, STATUS_FAILED, STATUS_EXECUTION_FAILED},
        STATUS_IN_PROGRESS: {STATUS_WAITING_VALIDATION, STATUS_ASSIGNED, STATUS_FAILED, STATUS_ROLLED_BACK},
        STATUS_WAITING_VALIDATION: {STATUS_COMPLETED, STATUS_IN_PROGRESS, STATUS_FAILED, STATUS_ROLLED_BACK},
        STATUS_COMPLETED: {STATUS_CLOSED, STATUS_ROLLED_BACK},
        STATUS_FAILED: {STATUS_READY, STATUS_CLOSED},
        STATUS_EXECUTION_FAILED: {STATUS_READY, STATUS_ROLLED_BACK, STATUS_CLOSED},
        STATUS_ROLLED_BACK: {STATUS_READY, STATUS_CLOSED},
        STATUS_CLOSED: set(),
    }

    KANBAN_STATUSES = [
        STATUS_READY,
        STATUS_SIMULATING,
        STATUS_READY_FOR_EXECUTION,
        STATUS_EXECUTING,
        STATUS_VALIDATING,
        STATUS_ASSIGNED,
        STATUS_IN_PROGRESS,
        STATUS_WAITING_VALIDATION,
        STATUS_COMPLETED,
        STATUS_EXECUTION_FAILED,
        STATUS_FAILED,
        STATUS_ROLLED_BACK,
    ]

    @staticmethod
    def assign_action(
        action_id: str,
        assigned_to: str | None = None,
        assigned_team: str | None = None,
        assigned_role: str | None = None,
        organization_id: str | None = None,
        actor: str | None = None,
    ) -> dict[str, Any]:
        action, org_id = WorkflowExecutionService._require_action(action_id, organization_id)
        if not action:
            return WorkflowExecutionService._not_found()
        team = assigned_team or WorkflowExecutionService.determine_assignment_team(action)
        role = assigned_role or WorkflowExecutionService._default_role_for_team(team)
        return WorkflowExecutionService._transition(
            action,
            org_id,
            WorkflowExecutionService.STATUS_ASSIGNED,
            actor,
            "Action assigned for execution",
            {
                "assigned_to": assigned_to or action.get("assigned_to") or action.get("owner"),
                "assigned_team": team,
                "assigned_role": role,
                "automation_readiness": WorkflowExecutionService.determine_automation_readiness(action),
            },
        )

    @staticmethod
    def start_execution(
        action_id: str,
        organization_id: str | None = None,
        actor: str | None = None,
    ) -> dict[str, Any]:
        action, org_id = WorkflowExecutionService._require_action(action_id, organization_id)
        if not action:
            return WorkflowExecutionService._not_found()
        updates = {
            "execution_started_at": action.get("execution_started_at") or WorkflowExecutionService._now(),
            "execution_progress": max(int(action.get("execution_progress") or 0), 10),
        }
        return WorkflowExecutionService._transition(
            action,
            org_id,
            WorkflowExecutionService.STATUS_IN_PROGRESS,
            actor,
            "Execution started",
            updates,
        )

    @staticmethod
    def pause_execution(
        action_id: str,
        reason: str | None = None,
        organization_id: str | None = None,
        actor: str | None = None,
    ) -> dict[str, Any]:
        action, org_id = WorkflowExecutionService._require_action(action_id, organization_id)
        if not action:
            return WorkflowExecutionService._not_found()
        return WorkflowExecutionService._transition(
            action,
            org_id,
            WorkflowExecutionService.STATUS_ASSIGNED,
            actor,
            reason or "Execution paused and returned to assigned state",
        )

    @staticmethod
    def complete_execution(
        action_id: str,
        implementation_notes: str | None = None,
        actual_savings: float | None = None,
        actual_risk_reduction: float | None = None,
        organization_id: str | None = None,
        actor: str | None = None,
    ) -> dict[str, Any]:
        action, org_id = WorkflowExecutionService._require_action(action_id, organization_id)
        if not action:
            return WorkflowExecutionService._not_found()
        completed_at = WorkflowExecutionService._now()
        updates = {
            "execution_completed_at": completed_at,
            "implementation_notes": implementation_notes or action.get("implementation_notes"),
            "actual_savings": WorkflowExecutionService._number(actual_savings, action.get("actual_savings")),
            "actual_risk_reduction": WorkflowExecutionService._number(
                actual_risk_reduction,
                action.get("actual_risk_reduction"),
            ),
            "execution_progress": 100,
            "execution_duration_minutes": WorkflowExecutionService._duration_minutes(
                action.get("execution_started_at"),
                completed_at,
            ),
        }
        return WorkflowExecutionService._transition(
            action,
            org_id,
            WorkflowExecutionService.STATUS_WAITING_VALIDATION,
            actor,
            "Execution completed and waiting for validation",
            updates,
        )

    @staticmethod
    def validate_execution(
        action_id: str,
        validated_by: str | None = None,
        actual_savings: float | None = None,
        actual_risk_reduction: float | None = None,
        evidence_url: str | None = None,
        organization_id: str | None = None,
        actor: str | None = None,
    ) -> dict[str, Any]:
        action, org_id = WorkflowExecutionService._require_action(action_id, organization_id)
        if not action:
            return WorkflowExecutionService._not_found()
        updates = {
            "validated_by": validated_by or actor or action.get("validated_by"),
            "validated_at": WorkflowExecutionService._now(),
            "actual_savings": WorkflowExecutionService._number(actual_savings, action.get("actual_savings")),
            "actual_risk_reduction": WorkflowExecutionService._number(
                actual_risk_reduction,
                action.get("actual_risk_reduction"),
            ),
            "evidence_url": evidence_url or action.get("evidence_url"),
        }
        return WorkflowExecutionService._transition(
            action,
            org_id,
            WorkflowExecutionService.STATUS_COMPLETED,
            actor,
            "Execution validated",
            updates,
        )

    @staticmethod
    def close_action(
        action_id: str,
        organization_id: str | None = None,
        actor: str | None = None,
    ) -> dict[str, Any]:
        action, org_id = WorkflowExecutionService._require_action(action_id, organization_id)
        if not action:
            return WorkflowExecutionService._not_found()
        return WorkflowExecutionService._transition(
            action,
            org_id,
            WorkflowExecutionService.STATUS_CLOSED,
            actor,
            "Action closed after validation and ROI measurement",
        )

    @staticmethod
    def rollback_action(
        action_id: str,
        rollback_notes: str | None = None,
        organization_id: str | None = None,
        actor: str | None = None,
    ) -> dict[str, Any]:
        action, org_id = WorkflowExecutionService._require_action(action_id, organization_id)
        if not action:
            return WorkflowExecutionService._not_found()
        return WorkflowExecutionService._transition(
            action,
            org_id,
            WorkflowExecutionService.STATUS_ROLLED_BACK,
            actor,
            rollback_notes or "Execution rolled back",
            {"rollback_notes": rollback_notes},
        )

    @staticmethod
    def fail_action(
        action_id: str,
        reason: str | None = None,
        organization_id: str | None = None,
        actor: str | None = None,
    ) -> dict[str, Any]:
        action, org_id = WorkflowExecutionService._require_action(action_id, organization_id)
        if not action:
            return WorkflowExecutionService._not_found()
        return WorkflowExecutionService._transition(
            action,
            org_id,
            WorkflowExecutionService.STATUS_FAILED,
            actor,
            reason or "Execution failed",
        )

    @staticmethod
    def reassign_action(
        action_id: str,
        assigned_to: str | None = None,
        assigned_team: str | None = None,
        assigned_role: str | None = None,
        organization_id: str | None = None,
        actor: str | None = None,
    ) -> dict[str, Any]:
        action, org_id = WorkflowExecutionService._require_action(action_id, organization_id)
        if not action:
            return WorkflowExecutionService._not_found()
        updates = {
            "assigned_to": assigned_to or action.get("assigned_to"),
            "assigned_team": assigned_team or WorkflowExecutionService.determine_assignment_team(action),
            "assigned_role": assigned_role or action.get("assigned_role"),
        }
        current_status = WorkflowExecutionService._status(action)
        target_status = current_status if current_status in {WorkflowExecutionService.STATUS_ASSIGNED, WorkflowExecutionService.STATUS_IN_PROGRESS} else WorkflowExecutionService.STATUS_ASSIGNED
        return WorkflowExecutionService._transition(action, org_id, target_status, actor, "Action reassigned", updates)

    @staticmethod
    def update_progress(
        action_id: str,
        progress: int,
        notes: str | None = None,
        organization_id: str | None = None,
        actor: str | None = None,
    ) -> dict[str, Any]:
        action, org_id = WorkflowExecutionService._require_action(action_id, organization_id)
        if not action:
            return WorkflowExecutionService._not_found()
        current_status = WorkflowExecutionService._status(action)
        if current_status not in {
            WorkflowExecutionService.STATUS_ASSIGNED,
            WorkflowExecutionService.STATUS_IN_PROGRESS,
            WorkflowExecutionService.STATUS_WAITING_VALIDATION,
        }:
            return WorkflowExecutionService._illegal_transition(current_status, current_status)
        bounded_progress = min(max(int(progress), 0), 100)
        updates = {
            "execution_progress": bounded_progress,
            "implementation_notes": notes or action.get("implementation_notes"),
            "last_status_change": WorkflowExecutionService._now(),
            "updated_at": WorkflowExecutionService._now(),
            "audit_trail": WorkflowExecutionService._append_audit(action, "UPDATE_PROGRESS", notes or f"Progress updated to {bounded_progress}%"),
        }
        updated = WorkflowExecutionService._update_action(action.get("action_id"), org_id, updates)
        WorkflowExecutionService._record_history(
            org_id,
            action.get("action_id"),
            current_status,
            current_status,
            "UPDATE_PROGRESS",
            actor,
            notes or f"Progress updated to {bounded_progress}%",
            {"progress": bounded_progress},
        )
        return {"status": "SUCCESS" if updated else "FAILED", "action_id": action.get("action_id"), "execution_status": current_status}

    @staticmethod
    def upload_evidence(
        action_id: str,
        evidence_url: str,
        notes: str | None = None,
        organization_id: str | None = None,
        actor: str | None = None,
    ) -> dict[str, Any]:
        action, org_id = WorkflowExecutionService._require_action(action_id, organization_id)
        if not action:
            return WorkflowExecutionService._not_found()
        current_status = WorkflowExecutionService._status(action)
        updates = {
            "evidence_url": evidence_url,
            "implementation_notes": notes or action.get("implementation_notes"),
            "updated_at": WorkflowExecutionService._now(),
            "audit_trail": WorkflowExecutionService._append_audit(action, "UPLOAD_EVIDENCE", notes or "Evidence uploaded"),
        }
        updated = WorkflowExecutionService._update_action(action.get("action_id"), org_id, updates)
        WorkflowExecutionService._record_history(
            org_id,
            action.get("action_id"),
            current_status,
            current_status,
            "UPLOAD_EVIDENCE",
            actor,
            notes or "Evidence uploaded",
            {"evidence_url": evidence_url},
            evidence_url,
        )
        return {"status": "SUCCESS" if updated else "FAILED", "action_id": action.get("action_id"), "evidence_url": evidence_url}

    @staticmethod
    def determine_assignment_team(action: dict[str, Any]) -> str:
        text = WorkflowExecutionService._search_text(action)
        rules = [
            (("azure",), "Azure Operations"),
            (("aws", "ec2", "rds", "s3", "ebs"), "Cloud Operations"),
            (("gcp", "google cloud"), "Cloud Operations"),
            (("license", "subscription", "renewal"), "IT Asset Management"),
            (("security", "iam", "credential", "permission"), "Security Team"),
            (("saas", "slack", "zoom", "microsoft 365"), "SaaS Governance"),
            (("database", "postgres", "sql", "rds"), "DBA Team"),
            (("kubernetes", "eks", "aks", "cluster"), "Platform Engineering"),
        ]
        for keywords, team in rules:
            if any(keyword in text for keyword in keywords):
                return team
        return action.get("owner") or "Operations"

    @staticmethod
    def determine_automation_readiness(action: dict[str, Any]) -> str:
        text = WorkflowExecutionService._search_text(action)
        if "schedule" in text or "cadence" in text:
            return "Scheduled"
        if action.get("automation_eligible") and action.get("action_type") == "RUN_CONNECTOR_SYNC":
            return "Automated"
        if action.get("automation_eligible"):
            return "Semi Automated"
        return "Manual"

    @staticmethod
    def get_action(action_id: str, organization_id: str | None = None) -> dict[str, Any] | None:
        action, _org_id = WorkflowExecutionService._require_action(action_id, organization_id)
        if not action:
            return None
        return WorkflowExecutionService._decorate_action(action)

    @staticmethod
    def get_action_queue(organization_id: str | None = None) -> list[dict[str, Any]]:
        org_id = resolve_organization_id(organization_id)
        actions = AIWorkflowService.get_action_queue(org_id)
        return [WorkflowExecutionService._decorate_action(action) for action in actions]

    @staticmethod
    def get_execution_history(action_id: str | None = None, organization_id: str | None = None) -> list[dict[str, Any]]:
        org_id = resolve_organization_id(organization_id)
        try:
            query = supabase.table(WorkflowExecutionService.HISTORY_TABLE).select("*").eq("organization_id", org_id)
            if action_id:
                query = query.eq("action_id", action_id)
            return query.order("created_at", desc=False).limit(500).execute().data or []
        except Exception:
            return WorkflowExecutionService._audit_history_from_actions(action_id, org_id)

    @staticmethod
    def get_dashboard(organization_id: str | None = None) -> dict[str, Any]:
        actions = WorkflowExecutionService.get_action_queue(organization_id)
        summary = WorkflowExecutionService._summary(actions)
        return {
            "summary": summary,
            "actions": actions,
            "kanban": {
                status: [action for action in actions if action.get("execution_status") == status]
                for status in WorkflowExecutionService.KANBAN_STATUSES
            },
            "pending_execution": [action for action in actions if action.get("execution_status") == WorkflowExecutionService.STATUS_READY],
            "assigned": [action for action in actions if action.get("execution_status") == WorkflowExecutionService.STATUS_ASSIGNED],
            "in_progress": [action for action in actions if action.get("execution_status") == WorkflowExecutionService.STATUS_IN_PROGRESS],
            "waiting_validation": [
                action for action in actions if action.get("execution_status") == WorkflowExecutionService.STATUS_WAITING_VALIDATION
            ],
            "completed": [action for action in actions if action.get("execution_status") == WorkflowExecutionService.STATUS_COMPLETED],
            "failed": [action for action in actions if action.get("execution_status") == WorkflowExecutionService.STATUS_FAILED],
            "history": WorkflowExecutionService.get_execution_history(organization_id=organization_id),
        }

    @staticmethod
    def _transition(
        action: dict[str, Any],
        organization_id: str,
        to_status: str,
        actor: str | None,
        message: str,
        updates: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        from_status = WorkflowExecutionService._status(action)
        if to_status != from_status and to_status not in WorkflowExecutionService.ALLOWED_TRANSITIONS.get(from_status, set()):
            return WorkflowExecutionService._illegal_transition(from_status, to_status)
        now = WorkflowExecutionService._now()
        payload = {
            **(updates or {}),
            "execution_status": to_status,
            "last_status_change": now,
            "updated_at": now,
            "audit_trail": WorkflowExecutionService._append_audit(action, f"STATE_{to_status}", message),
        }
        if to_status == WorkflowExecutionService.STATUS_IN_PROGRESS and not action.get("execution_started_at"):
            payload["execution_started_at"] = now
        updated = WorkflowExecutionService._update_action(action.get("action_id"), organization_id, payload)
        WorkflowExecutionService._record_history(
            organization_id,
            action.get("action_id"),
            from_status,
            to_status,
            f"STATE_{to_status}",
            actor,
            message,
            payload,
            payload.get("evidence_url"),
        )
        return {
            "status": "SUCCESS" if updated else "FAILED",
            "action_id": action.get("action_id"),
            "from_status": from_status,
            "to_status": to_status,
            "message": message,
        }

    @staticmethod
    def _require_action(action_id: str, organization_id: str | None) -> tuple[dict[str, Any] | None, str]:
        org_id = resolve_organization_id(organization_id)
        target = str(action_id or "").strip()
        for action in AIWorkflowService.get_action_queue(org_id):
            if action.get("action_id") == target:
                return WorkflowExecutionService._decorate_action(action), org_id
        return None, org_id

    @staticmethod
    def _decorate_action(action: dict[str, Any]) -> dict[str, Any]:
        decorated = dict(action)
        decorated["execution_status"] = WorkflowExecutionService._status(action)
        decorated["assigned_team"] = decorated.get("assigned_team") or WorkflowExecutionService.determine_assignment_team(decorated)
        decorated["assigned_role"] = decorated.get("assigned_role") or WorkflowExecutionService._default_role_for_team(decorated["assigned_team"])
        decorated["automation_readiness"] = decorated.get("automation_readiness") or WorkflowExecutionService.determine_automation_readiness(decorated)
        decorated["roi_realization_percent"] = WorkflowExecutionService._roi_realization(decorated)
        return decorated

    @staticmethod
    def _status(action: dict[str, Any]) -> str:
        raw_status = str(action.get("execution_status") or "").strip().upper().replace(" ", "_")
        if raw_status in WorkflowExecutionService.ALLOWED_TRANSITIONS:
            return raw_status
        if raw_status == "EXECUTED":
            return WorkflowExecutionService.STATUS_COMPLETED
        if raw_status == "NOT_STARTED":
            raw_status = ""
        if raw_status == "FAILED":
            return WorkflowExecutionService.STATUS_FAILED
        approval = str(action.get("approval_status") or "").strip()
        if approval == "Pending":
            return WorkflowExecutionService.STATUS_PENDING_APPROVAL
        if approval in {"Approved", "Auto-Approved"}:
            return WorkflowExecutionService.STATUS_READY
        if approval == "Rejected":
            return WorkflowExecutionService.STATUS_FAILED
        return WorkflowExecutionService.STATUS_PENDING_APPROVAL

    @staticmethod
    def _update_action(action_id: str, organization_id: str, payload: dict[str, Any]) -> bool:
        try:
            supabase.table(WorkflowExecutionService.ACTION_TABLE).update(payload).eq("organization_id", organization_id).eq(
                "action_id",
                action_id,
            ).execute()
            return True
        except Exception:
            fallback_payload = {
                key: value
                for key, value in payload.items()
                if key in {"approval_status", "execution_status", "updated_at", "audit_trail"}
            }
            if not fallback_payload:
                return False
            try:
                supabase.table(WorkflowExecutionService.ACTION_TABLE).update(fallback_payload).eq(
                    "organization_id",
                    organization_id,
                ).eq("action_id", action_id).execute()
                return True
            except Exception:
                return False

    @staticmethod
    def _record_history(
        organization_id: str,
        action_id: str,
        from_status: str | None,
        to_status: str,
        event_type: str,
        actor: str | None,
        message: str | None,
        metadata: dict[str, Any] | None = None,
        evidence_url: str | None = None,
    ) -> None:
        try:
            supabase.table(WorkflowExecutionService.HISTORY_TABLE).insert(
                {
                    "organization_id": organization_id,
                    "action_id": action_id,
                    "from_status": from_status,
                    "to_status": to_status,
                    "event_type": event_type,
                    "actor": actor or "WorkflowExecutionService",
                    "message": message,
                    "evidence_url": evidence_url,
                    "metadata": metadata or {},
                }
            ).execute()
        except Exception:
            return

    @staticmethod
    def _append_audit(action: dict[str, Any], event: str, message: str) -> list[dict[str, Any]]:
        trail = action.get("audit_trail") or []
        if isinstance(trail, str):
            trail = []
        return [
            *trail,
            {
                "timestamp": WorkflowExecutionService._now(),
                "event": event,
                "message": message,
                "actor": "WorkflowExecutionService",
            },
        ]

    @staticmethod
    def _summary(actions: list[dict[str, Any]]) -> dict[str, Any]:
        completed_today = len(
            [
                action
                for action in actions
                if action.get("execution_status") == WorkflowExecutionService.STATUS_COMPLETED
                and str(action.get("execution_completed_at") or "").startswith(WorkflowExecutionService._today())
            ]
        )
        automated = len([action for action in actions if action.get("automation_readiness") in {"Automated", "Scheduled"}])
        return {
            "total_actions": len(actions),
            "pending_execution": len([action for action in actions if action.get("execution_status") == WorkflowExecutionService.STATUS_READY]),
            "simulation": len([action for action in actions if action.get("execution_status") == WorkflowExecutionService.STATUS_SIMULATING]),
            "ready_for_execution": len(
                [action for action in actions if action.get("execution_status") == WorkflowExecutionService.STATUS_READY_FOR_EXECUTION]
            ),
            "executing": len([action for action in actions if action.get("execution_status") == WorkflowExecutionService.STATUS_EXECUTING]),
            "assigned": len([action for action in actions if action.get("execution_status") == WorkflowExecutionService.STATUS_ASSIGNED]),
            "in_progress": len([action for action in actions if action.get("execution_status") == WorkflowExecutionService.STATUS_IN_PROGRESS]),
            "validation": len([action for action in actions if action.get("execution_status") == WorkflowExecutionService.STATUS_VALIDATING]),
            "waiting_validation": len(
                [action for action in actions if action.get("execution_status") == WorkflowExecutionService.STATUS_WAITING_VALIDATION]
            ),
            "completed_today": completed_today,
            "completed": len([action for action in actions if action.get("execution_status") == WorkflowExecutionService.STATUS_COMPLETED]),
            "failed": len(
                [
                    action
                    for action in actions
                    if action.get("execution_status") in {WorkflowExecutionService.STATUS_FAILED, WorkflowExecutionService.STATUS_EXECUTION_FAILED}
                ]
            ),
            "rollback": len([action for action in actions if action.get("execution_status") == WorkflowExecutionService.STATUS_ROLLED_BACK]),
            "average_resolution_time_minutes": round(
                WorkflowExecutionService._average([action.get("execution_duration_minutes") for action in actions]),
                1,
            ),
            "automation_percent": round((automated / len(actions)) * 100, 1) if actions else 0,
            "realized_savings": round(sum(float(action.get("actual_savings") or 0) for action in actions), 2),
            "verified_savings": round(sum(float(action.get("actual_savings") or 0) for action in actions), 2),
            "projected_savings": round(sum(float(action.get("expected_savings") or 0) for action in actions), 2),
            "expected_savings": round(sum(float(action.get("expected_savings") or 0) for action in actions), 2),
            "risk_reduction": round(WorkflowExecutionService._average([action.get("actual_risk_reduction") for action in actions]), 1),
            "success_rate": WorkflowExecutionService._success_rate(actions),
            "rollback_percent": WorkflowExecutionService._status_percent(actions, WorkflowExecutionService.STATUS_ROLLED_BACK),
            "policy_compliance": 100.0,
        }

    @staticmethod
    def _audit_history_from_actions(action_id: str | None, organization_id: str) -> list[dict[str, Any]]:
        rows = []
        for action in AIWorkflowService.get_action_queue(organization_id):
            if action_id and action.get("action_id") != action_id:
                continue
            for item in action.get("audit_trail") or []:
                if isinstance(item, dict):
                    rows.append(
                        {
                            "organization_id": organization_id,
                            "action_id": action.get("action_id"),
                            "from_status": None,
                            "to_status": WorkflowExecutionService._status(action),
                            "event_type": item.get("event"),
                            "actor": item.get("actor"),
                            "message": item.get("message"),
                            "created_at": item.get("timestamp"),
                        }
                    )
        return rows

    @staticmethod
    def _search_text(action: dict[str, Any]) -> str:
        payload = action.get("payload") or {}
        decision = payload.get("decision") if isinstance(payload, dict) else {}
        fields = [
            action.get("title"),
            action.get("description"),
            action.get("action_type"),
            action.get("owner"),
            decision.get("category") if isinstance(decision, dict) else "",
            decision.get("recommended_action") if isinstance(decision, dict) else "",
            decision.get("recommendation") if isinstance(decision, dict) else "",
            decision.get("security_impact") if isinstance(decision, dict) else "",
        ]
        return " ".join(str(field or "") for field in fields).lower()

    @staticmethod
    def _default_role_for_team(team: str) -> str:
        roles = {
            "Azure Operations": "Cloud Engineer",
            "Cloud Operations": "Cloud Engineer",
            "IT Asset Management": "Asset Manager",
            "Security Team": "Security Administrator",
            "SaaS Governance": "SaaS Administrator",
            "DBA Team": "Database Administrator",
            "Platform Engineering": "Platform Engineer",
        }
        return roles.get(team, "Operations Owner")

    @staticmethod
    def _roi_realization(action: dict[str, Any]) -> float:
        expected = float(action.get("expected_savings") or 0)
        actual = float(action.get("actual_savings") or 0)
        if expected <= 0:
            return 0.0
        return round((actual / expected) * 100, 1)

    @staticmethod
    def _duration_minutes(started_at: Any, completed_at: Any) -> int:
        try:
            if not started_at or not completed_at:
                return 0
            start = datetime.fromisoformat(str(started_at).replace("Z", "+00:00"))
            end = datetime.fromisoformat(str(completed_at).replace("Z", "+00:00"))
            return max(int((end - start).total_seconds() // 60), 0)
        except Exception:
            return 0

    @staticmethod
    def _number(candidate: Any, fallback: Any) -> float:
        try:
            if candidate is not None:
                return float(candidate)
            return float(fallback or 0)
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def _average(values: list[Any]) -> float:
        numeric = [float(value) for value in values if value not in (None, "")]
        if not numeric:
            return 0.0
        return sum(numeric) / len(numeric)

    @staticmethod
    def _success_rate(actions: list[dict[str, Any]]) -> float:
        completed = len([action for action in actions if action.get("execution_status") == WorkflowExecutionService.STATUS_COMPLETED])
        failed = len(
            [
                action
                for action in actions
                if action.get("execution_status") in {WorkflowExecutionService.STATUS_FAILED, WorkflowExecutionService.STATUS_EXECUTION_FAILED}
            ]
        )
        total = completed + failed
        return round((completed / total) * 100, 1) if total else 0.0

    @staticmethod
    def _status_percent(actions: list[dict[str, Any]], status: str) -> float:
        if not actions:
            return 0.0
        count = len([action for action in actions if action.get("execution_status") == status])
        return round((count / len(actions)) * 100, 1)

    @staticmethod
    def _illegal_transition(from_status: str, to_status: str) -> dict[str, Any]:
        return {
            "status": "FAILED",
            "message": f"Illegal workflow transition: {from_status} -> {to_status}",
            "from_status": from_status,
            "to_status": to_status,
        }

    @staticmethod
    def _not_found() -> dict[str, Any]:
        return {"status": "FAILED", "message": "Action not found"}

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _today() -> str:
        return datetime.now(timezone.utc).date().isoformat()
