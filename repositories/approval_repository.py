"""
Approval Repository
Enterprise approval workflow data access layer.
"""

from __future__ import annotations

from datetime import datetime, timezone

from services.supabase_client import supabase


ROLE_MAPPING = {
    "executive": "ceo",
    "cio": "cio",
    "finance": "finance",
    "technical": "technical",
}


WORKFLOW_STAGES = {
    "FINANCE": {
        "next_stage": "CIO",
        "next_role": "cio",
    },
    "CIO": {
        "next_stage": "CEO",
        "next_role": ROLE_MAPPING["executive"],
    },
    "CEO": {
        "next_stage": "APPROVED",
        "next_role": None,
    },
}


COMPLETED_STATUSES = {
    "APPROVED",
    "REJECTED",
    "COMPLETED",
    "CLOSED",
}


def _parse_datetime(value):
    if not value:
        return None

    try:
        parsed = datetime.fromisoformat(
            str(value).replace("Z", "+00:00")
        )
    except Exception:
        return None

    if parsed.tzinfo:
        parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)

    return parsed


def _completion_datetime(approval):
    for key in (
        "completed_at",
        "approved_at",
        "rejected_at",
    ):
        parsed = _parse_datetime(approval.get(key))
        if parsed:
            return parsed

    return None


class ApprovalRepository:

    @staticmethod
    def get_pending_approvals(role: str | None = None):
        query = (
            supabase.table("approval_requests")
            .select("*")
            .eq("status", "PENDING")
        )

        if role:
            role_key = role.lower()

            role_filters = {
                "executive": ["ceo", "CEO", "executive"],
                "ceo": ["ceo", "CEO", "executive"],
                "cio": ["cio", "CIO"],
                "finance": ["finance", "FINANCE"],
                "technical": ["technical", "TECHNICAL"],
            }

            allowed_roles = role_filters.get(
                role_key,
                [role_key, role_key.upper()]
            )

            query = query.in_(
                "current_approver_role",
                allowed_roles
            )

        response = (
            query
            .order("created_at", desc=True)
            .execute()
        )

        return response.data or []

    @staticmethod
    def get_all_approvals():
        response = (
            supabase.table("approval_requests")
            .select("*")
            .order("created_at", desc=True)
            .execute()
        )
        return response.data or []

    @staticmethod
    def get_overdue_approvals():
        approvals = ApprovalRepository.get_all_approvals()

        now = datetime.utcnow()
        overdue = []

        for approval in approvals:
            if str(approval.get("status", "")).upper() != "PENDING":
                continue

            due_date = approval.get("due_date")
            if not due_date:
                continue

            due_dt = _parse_datetime(due_date)
            if due_dt and due_dt < now:
                overdue.append(approval)

        return overdue

    @staticmethod
    def get_sla_metrics():
        approvals = ApprovalRepository.get_all_approvals()
        now = datetime.utcnow()

        completed_within_sla = 0
        breached_sla = 0
        pending_overdue = 0
        unknown_sla = 0

        for approval in approvals:
            status = str(
                approval.get("status", "")
            ).upper()
            due_dt = _parse_datetime(
                approval.get("due_date")
            )

            if not due_dt:
                unknown_sla += 1
                continue

            if status == "PENDING":
                if due_dt < now:
                    pending_overdue += 1
                    breached_sla += 1
                else:
                    unknown_sla += 1
                continue

            if status in COMPLETED_STATUSES:
                completed_dt = _completion_datetime(approval)

                if not completed_dt:
                    unknown_sla += 1
                    continue

                if completed_dt <= due_dt:
                    completed_within_sla += 1
                else:
                    breached_sla += 1
                continue

            if due_dt < now:
                breached_sla += 1
            else:
                unknown_sla += 1

        measured = completed_within_sla + breached_sla
        compliance = (
            round((completed_within_sla / measured) * 100, 2)
            if measured
            else 100
        )

        return {
            "total_requests": len(approvals),
            "completed_within_sla": completed_within_sla,
            "breached_sla": breached_sla,
            "pending_overdue": pending_overdue,
            "unknown_sla": unknown_sla,
            "sla_compliance_percent": compliance,
            "sla_compliance": compliance,
        }

    @staticmethod
    def get_approval_by_id(approval_id: int):
        response = (
            supabase.table("approval_requests")
            .select("*")
            .eq("id", approval_id)
            .limit(1)
            .execute()
        )

        if response.data:
            return response.data[0]

        return None

    @staticmethod
    def get_approval_history(approval_id: int):
        response = (
            supabase.table("approval_history")
            .select("*")
            .eq("approval_request_id", approval_id)
            .order("created_at", desc=False)
            .execute()
        )
        return response.data or []

    @staticmethod
    def approve_request(
        approval_id: int,
        approver_id: int,
        comments: str = "",
    ):
        request = ApprovalRepository.get_approval_by_id(
            approval_id
        )

        if not request:
            return None

        current_stage = (
            request.get("workflow_stage")
            or "FINANCE"
        ).upper()

        next_step = WORKFLOW_STAGES.get(
            current_stage
        )

        if not next_step:
            return None

        # --------------------------------------------------
        # FINAL APPROVAL
        # --------------------------------------------------

        if next_step["next_stage"] == "APPROVED":

            update_payload = {
                "status": "APPROVED",
                "workflow_status": "APPROVED",
                "workflow_stage": "APPROVED",
                "approved_by": approver_id,
                "approved_at": datetime.utcnow().isoformat(),
                "comments": comments,
            }

        # --------------------------------------------------
        # MOVE TO NEXT STAGE
        # --------------------------------------------------

        else:

            update_payload = {
                "status": "PENDING",
                "workflow_status": "PENDING",
                "workflow_stage": next_step["next_stage"],
                "current_approver_role": next_step["next_role"],
                "comments": comments,
            }

        response = (
            supabase.table("approval_requests")
            .update(update_payload)
            .eq("id", approval_id)
            .execute()
        )

        # --------------------------------------------------
        # AUDIT HISTORY
        # --------------------------------------------------

        supabase.table("approval_history").insert(
            {
                "approval_request_id": approval_id,
                "action": "APPROVE",
                "from_stage": current_stage,
                "to_stage": next_step["next_stage"],
                "actor_id": str(approver_id),
                "actor_role": request.get(
                    "current_approver_role",
                    ""
                ),
                "comments": comments,
            }
        ).execute()

        return response.data

    @staticmethod
    def reject_request(
        approval_id: int,
        approver_id: int,
        comments: str = "",
    ):
        request = ApprovalRepository.get_approval_by_id(
            approval_id
        )

        if not request:
            return None

        current_stage = (
            request.get("workflow_stage")
            or "FINANCE"
        ).upper()

        response = (
            supabase.table("approval_requests")
            .update(
                {
                    "status": "REJECTED",
                    "workflow_status": "REJECTED",
                    "workflow_stage": "REJECTED",
                    "rejected_by": approver_id,
                    "comments": comments,
                }
            )
            .eq("id", approval_id)
            .execute()
        )

        supabase.table("approval_history").insert(
            {
                "approval_request_id": approval_id,
                "action": "REJECT",
                "from_stage": current_stage,
                "to_stage": "REJECTED",
                "actor_id": str(approver_id),
                "actor_role": request.get(
                    "current_approver_role",
                    ""
                ),
                "comments": comments,
            }
        ).execute()

        return response.data

    @staticmethod
    def escalate_request(
        approval_id: int,
        escalated_to: int,
        comments: str = "",
    ):
        request = ApprovalRepository.get_approval_by_id(
            approval_id
        )

        if not request:
            return None

        current_stage = (
            request.get("workflow_stage")
            or "FINANCE"
        ).upper()

        response = (
            supabase.table("approval_requests")
            .update(
                {
                    "status": "ESCALATED",
                    "workflow_status": "ESCALATED",
                    "escalated_to": escalated_to,
                    "comments": comments,
                }
            )
            .eq("id", approval_id)
            .execute()
        )

        supabase.table("approval_history").insert(
            {
                "approval_request_id": approval_id,
                "action": "ESCALATE",
                "from_stage": current_stage,
                "to_stage": "ESCALATED",
                "actor_id": str(escalated_to),
                "actor_role": request.get(
                    "current_approver_role",
                    ""
                ),
                "comments": comments,
            }
        ).execute()

        return response.data

    @staticmethod
    def approval_metrics():
        approvals = ApprovalRepository.get_all_approvals()

        pending = len(
            [a for a in approvals if a.get("status") == "PENDING"]
        )

        approved = len(
            [a for a in approvals if a.get("status") == "APPROVED"]
        )

        rejected = len(
            [a for a in approvals if a.get("status") == "REJECTED"]
        )

        escalated = len(
            [a for a in approvals if a.get("status") == "ESCALATED"]
        )

        return {
            "pending": pending,
            "approved": approved,
            "rejected": rejected,
            "escalated": escalated,
            "total": len(approvals),
        }

    @staticmethod
    def workflow_stage_metrics():

        approvals = ApprovalRepository.get_all_approvals()

        return {
            "pmo": len(
                [
                    a for a in approvals
                    if str(a.get("workflow_stage", "")).upper() == "PMO"
                    and str(a.get("status", "")).upper() == "PENDING"
                ]
            ),
            "finance": len(
                [
                    a for a in approvals
                    if str(a.get("workflow_stage", "")).upper() == "FINANCE"
                    and str(a.get("status", "")).upper() == "PENDING"
                ]
            ),
            "cio": len(
                [
                    a for a in approvals
                    if str(a.get("workflow_stage", "")).upper() == "CIO"
                    and str(a.get("status", "")).upper() == "PENDING"
                ]
            ),
            "ceo": len(
                [
                    a for a in approvals
                    if str(a.get("workflow_stage", "")).upper() == "CEO"
                    and str(a.get("status", "")).upper() == "PENDING"
                ]
            ),
            "completed": len(
                [
                    a for a in approvals
                    if str(a.get("status", "")).upper() == "APPROVED"
                ]
            ),
        }
