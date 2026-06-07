from __future__ import annotations

from datetime import datetime
from typing import Any

from database.db import (
    add_recommendation_event,
    get_recommendation,
    update_recommendation_details,
    update_recommendation_status,
)
from services.audit_service import (
    log_recommendation_accepted,
    log_recommendation_rejected,
    log_status_changed,
    log_workflow_changed,
)

WORKFLOW_STATES = [
    "NEW",
    "PENDING_APPROVAL",
    "APPROVED",
    "REJECTED",
    "ASSIGNED",
    "IN_PROGRESS",
    "IMPLEMENTED",
    "SNOOZED",
    "ESCALATED",
    "CLOSED",
]

LEGACY_TO_WORKFLOW = {
    "new": "NEW",
    "pending": "PENDING_APPROVAL",
    "pending_approval": "PENDING_APPROVAL",
    "accepted": "APPROVED",
    "approved": "APPROVED",
    "dismissed": "REJECTED",
    "rejected": "REJECTED",
    "assigned": "ASSIGNED",
    "done": "CLOSED",
    "completed": "CLOSED",
    "implemented": "IMPLEMENTED",
    "snoozed": "SNOOZED",
    "in_progress": "IN_PROGRESS",
    "escalated": "ESCALATED",
    "closed": "CLOSED",
}

WORKFLOW_TO_STORAGE = {
    "NEW": "new",
    "PENDING_APPROVAL": "pending",
    "APPROVED": "accepted",
    "REJECTED": "dismissed",
    "ASSIGNED": "accepted",
    "IN_PROGRESS": "in_progress",
    "IMPLEMENTED": "implemented",
    "SNOOZED": "snoozed",
    "ESCALATED": "accepted",
    "CLOSED": "completed",
}

ALLOWED_WORKFLOW_TRANSITIONS = {
    "NEW": {"PENDING_APPROVAL", "REJECTED"},
    "PENDING_APPROVAL": {"APPROVED", "REJECTED"},
    "APPROVED": {"ASSIGNED"},
    "ASSIGNED": {"IN_PROGRESS"},
    "IN_PROGRESS": {"IMPLEMENTED", "ESCALATED"},
    "IMPLEMENTED": {"CLOSED"},
    "SNOOZED": {"PENDING_APPROVAL"},
    "ESCALATED": {"APPROVED", "REJECTED"},
    "REJECTED": {"NEW", "PENDING_APPROVAL"},
    "CLOSED": set(),
}


def normalize_workflow_state(status: str | None) -> str:
    normalized = str(status or "").strip().lower()
    return LEGACY_TO_WORKFLOW.get(normalized, "NEW")


def _storage_state(workflow_state: str) -> str:
    state = str(workflow_state or "NEW").strip().upper()
    return WORKFLOW_TO_STORAGE.get(state, "new")


def can_transition_workflow_state(current_state: str | None, target_state: str | None) -> bool:
    current = normalize_workflow_state(current_state)
    target = str(target_state or "NEW").strip().upper()
    return target in ALLOWED_WORKFLOW_TRANSITIONS.get(current, set())


def _log_workflow_transition(recommendation_id: int, username: str, old_state: str, new_state: str, notes: str | None) -> None:
    add_recommendation_event(
        recommendation_id,
        username,
        action="workflow_state_changed",
        old_value=old_state,
        new_value=new_state,
        notes=notes,
    )
    log_status_changed(
        resource_id=recommendation_id,
        changed_by=username,
        org_id=1,
        resource_type="recommendation",
        old_status=old_state,
        new_status=new_state,
        notes=notes,
    )
    log_workflow_changed(
        workflow_id=recommendation_id,
        changed_by=username,
        org_id=1,
        old_state=old_state,
        new_state=new_state,
        notes=notes,
        resource_type="recommendation",
    )
    if new_state == "APPROVED":
        log_recommendation_accepted(
            recommendation_id=recommendation_id,
            accepted_by=username,
            org_id=1,
            previous_state=old_state,
            notes=notes,
        )
    elif new_state == "REJECTED":
        log_recommendation_rejected(
            recommendation_id=recommendation_id,
            rejected_by=username,
            org_id=1,
            reason=notes,
            previous_state=old_state,
        )


def transition_workflow_state(
    recommendation_id: int,
    target_state: str,
    *,
    username: str,
    owner: str | None = None,
    notes: str | None = None,
    dismiss_reason: str | None = None,
) -> bool:
    current = get_recommendation(recommendation_id) or {}
    previous_state = normalize_workflow_state(current.get("status"))
    desired_state = str(target_state or "NEW").strip().upper()

    if not can_transition_workflow_state(previous_state, desired_state):
        add_recommendation_event(
            recommendation_id,
            username,
            action="workflow_transition_rejected",
            old_value=previous_state,
            new_value=desired_state,
            notes=notes or "Rejected invalid workflow transition",
        )
        return False

    status_value = _storage_state(desired_state)

    updated = update_recommendation_status(
        recommendation_id,
        status_value,
        username=username,
        owner=owner,
        dismiss_reason=dismiss_reason,
        notes=notes,
    )
    if not updated:
        return False

    if desired_state == "ESCALATED":
        update_recommendation_details(
            recommendation_id=recommendation_id,
            username=username,
            priority="high",
            notes="Escalated and raised to high priority",
        )
    if desired_state == "IN_PROGRESS":
        update_recommendation_details(
            recommendation_id=recommendation_id,
            username=username,
            owner=owner,
            notes="Execution started",
        )

    _log_workflow_transition(recommendation_id, username, previous_state, desired_state, notes)
    return True


def assign_owner(recommendation_id: int, owner: str, *, username: str, notes: str | None = None) -> bool:
    current = get_recommendation(recommendation_id) or {}
    old_owner = str(current.get("owner") or "")
    updated = update_recommendation_details(
        recommendation_id=recommendation_id,
        username=username,
        owner=owner,
        notes=notes or f"Assigned to {owner}",
    )
    if not updated:
        return False
    add_recommendation_event(
        recommendation_id,
        username,
        action="assignment_changed",
        old_value=old_owner,
        new_value=owner,
        notes=notes,
    )
    return True


def add_comment(recommendation_id: int, *, username: str, comment: str) -> bool:
    text = str(comment or "").strip()
    if not text:
        return False
    add_recommendation_event(
        recommendation_id,
        username,
        action="comment_added",
        old_value=None,
        new_value=text,
        notes=text,
    )
    return True


def workflow_timestamp() -> str:
    return datetime.utcnow().isoformat()

