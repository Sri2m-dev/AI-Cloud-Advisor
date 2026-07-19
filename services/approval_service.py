"""
Enterprise Approval Workflow Service
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import uuid4

from core.permissions.decorators import PermissionDenied
from core.permissions.permission_matrix import has_permission
from core.workflows.sla_engine import SLAEngine
from repositories.approval_repository import ApprovalRepository


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

    return ApprovalActionResult(
        success=True,
        data={"trace_id": str(uuid4()), "request_id": str(approval_id)},
    )


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
    def get_dashboard_metrics() -> dict[str, Any]:
        return ApprovalRepository.approval_metrics()

    @staticmethod
    def get_workflow_stage_metrics():
        return ApprovalRepository.workflow_stage_metrics()

    @staticmethod
    def get_overdue_approvals():
        return ApprovalRepository.get_overdue_approvals()

    @staticmethod
    def get_pending_approvals(role: str | None = None):
        return ApprovalRepository.get_pending_approvals(role)

    @staticmethod
    def get_all_approvals():
        return ApprovalRepository.get_all_approvals()

    @staticmethod
    def get_approval_details(approval_id: int):
        return ApprovalRepository.get_approval_by_id(approval_id)

    @staticmethod
    def get_approval_history(approval_id: int):
        return ApprovalRepository.get_approval_history(approval_id)

    @staticmethod
    def approve_request(
        approval_id: int,
        approver_id: int,
        comments: str = "",
    ):
        return ApprovalRepository.approve_request(
            approval_id=approval_id,
            approver_id=approver_id,
            comments=comments,
        )

    @staticmethod
    def reject_request(
        approval_id: int,
        approver_id: int,
        comments: str = "",
    ):
        return ApprovalRepository.reject_request(
            approval_id=approval_id,
            approver_id=approver_id,
            comments=comments,
        )

    @staticmethod
    def escalate_request(
        approval_id: int,
        escalated_to: int,
        comments: str = "",
    ):
        return ApprovalRepository.escalate_request(
            approval_id=approval_id,
            escalated_to=escalated_to,
            comments=comments,
        )

    @staticmethod
    def get_sla_metrics():
        return ApprovalRepository.get_sla_metrics()

    @staticmethod
    def workflow_summary():

        metrics = ApprovalRepository.approval_metrics()
        sla = ApprovalService.get_sla_metrics()

        return {
            "metrics": metrics,
            "sla": sla,
            "generated_at": datetime.utcnow().isoformat(),
        }
