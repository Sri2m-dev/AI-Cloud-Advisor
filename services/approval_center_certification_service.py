from __future__ import annotations

from datetime import datetime
from typing import Any


APPROVAL_COLUMNS = [
    "id",
    "request_type",
    "title",
    "description",
    "status",
    "priority",
    "workflow_stage",
    "current_approver_role",
    "workflow_status",
    "created_at",
]


class ApprovalCenterCertificationService:
    """Certification metadata service for Approval Center."""

    @staticmethod
    def count_due_today(approvals: list[dict[str, Any]]) -> int:
        today = datetime.utcnow().date()
        due_today = 0

        for approval in approvals:
            if str(approval.get("status", "")).upper() != "PENDING":
                continue

            due_date = approval.get("due_date")
            if not due_date:
                continue

            try:
                due_dt = datetime.fromisoformat(str(due_date).replace("Z", "+00:00"))
            except Exception:
                continue

            if due_dt.date() == today:
                due_today += 1

        return due_today

    @staticmethod
    def visible_columns(rows: list[dict[str, Any]]) -> list[str]:
        if not rows:
            return []
        columns = set()
        for row in rows:
            columns.update(row.keys())
        return [column for column in APPROVAL_COLUMNS if column in columns]

    @staticmethod
    def get_dashboard(
        *,
        metrics: dict[str, Any],
        stage_metrics: dict[str, Any],
        overdue_approvals: list[dict[str, Any]],
        sla: dict[str, Any],
        approval_register: list[dict[str, Any]],
        pending: list[dict[str, Any]],
        current_role: str,
    ) -> dict[str, Any]:
        overdue_count = len(overdue_approvals)
        due_today_count = ApprovalCenterCertificationService.count_due_today(approval_register)
        sla_value = sla.get("sla_compliance_percent", sla.get("sla_compliance", 100))
        pending_count = metrics.get("pending", 0)

        return {
            "overdue_count": overdue_count,
            "due_today_count": due_today_count,
            "sla_value": sla_value,
            "executive_summary": ApprovalCenterCertificationService._executive_summary(
                pending_count=pending_count,
                overdue_count=overdue_count,
                due_today_count=due_today_count,
                sla_value=sla_value,
                current_role=current_role,
            ),
            "evidence": ApprovalCenterCertificationService._evidence(
                metrics=metrics,
                stage_metrics=stage_metrics,
                overdue_count=overdue_count,
                due_today_count=due_today_count,
                sla_value=sla_value,
                approval_register=approval_register,
                pending=pending,
                current_role=current_role,
            ),
        }

    @staticmethod
    def _executive_summary(
        *,
        pending_count: int,
        overdue_count: int,
        due_today_count: int,
        sla_value: Any,
        current_role: str,
    ) -> str:
        if pending_count:
            posture = f"{pending_count} approval request(s) are pending for review."
        else:
            posture = "There are no pending approval requests requiring immediate action."

        risk_sentence = (
            f"{overdue_count} approval request(s) are overdue and {due_today_count} are due today."
            if overdue_count or due_today_count
            else "No overdue approvals or same-day approval deadlines are currently visible."
        )

        sentences = [
            posture,
            risk_sentence,
            f"SLA compliance is {sla_value}, and the current role context is {current_role or 'unknown'}.",
            "Approval decisions remain service-backed through the approval repository and workflow service.",
        ]
        return " ".join(sentences)

    @staticmethod
    def _evidence(
        *,
        metrics: dict[str, Any],
        stage_metrics: dict[str, Any],
        overdue_count: int,
        due_today_count: int,
        sla_value: Any,
        approval_register: list[dict[str, Any]],
        pending: list[dict[str, Any]],
        current_role: str,
    ) -> dict[str, Any]:
        total = int(metrics.get("total", len(approval_register)) or 0)
        pending_count = int(metrics.get("pending", len(pending)) or 0)
        coverage = round((total / max(total, 1)) * 100, 1) if total else 0.0

        return {
            "source_data": [
                {"Section": "Approval Metrics", "Source": "ApprovalService.get_dashboard_metrics", "Mode": "Service"},
                {"Section": "Workflow Stages", "Source": "ApprovalService.get_workflow_stage_metrics", "Mode": "Service"},
                {"Section": "Pending Approvals", "Source": "ApprovalService.get_pending_approvals", "Mode": "Service"},
                {"Section": "Approval Register", "Source": "ApprovalService.get_all_approvals", "Mode": "Service"},
                {"Section": "SLA", "Source": "ApprovalService.get_sla_metrics", "Mode": "Service"},
            ],
            "data_coverage": [
                {"Coverage Area": "Approval Register", "Value": f"{coverage:.1f}%", "Status": "Tracked" if total else "No Records"},
                {"Coverage Area": "Pending Approvals", "Value": str(pending_count), "Status": "Action Required" if pending_count else "Clear"},
                {"Coverage Area": "Overdue Approvals", "Value": str(overdue_count), "Status": "Review" if overdue_count else "Clear"},
                {"Coverage Area": "Due Today", "Value": str(due_today_count), "Status": "Watch" if due_today_count else "Clear"},
            ],
            "ai_interpretation": (
                "Approval Center is service-backed and ready for executive governance review. "
                "The primary operational signal is the pending approval queue, supported by SLA, overdue, and workflow-stage evidence."
            ),
            "raw_evidence": {
                "Approval Metrics": [
                    {"Metric": "Pending", "Value": metrics.get("pending", 0)},
                    {"Metric": "Approved", "Value": metrics.get("approved", 0)},
                    {"Metric": "Rejected", "Value": metrics.get("rejected", 0)},
                    {"Metric": "Total", "Value": metrics.get("total", total)},
                    {"Metric": "SLA Compliance", "Value": sla_value},
                    {"Metric": "Current Role", "Value": current_role or "unknown"},
                ],
                "Workflow Stages": [
                    {"Stage": str(stage).upper(), "Count": value}
                    for stage, value in stage_metrics.items()
                ],
            },
        }
