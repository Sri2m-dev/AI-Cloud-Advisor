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

    def get_history(self, context: TenantContext, request_id: str) -> tuple[ApprovalHistory, ...]: ...


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
        target = str(to_state).upper()
        workflow_stage = current.workflow_stage
        if target == "APPROVED" and current.workflow_stage != "CEO":
            workflow_stage = STAGE_ORDER[STAGE_ORDER.index(current.workflow_stage) + 1]
            target = "PENDING"
        if target not in ALLOWED_TRANSITIONS.get(current.state, frozenset()):
            raise ApprovalAuthorityError(
                f"invalid approval transition: {current.state} -> {target}"
            )
        now = datetime.now(timezone.utc)
        updated = replace(
            current,
            state=target,
            decision_actor=actor,
            decision_at=now,
            workflow_stage=workflow_stage,
            current_approver_role=STAGE_ROLES[workflow_stage],
            escalated_to=escalated_to if target == "ESCALATED" else None,
        )
        self._requests[key] = updated
        self._history[key].append(
            ApprovalHistory(
                history_id=str(uuid4()), request_id=request_id,
                organization_id=context.organization_id, tenant_id=context.tenant_id,
                from_state=current.state, to_state=target, actor=actor,
                reason=reason, occurred_at=now,
                action="ESCALATE" if target == "ESCALATED" else "TRANSITION",
                actor_role=actor_role,
            )
        )
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
    """PostgREST adapter for the explicit v1 approval authority tables."""

    def __init__(self, client: Any) -> None:
        self._client = client

    def create_request(
        self, context: TenantContext, *, subject_id: str, requested_action: str,
        requesting_actor: str, reason: str, request_id: str | None = None,
    ) -> ApprovalRequest:
        payload = {
            "request_id": request_id or str(uuid4()),
            "organization_id": context.organization_id,
            "tenant_id": context.tenant_id,
            "subject_id": subject_id,
            "requested_action": requested_action,
            "state": "PENDING",
            "requesting_actor": requesting_actor,
            "reason": reason,
            "workflow_stage": workflow_stage,
            "current_approver_role": STAGE_ROLES[workflow_stage],
        }
        row = self._client.table("nexora_v1_approval_requests").insert(payload).execute().data[0]
        return _request_from_row(row)

    def get_request(self, context: TenantContext, request_id: str) -> ApprovalRequest | None:
        rows = (
            self._client.table("nexora_v1_approval_requests")
            .select("*")
            .eq("organization_id", context.organization_id)
            .eq("tenant_id", context.tenant_id)
            .eq("request_id", request_id)
            .limit(1)
            .execute()
            .data
            or []
        )
        return _request_from_row(rows[0]) if rows else None

    def list_requests(self, context: TenantContext) -> tuple[ApprovalRequest, ...]:
        rows = (
            self._client.table("nexora_v1_approval_requests")
            .select("*")
            .eq("organization_id", context.organization_id)
            .eq("tenant_id", context.tenant_id)
            .order("created_at", desc=True)
            .execute()
            .data
            or []
        )
        return tuple(_request_from_row(row) for row in rows)

    def transition_request(
        self, context: TenantContext, request_id: str, *, to_state: str,
        actor: str, reason: str, actor_role: str | None = None,
        escalated_to: str | None = None,
    ) -> ApprovalRequest:
        current = self.get_request(context, request_id)
        if current is None:
            raise ApprovalAuthorityError("approval request not found")
        target = str(to_state).upper()
        workflow_stage = current.workflow_stage
        if target == "APPROVED" and current.workflow_stage != "CEO":
            workflow_stage = STAGE_ORDER[STAGE_ORDER.index(current.workflow_stage) + 1]
            target = "PENDING"
        if target not in ALLOWED_TRANSITIONS.get(current.state, frozenset()):
            raise ApprovalAuthorityError(
                f"invalid approval transition: {current.state} -> {target}"
            )
        now = datetime.now(timezone.utc).isoformat()
        row = (
            self._client.table("nexora_v1_approval_requests")
            .update({
                "state": target,
                "decision_actor": actor,
                "decision_at": now,
                "workflow_stage": workflow_stage,
                "current_approver_role": STAGE_ROLES[workflow_stage],
                "escalated_to": escalated_to if target == "ESCALATED" else None,
            })
            .eq("organization_id", context.organization_id)
            .eq("tenant_id", context.tenant_id)
            .eq("request_id", request_id)
            .execute()
            .data[0]
        )
        self._client.table("nexora_v1_approval_history").insert({
            "request_id": request_id,
            "organization_id": context.organization_id,
            "tenant_id": context.tenant_id,
            "from_state": current.state,
            "to_state": target,
            "actor": actor,
            "reason": reason,
            "occurred_at": now,
            "action": "ESCALATE" if target == "ESCALATED" else "TRANSITION",
            "actor_role": actor_role,
        }).execute()
        return _request_from_row(row)

    def get_history(self, context: TenantContext, request_id: str) -> tuple[ApprovalHistory, ...]:
        rows = (
            self._client.table("nexora_v1_approval_history")
            .select("*")
            .eq("organization_id", context.organization_id)
            .eq("tenant_id", context.tenant_id)
            .eq("request_id", request_id)
            .order("occurred_at")
            .execute()
            .data
            or []
        )
        return tuple(ApprovalHistory(**row) for row in rows)


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
