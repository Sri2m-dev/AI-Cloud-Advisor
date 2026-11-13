"""Authenticated V1 approval API backed by append-only customer workflow events."""

from dataclasses import asdict
from functools import lru_cache
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict

from auth.authenticated_tenant import (
    AuthenticatedTenantContext,
    AuthenticatedTenantError,
    api_application_account,
)
from backend.security import get_current_user

router = APIRouter(prefix="/approvals", tags=["approvals"])
_READ_ROLES = frozenset(
    {"client_admin", "executive", "cio", "finance", "operations", "auditor"}
)


class ApprovalCreate(BaseModel):
    workspace_id: str
    decision_id: str
    reason: str

    model_config = ConfigDict(extra="forbid")


class ApprovalCommand(BaseModel):
    approved_by: str | None = None
    rejected_by: str | None = None
    escalated_by: str | None = None
    comments: str | None = None
    reason: str | None = None
    escalate_to: str | None = None

    model_config = ConfigDict(extra="forbid")


def _request_context(request: Request, user: dict[str, Any]):
    try:
        account = api_application_account(user)
        authorization = request.headers.get("authorization", "")
        scheme, _, token = authorization.partition(" ")
        if scheme.lower() != "bearer" or not token.strip():
            raise HTTPException(status_code=401, detail="A verified bearer token is required")
        context = AuthenticatedTenantContext(
            organization_id=account.organization_id,
            organization_name=str(
                user.get("organization_name")
                or user.get("tenant_name")
                or account.organization_id
            ),
            user_id=str(user.get("user_id") or user.get("sub") or account.user_id),
            user_email=str(user.get("email") or account.user_id),
            role=str(user.get("role") or ""),
            authorization_claims=frozenset(),
            tenant_id=account.organization_id,
            auth_access_token=token.strip(),
        )
    except AuthenticatedTenantError as error:
        raise HTTPException(status_code=403, detail="Approval scope denied") from error
    except PermissionError as error:
        raise HTTPException(status_code=403, detail="Approval scope denied") from error
    return context, account


def _verify_selectors(
    request: Request,
    account,
    context: AuthenticatedTenantContext,
    *,
    actor: str | None = None,
    organization_id: str | None = None,
) -> None:
    organizations = request.query_params.getlist("org_id")
    if organization_id is not None:
        organizations.append(organization_id)
    actors = request.query_params.getlist("created_by")
    actors.extend(request.query_params.getlist("username"))
    if actor is not None:
        actors.append(actor)
    if any(value != account.organization_id for value in organizations):
        raise HTTPException(status_code=403, detail="Approval scope denied")
    valid_actors = {account.user_id, context.user_id}
    if any(value not in valid_actors for value in actors):
        raise HTTPException(status_code=403, detail="Approval actor denied")


@lru_cache(maxsize=1)
def _workflow_service():
    from services.customer_workflow_service import (
        CustomerWorkflowError,
        CustomerWorkflowService,
    )
    from universal_evidence.persistence import LifecyclePersistenceError

    try:
        return CustomerWorkflowService.from_environment()
    except (CustomerWorkflowError, LifecyclePersistenceError) as error:
        raise HTTPException(
            status_code=503,
            detail="Customer workflow persistence is unavailable",
        ) from error


def _run(operation):
    from services.customer_workflow_service import CustomerWorkflowError
    from universal_evidence.persistence import LifecyclePersistenceError

    try:
        return operation()
    except PermissionError as error:
        raise HTTPException(status_code=403, detail="Approval scope denied") from error
    except CustomerWorkflowError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except LifecyclePersistenceError as error:
        raise HTTPException(
            status_code=503,
            detail="Customer workflow persistence is unavailable",
        ) from error


def _approval_records(service, context: AuthenticatedTenantContext) -> list[dict[str, Any]]:
    records = []
    for workspace in service.list_workspaces(context):
        workflow = service.resume_workspace(context, workspace.workspace_id)
        events = workflow["approvals"]
        requests = [
            event for event in events
            if event["event_type"] == "APPROVAL_REQUESTED"
        ]
        transitions = [
            event for event in events
            if event["event_type"] == "APPROVAL_TRANSITIONED"
        ]
        for request_event in requests:
            request_payload = request_event["payload"]
            approval_id = request_payload["approval_id"]
            history = []
            approval = dict(request_payload["approval"])
            for event in transitions:
                payload = event["payload"]
                if payload["approval_id"] != approval_id:
                    continue
                approval = dict(payload["approval"])
                history.append(dict(payload["history"]))
            records.append(
                {
                    **approval,
                    "approval_id": approval_id,
                    "workspace_id": workspace.workspace_id,
                    "request_event_id": request_event["event_id"],
                    "requested_at": request_event["occurred_at"],
                    "decision_event_id": request_payload["decision_id"],
                    "evidence_event_id": request_payload["evidence_id"],
                    "history": history,
                }
            )
    return records


def _find_approval(service, context: AuthenticatedTenantContext, approval_id: str):
    for record in _approval_records(service, context):
        if record["approval_id"] == approval_id:
            return record
    raise HTTPException(status_code=404, detail="Approval was not found")


@router.post("/create")
def create_approval(
    payload: ApprovalCreate,
    request: Request,
    user=Depends(get_current_user),
):
    context, account = _request_context(request, user)
    _verify_selectors(request, account, context)
    service = _workflow_service()
    event = _run(
        lambda: service.request_approval(
            context,
            payload.workspace_id,
            decision_id=payload.decision_id,
            reason=payload.reason,
        )
    )
    return asdict(event)


@router.get("/list")
@router.get("/metrics/queue")
@router.get("/workflow/transitions")
@router.get("/dashboard/snapshot")
def list_approvals(request: Request, user=Depends(get_current_user)):
    context, account = _request_context(request, user)
    _verify_selectors(request, account, context)
    if context.role not in _READ_ROLES:
        raise HTTPException(status_code=403, detail="Approval role denied")
    records = _run(lambda: _approval_records(_workflow_service(), context))
    if request.url.path.endswith("/metrics/queue"):
        return {
            "total": len(records),
            "pending": sum(record["state"] == "PENDING" for record in records),
        }
    if request.url.path.endswith("/workflow/transitions"):
        return {
            "transitions": [
                {
                    "approval_id": record["approval_id"],
                    "workspace_id": record["workspace_id"],
                    **history,
                }
                for record in records
                for history in record["history"]
            ]
        }
    return {"approvals": records}


@router.get("/{approval_id}/history")
def get_approval_history(
    approval_id: str,
    request: Request,
    user=Depends(get_current_user),
):
    context, account = _request_context(request, user)
    _verify_selectors(request, account, context)
    if context.role not in _READ_ROLES:
        raise HTTPException(status_code=403, detail="Approval role denied")
    record = _run(lambda: _find_approval(_workflow_service(), context, approval_id))
    return {
        "approval_id": approval_id,
        "workspace_id": record["workspace_id"],
        "history": record["history"],
    }


@router.get("/{approval_id}")
def get_approval(
    approval_id: str,
    request: Request,
    user=Depends(get_current_user),
):
    context, account = _request_context(request, user)
    _verify_selectors(request, account, context)
    if context.role not in _READ_ROLES:
        raise HTTPException(status_code=403, detail="Approval role denied")
    return _run(lambda: _find_approval(_workflow_service(), context, approval_id))


@router.post("/{approval_id}/export")
def export_approval_evidence(
    approval_id: str,
    request: Request,
    user=Depends(get_current_user),
):
    context, account = _request_context(request, user)
    _verify_selectors(request, account, context)
    record = _run(lambda: _find_approval(_workflow_service(), context, approval_id))
    service = _workflow_service()
    event = _run(
        lambda: service.export_evidence(
            context,
            record["workspace_id"],
            approval_id=approval_id,
        )
    )
    return asdict(event)


def _transition(
    approval_id: str,
    payload: ApprovalCommand,
    request: Request,
    user: dict[str, Any],
    *,
    target: str,
):
    context, account = _request_context(request, user)
    actors = [
        value
        for value in (payload.approved_by, payload.rejected_by, payload.escalated_by)
        if value is not None
    ]
    _verify_selectors(
        request,
        account,
        context,
        actor=actors[0] if actors else None,
    )
    if any(actor not in {account.user_id, context.user_id} for actor in actors):
        raise HTTPException(status_code=403, detail="Approval actor denied")
    record = _run(lambda: _find_approval(_workflow_service(), context, approval_id))
    event = _run(
        lambda: _workflow_service().transition_approval(
            context,
            record["workspace_id"],
            approval_id=approval_id,
            target=target,
            reason=payload.reason or payload.comments or "",
            escalated_to=payload.escalate_to,
        )
    )
    return asdict(event)


@router.post("/{approval_id}/approve")
def approve_approval(
    approval_id: str,
    payload: ApprovalCommand,
    request: Request,
    user=Depends(get_current_user),
):
    return _transition(approval_id, payload, request, user, target="APPROVED")


@router.post("/{approval_id}/reject")
def reject_approval(
    approval_id: str,
    payload: ApprovalCommand,
    request: Request,
    user=Depends(get_current_user),
):
    return _transition(approval_id, payload, request, user, target="REJECTED")


@router.post("/{approval_id}/escalate")
def escalate_approval(
    approval_id: str,
    payload: ApprovalCommand,
    request: Request,
    user=Depends(get_current_user),
):
    return _transition(approval_id, payload, request, user, target="ESCALATED")
