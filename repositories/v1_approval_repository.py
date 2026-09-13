"""Approval Center compatibility adapter over NEXORA_V1_APPROVAL_AUTHORITY."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from auth.authenticated_tenant import AuthenticatedTenantContext
from services.v1_approval_authority import ApprovalAuthorityError, SupabaseApprovalAuthority


class V1ApprovalRepository:
    def __init__(self, authority: SupabaseApprovalAuthority) -> None:
        self.authority = authority

    def list_requests(self, context: AuthenticatedTenantContext, role: str | None = None):
        rows = [_row(request) for request in self.authority.list_requests(context)]
        if role:
            roles = {"executive": "ceo", "cio": "cio", "finance": "finance", "technical": "technical"}
            wanted = roles.get(role.lower(), role.lower())
            rows = [row for row in rows if row["current_approver_role"] == wanted]
        return [row for row in rows if row["status"] in {"PENDING", "ESCALATED"}]

    def all_requests(self, context: AuthenticatedTenantContext):
        return [_row(request) for request in self.authority.list_requests(context)]

    def get_request(self, context: AuthenticatedTenantContext, approval_id: int | str):
        request_id = self._request_id(context, approval_id)
        request = self.authority.get_request(context, request_id)
        return _row(request) if request else None

    def get_history(self, context: AuthenticatedTenantContext, approval_id: int | str):
        request_id = self._request_id(context, approval_id)
        return [_history_row(item) for item in self.authority.get_history(context, request_id)]

    def transition(self, context, approval_id, *, target, actor, reason, actor_role=None, escalated_to=None):
        request_id = self._request_id(context, approval_id)
        request = self.authority.transition_request(
            context, request_id, to_state=target, actor=actor, actor_role=actor_role,
            escalated_to=escalated_to, reason=reason,
        )
        return [_row(request)]

    def _request_id(self, context, approval_id):
        if isinstance(approval_id, str) and not approval_id.isdigit():
            return approval_id
        for request in self.authority.list_requests(context):
            if request.compatibility_id == int(approval_id):
                return request.request_id
        raise ApprovalAuthorityError("approval request not found")


def _row(request):
    if request is None:
        return {}
    timestamp = request.decision_at or request.created_at
    return {
        "id": request.compatibility_id,
        "request_id": request.request_id,
        "organization_id": request.organization_id,
        "tenant_id": request.tenant_id,
        "subject_id": request.subject_id,
        "requested_action": request.requested_action,
        "status": request.state,
        "workflow_status": request.state,
        "workflow_stage": request.workflow_stage,
        "current_approver_role": request.current_approver_role,
        "requesting_actor": request.requesting_actor,
        "decision_actor": request.decision_actor,
        "comments": request.reason,
        "created_at": request.created_at.isoformat(),
        "approved_at": timestamp.isoformat() if request.state == "APPROVED" else None,
        "rejected_at": timestamp.isoformat() if request.state == "REJECTED" else None,
        "completed_at": timestamp.isoformat() if request.state == "COMPLETED" else None,
        "escalated_to": request.escalated_to,
    }


def _history_row(item):
    return {
        "id": item.history_id,
        "request_id": item.request_id,
        "approval_request_id": item.request_id,
        "action": item.action,
        "from_stage": item.from_state,
        "to_stage": item.to_state,
        "actor_id": item.actor,
        "actor_role": item.actor_role,
        "comments": item.reason,
        "created_at": item.occurred_at.isoformat(),
    }
