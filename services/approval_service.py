"""
Enterprise Approval Workflow Service
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from repositories.approval_repository import ApprovalRepository


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
