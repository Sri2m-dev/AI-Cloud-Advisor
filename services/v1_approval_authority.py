"""Tenant-scoped v1 approval authority for the RC-001 runtime boundary."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timezone
from typing import Any, Mapping, Protocol
from uuid import uuid4

from data_fabric.foundation import TenantContext


class ApprovalAuthorityError(ValueError):
    """Raised when a v1 approval operation violates its contract."""


ALLOWED_TRANSITIONS = {
    "PENDING": frozenset({"PENDING", "APPROVED", "REJECTED", "ESCALATED"}),
    "ESCALATED": frozenset({"PENDING", "REJECTED"}),
    "APPROVED": frozenset({"COMPLETED", "CLOSED"}),
    "REJECTED": frozenset({"CLOSED"}),
    "COMPLETED": frozenset({"CLOSED"}),
    "CLOSED": frozenset(),
}
STAGE_ROLES = {"FINANCE": "finance", "CIO": "cio", "CEO": "ceo"}
STAGE_ORDER = ("FINANCE", "CIO", "CEO")


@dataclass(frozen=True, slots=True)
class ApprovalRequest:
    request_id: str
    organization_id: str
    tenant_id: str
    subject_id: str
    requested_action: str
    state: str
    requesting_actor: str
    reason: str
    created_at: datetime
    decision_actor: str | None = None
    decision_at: datetime | None = None
    workflow_stage: str = "FINANCE"
    current_approver_role: str = "finance"
    compatibility_id: int | None = None
    escalated_to: str | None = None

    def __post_init__(self) -> None:
        if not self.request_id or not self.subject_id or not self.requested_action:
            raise ApprovalAuthorityError("approval identity and requested action are required")
        if self.state not in ALLOWED_TRANSITIONS and self.state != "PENDING":
            raise ApprovalAuthorityError(f"unsupported approval state: {self.state}")
        if self.workflow_stage not in STAGE_ROLES:
            raise ApprovalAuthorityError(f"unsupported workflow stage: {self.workflow_stage}")
        if self.current_approver_role != STAGE_ROLES[self.workflow_stage]:
            raise ApprovalAuthorityError("approver role does not match workflow stage")


@dataclass(frozen=True, slots=True)
class ApprovalHistory:
    history_id: str
    request_id: str
    organization_id: str
    tenant_id: str
    from_state: str
    to_state: str
    actor: str
    reason: str
    occurred_at: datetime
    action: str = "TRANSITION"
    actor_role: str | None = None


def transition_approval_request(
    current: ApprovalRequest,
    *,
    to_state: str,
    actor: str,
    reason: str,
    actor_role: str | None = None,
    escalated_to: str | None = None,
    now: datetime | None = None,
) -> tuple[ApprovalRequest, ApprovalHistory]:
    """Apply the canonical customer approval transition without persistence."""
    target = str(to_state).upper()
    workflow_stage = current.workflow_stage
    if target == "APPROVED" and current.workflow_stage != "CEO":
        workflow_stage = STAGE_ORDER[STAGE_ORDER.index(current.workflow_stage) + 1]
        target = "PENDING"
    if target not in ALLOWED_TRANSITIONS.get(current.state, frozenset()):
        raise ApprovalAuthorityError(
            f"invalid approval transition: {current.state} -> {target}"
        )
    occurred_at = now or datetime.now(timezone.utc)
    updated = replace(
        current,
        state=target,
        decision_actor=actor,
        decision_at=occurred_at,
        workflow_stage=workflow_stage,
        current_approver_role=STAGE_ROLES[workflow_stage],
        escalated_to=escalated_to if target == "ESCALATED" else None,
    )
    history = ApprovalHistory(
        history_id=str(uuid4()),
        request_id=current.request_id,
        organization_id=current.organization_id,
        tenant_id=current.tenant_id,
        from_state=current.state,
        to_state=target,
        actor=actor,
        reason=reason,
        occurred_at=occurred_at,
        action="ESCALATE" if target == "ESCALATED" else "TRANSITION",
        actor_role=actor_role,
    )
    return updated, history


class ApprovalAuthority(Protocol):
    def create_request(
        self, context: TenantContext, *, subject_id: str, requested_action: str,
        requesting_actor: str, reason: str, request_id: str | None = None,
        workflow_stage: str = "FINANCE",
    ) -> ApprovalRequest: ...

    def get_request(self, context: TenantContext, request_id: str) -> ApprovalRequest | None: ...

    def list_requests(self, context: TenantContext) -> tuple[ApprovalRequest, ...]: ...

    def transition_request(
        self, context: TenantContext, request_id: str, *, to_state: str,
        actor: str, reason: str,
    ) -> ApprovalRequest: ...

    def get_history(
        self, context: TenantContext, request_id: str
    ) -> tuple[ApprovalHistory, ...]: ...


class InMemoryApprovalAuthority:
    """Deterministic reference authority used by local/runtime contract tests."""

    def __init__(self) -> None:
        self._requests: dict[tuple[str, str, str], ApprovalRequest] = {}
        self._history: dict[tuple[str, str, str], list[ApprovalHistory]] = {}

    def create_request(
        self, context: TenantContext, *, subject_id: str, requested_action: str,
        requesting_actor: str, reason: str, request_id: str | None = None,
        workflow_stage: str = "FINANCE",
    ) -> ApprovalRequest:
        request = ApprovalRequest(
            request_id=request_id or str(uuid4()),
            organization_id=context.organization_id,
            tenant_id=context.tenant_id,
            subject_id=subject_id,
            requested_action=requested_action,
            state="PENDING",
            requesting_actor=requesting_actor,
            reason=reason,
            created_at=datetime.now(timezone.utc),
            workflow_stage=workflow_stage,
            current_approver_role=STAGE_ROLES[workflow_stage],
            compatibility_id=self._next_compatibility_id(context),
        )
        key = self._key(context, request.request_id)
        if key in self._requests:
            raise ApprovalAuthorityError("approval request already exists")
        self._requests[key] = request
        self._history[key] = []
        return request

    def get_request(self, context: TenantContext, request_id: str) -> ApprovalRequest | None:
        return self._requests.get(self._key(context, request_id))

    def list_requests(self, context: TenantContext) -> tuple[ApprovalRequest, ...]:
        prefix = (context.organization_id, context.tenant_id)
        return tuple(
            request for key, request in self._requests.items()
            if key[:2] == prefix
        )

    def transition_request(
        self, context: TenantContext, request_id: str, *, to_state: str,
        actor: str, reason: str, actor_role: str | None = None,
        escalated_to: str | None = None,
    ) -> ApprovalRequest:
        key = self._key(context, request_id)
        current = self._requests.get(key)
        if current is None:
            raise ApprovalAuthorityError("approval request not found")
        updated, history = transition_approval_request(
            current,
            to_state=to_state,
            actor=actor,
            reason=reason,
            actor_role=actor_role,
            escalated_to=escalated_to,
        )
        self._requests[key] = updated
        self._history[key].append(history)
        return updated

    def get_history(self, context: TenantContext, request_id: str) -> tuple[ApprovalHistory, ...]:
        return tuple(self._history.get(self._key(context, request_id), ()))

    @staticmethod
    def _key(context: TenantContext, request_id: str) -> tuple[str, str, str]:
        if not request_id:
            raise ApprovalAuthorityError("request_id is required")
        return context.organization_id, context.tenant_id, request_id

    def _next_compatibility_id(self, context: TenantContext) -> int:
        return 1 + max(
            (request.compatibility_id or 0 for key, request in self._requests.items()
             if key[:2] == (context.organization_id, context.tenant_id)),
            default=0,
        )


class SupabaseApprovalAuthority:
    """Read-only scoped adapter until an approved atomic decision RPC exists."""

    def __init__(self, client: Any) -> None:
        self._client = client

    @staticmethod
    def _context(context):
        from auth.authenticated_tenant import AuthenticatedTenantContext

        if not isinstance(context, AuthenticatedTenantContext):
            raise PermissionError("Authenticated tenant context is required")
        return context

    @staticmethod
    def _checked(context, row, request_id=None):
        if (str(row.get("organization_id")), str(row.get("tenant_id"))) != (
                context.organization_id, context.tenant_id):
            raise PermissionError("Approval response crossed tenant boundary")
        if request_id is not None and str(row.get("request_id")) != str(request_id):
            raise PermissionError("Approval response crossed request boundary")
        return row

    def create_request(self, context, *, subject_id, requested_action, requesting_actor,
                       reason, request_id=None, workflow_stage="FINANCE"):
        from auth.authenticated_tenant import require_protected_workflow

        context = self._context(context)
        require_protected_workflow("approval_submission", context, actor=requesting_actor)

    def transition_request(self, context, request_id, *, to_state, actor, reason,
                           actor_role=None, escalated_to=None):
        from auth.authenticated_tenant import require_protected_workflow

        context = self._context(context)
        require_protected_workflow("approval_decision", context, actor=actor)

    def get_request(self, context, request_id):
        context = self._context(context)
        rows = (self._client.table("nexora_v1_approval_requests").select("*")
                .eq("organization_id",context.organization_id).eq("tenant_id",context.tenant_id)
                .eq("request_id",request_id).limit(1).execute().data or [])
        return _request_from_row(self._checked(context,rows[0],request_id)) if rows else None

    def list_requests(self, context):
        context = self._context(context)
        rows = (self._client.table("nexora_v1_approval_requests").select("*")
                .eq("organization_id",context.organization_id).eq("tenant_id",context.tenant_id)
                .order("created_at",desc=True).execute().data or [])
        return tuple(_request_from_row(self._checked(context,row)) for row in rows)

    def get_history(self, context, request_id):
        context = self._context(context)
        rows = (self._client.table("nexora_v1_approval_history").select("*")
                .eq("organization_id",context.organization_id).eq("tenant_id",context.tenant_id)
                .eq("request_id",request_id).order("occurred_at").execute().data or [])
        return tuple(ApprovalHistory(**(self._checked(context,row,request_id) |
                     {"occurred_at":_timestamp(row["occurred_at"])})) for row in rows)


def _request_from_row(row: Mapping[str, Any]) -> ApprovalRequest:
    return ApprovalRequest(
        request_id=str(row["request_id"]),
        organization_id=str(row["organization_id"]),
        tenant_id=str(row["tenant_id"]),
        subject_id=str(row["subject_id"]),
        requested_action=str(row["requested_action"]),
        state=str(row["state"]),
        requesting_actor=str(row["requesting_actor"]),
        decision_actor=row.get("decision_actor"),
        reason=str(row["reason"]),
        created_at=_timestamp(row["created_at"]),
        decision_at=_timestamp(row["decision_at"]) if row.get("decision_at") else None,
        workflow_stage=str(row.get("workflow_stage") or "FINANCE"),
        current_approver_role=str(row.get("current_approver_role") or "finance"),
        compatibility_id=row.get("compatibility_id"),
        escalated_to=row.get("escalated_to"),
    )


def _timestamp(value: Any) -> datetime:
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
