"""
Enterprise Approval Workflow Service
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from core.permissions.decorators import PermissionDenied
from core.permissions.permission_matrix import has_permission
from core.workflows.sla_engine import SLAEngine
from repositories.approval_repository import ApprovalRepository
from repositories.v1_approval_repository import V1ApprovalRepository
from services.enterprise_spend_composition import authenticated_tenant_context
from services.supabase_client import supabase
from services.v1_approval_authority import SupabaseApprovalAuthority

_V1_APPROVAL_REPOSITORY = V1ApprovalRepository(SupabaseApprovalAuthority(supabase))


def _approval_context():
    import streamlit as st

    return authenticated_tenant_context(st.session_state)


@dataclass(frozen=True)
class SLAStatusResult:
    """Compatibility result returned by the approval SLA service API."""

    success: bool
    data: str | None = None
    message: str = ""
    errors: tuple[str, ...] = ()


def calculate_sla_status(
    approval: dict[str, Any] | None,
    now: datetime | None = None,
) -> SLAStatusResult:
    """Calculate an approval's SLA status using the canonical workflow engine."""

    if not isinstance(approval, dict):
        return SLAStatusResult(
            success=False,
            message="Approval must be a mapping",
            errors=("invalid_approval",),
        )

    created_at = approval.get("created_at")
    if created_at is None or not str(created_at).strip():
        return SLAStatusResult(
            success=False,
            message="Approval created_at is required",
            errors=("missing_created_at",),
        )

    try:
        status = SLAEngine.detect_breach(approval, now)
    except (TypeError, ValueError) as exc:
        return SLAStatusResult(
            success=False,
            message=f"Invalid approval created_at: {exc}",
            errors=("invalid_created_at",),
        )

    return SLAStatusResult(success=True, data=status.upper())


@dataclass(frozen=True)
class ApprovalActionResult:
    """Result shape retained for the module-level approval action API."""

    success: bool
    data: dict[str, str]


def _approval_action_result(
    approval_id: str,
    action: str,
    user_role: str | None,
) -> ApprovalActionResult:
    if not user_role or not has_permission(user_role, action):
        raise PermissionDenied(f"Role '{user_role}' lacks permission for '{action}'")

    # A role check and random trace ID are not a committed approval decision.
    from auth.authenticated_tenant import require_protected_workflow

    require_protected_workflow("approval_compatibility_action")


def approve_request(
    approval_id: str,
    approved_by: str,
    *,
    user_role: str | None = None,
) -> ApprovalActionResult:
    """Retain the established module-level RBAC approval entry point."""

    del approved_by
    return _approval_action_result(approval_id, "approve_request", user_role)


def reject_request(
    approval_id: str,
    rejected_by: str,
    *,
    user_role: str | None = None,
) -> ApprovalActionResult:
    """Retain the established module-level RBAC rejection entry point."""

    del rejected_by
    return _approval_action_result(approval_id, "reject_request", user_role)


class ApprovalService:
    @staticmethod
    def _safe_read(method, fallback):
        try:
            return method()
        except RuntimeError as exc:
            if "SUPABASE_" not in str(exc):
                raise
            return fallback

    @staticmethod
    def get_dashboard_metrics() -> dict[str, Any]:
        rows = ApprovalService.get_all_approvals()
        return {
            "pending": sum(row.get("status") == "PENDING" for row in rows),
            "approved": sum(row.get("status") == "APPROVED" for row in rows),
            "rejected": sum(row.get("status") == "REJECTED" for row in rows),
            "escalated": sum(row.get("status") == "ESCALATED" for row in rows),
            "total": len(rows),
        }

    @staticmethod
    def get_workflow_stage_metrics():
        rows = ApprovalService.get_all_approvals()
        return {
            stage.lower(): sum(
                row.get("workflow_stage") == stage and row.get("status") == "PENDING"
                for row in rows
            )
            for stage in ("FINANCE", "CIO", "CEO")
        } | {"pmo": 0, "completed": sum(row.get("status") == "COMPLETED" for row in rows)}

    @staticmethod
    def get_overdue_approvals():
        return []

    @staticmethod
    def get_pending_approvals(role: str | None = None):
        try:
            return _V1_APPROVAL_REPOSITORY.list_requests(_approval_context(), role)
        except Exception:
            return []

    @staticmethod
    def get_all_approvals():
        try:
            return _V1_APPROVAL_REPOSITORY.all_requests(_approval_context())
        except Exception:
            return []

    @staticmethod
    def get_approval_details(approval_id: int):
        try:
            return _V1_APPROVAL_REPOSITORY.get_request(_approval_context(), approval_id)
        except Exception:
            return None

    @staticmethod
    def get_approval_history(approval_id: int):
        try:
            return _V1_APPROVAL_REPOSITORY.get_history(_approval_context(), approval_id)
        except Exception:
            return []

    @staticmethod
    def approve_request(
        approval_id: int,
        approver_id: int,
        comments: str = "",
    ):
        context = _approval_context()
        return _V1_APPROVAL_REPOSITORY.transition(
            context,
            approval_id,
            target="APPROVED",
            actor=context.user_id,
            reason=comments,
            actor_role=context.role,
        )

    @staticmethod
    def reject_request(
        approval_id: int,
        approver_id: int,
        comments: str = "",
    ):
        context = _approval_context()
        return _V1_APPROVAL_REPOSITORY.transition(
            context,
            approval_id,
            target="REJECTED",
            actor=context.user_id,
            reason=comments,
            actor_role=context.role,
        )

    @staticmethod
    def escalate_request(
        approval_id: int,
        escalated_to: int,
        comments: str = "",
    ):
        context = _approval_context()
        return _V1_APPROVAL_REPOSITORY.transition(
            context,
            approval_id,
            target="ESCALATED",
            actor=context.user_id,
            actor_role=context.role,
            escalated_to=str(escalated_to),
            reason=comments,
        )

    @staticmethod
    def get_sla_metrics():
        # The canonical v1 authority has no deadline/policy binding. Escalation
        # aging thresholds are not a completion SLA and must not be substituted.
        result = {
            "status": "UNKNOWN",
            "total_requests": None,
            "completed_within_sla": None,
            "breached_sla": None,
            "pending_overdue": None,
            "pending_within_sla": None,
            "unknown_sla": None,
            "measured_requests": 0,
            "sla_compliance_percent": None,
            "sla_compliance": None,
            "reason": (
                "Canonical v1 approvals have no authoritative deadline or SLA policy binding "
                "defining the measurement clock, eligible states and completion event. "
                "created_at and decision_at alone cannot establish compliance."
            ),
        }
        try:
            requests = _V1_APPROVAL_REPOSITORY.sla_requests(_approval_context())
        except Exception:
            result.update(
                status="NOT_AVAILABLE",
                measured_requests=None,
                reason="Authenticated canonical approval SLA evidence could not be read.",
            )
            return result
        result.update(total_requests=len(requests), unknown_sla=len(requests))
        if not requests:
            result["reason"] = "No approvals: SLA compliance has no measured population."
        return result

    @staticmethod
    def workflow_summary():
        metrics = ApprovalRepository.approval_metrics()
        sla = ApprovalService.get_sla_metrics()

        return {
            "metrics": metrics,
            "sla": sla,
            "generated_at": datetime.utcnow().isoformat(),
        }
