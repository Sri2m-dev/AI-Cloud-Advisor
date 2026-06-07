"""Enterprise approval workflow engine."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from repositories.approval_repository import ApprovalRepository, utc_now


APPROVAL_STATUS_LIFECYCLE = {
    "DRAFT": {"PENDING"},
    "SUBMITTED": {"PENDING", "REJECTED"},
    "PENDING": {"APPROVED", "REJECTED", "ESCALATED"},
    "PENDING_APPROVAL": {"APPROVED", "REJECTED", "ESCALATED"},
    "ESCALATED": {"APPROVED", "REJECTED"},
    "APPROVED": {"COMPLETED", "ROLLED_BACK", "REJECTED"},
    "COMPLETED": {"ROLLED_BACK"},
    "REJECTED": {"PENDING"},
    "ROLLED_BACK": {"PENDING"},
}

TERMINAL_STATUSES = {"COMPLETED"}


@dataclass(frozen=True)
class ApprovalTransition:
    approval_id: str
    target_status: str
    actor: str
    comments: str = ""
    organization_id: str | None = None
    rollback_to_status: str = "PENDING"


def normalize_status(status: str | None) -> str:
    value = str(status or "PENDING").strip().upper()
    aliases = {
        "NEW": "PENDING",
        "PENDING_APPROVAL": "PENDING_APPROVAL",
        "ACCEPTED": "APPROVED",
        "DISMISSED": "REJECTED",
        "DONE": "COMPLETED",
        "IMPLEMENTED": "COMPLETED",
    }
    return aliases.get(value, value)


def allowed_transitions(status: str | None) -> set[str]:
    return APPROVAL_STATUS_LIFECYCLE.get(normalize_status(status), set())


def can_transition(current_status: str | None, target_status: str | None) -> bool:
    target = normalize_status(target_status)
    return target in allowed_transitions(current_status)


class ApprovalWorkflowEngine:
    @staticmethod
    def transition(transition: ApprovalTransition) -> dict[str, Any]:
        current = ApprovalRepository.fetch_approval(
            transition.approval_id,
            organization_id=transition.organization_id,
        ) or {"id": transition.approval_id, "status": "PENDING"}

        previous_status = normalize_status(current.get("status"))
        target_status = normalize_status(transition.target_status)
        now = utc_now()

        if not can_transition(previous_status, target_status):
            ApprovalWorkflowEngine._write_audit_event(
                approval_id=transition.approval_id,
                actor=transition.actor,
                action="approval_transition_rejected",
                previous_status=previous_status,
                new_status=target_status,
                comments=transition.comments or "Invalid approval transition",
                organization_id=transition.organization_id or current.get("org_id"),
                created_at=now,
            )
            return {
                "ok": False,
                "error": "INVALID_TRANSITION",
                "previous_status": previous_status,
                "target_status": target_status,
            }

        payload = ApprovalWorkflowEngine._payload_for_transition(
            target_status=target_status,
            actor=transition.actor,
            comments=transition.comments,
            created_at=now,
            rollback_to_status=transition.rollback_to_status,
        )
        ApprovalRepository.update_approval(
            transition.approval_id,
            payload,
            organization_id=transition.organization_id,
        )
        ApprovalWorkflowEngine._write_audit_event(
            approval_id=transition.approval_id,
            actor=transition.actor,
            action=f"approval_{target_status.lower()}",
            previous_status=previous_status,
            new_status=target_status,
            comments=transition.comments,
            organization_id=transition.organization_id or current.get("org_id"),
            created_at=now,
        )
        return {
            "ok": True,
            "approval_id": transition.approval_id,
            "previous_status": previous_status,
            "status": target_status,
            "timestamp": now,
        }

    @staticmethod
    def _payload_for_transition(
        *,
        target_status: str,
        actor: str,
        comments: str,
        created_at: str,
        rollback_to_status: str,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "status": target_status,
            "updated_at": created_at,
            "updated_by": actor,
            "approver_comments": comments,
        }
        if target_status == "APPROVED":
            payload.update({"approved_at": created_at, "approved_by": actor})
        elif target_status == "REJECTED":
            payload.update({"rejected_at": created_at, "rejected_by": actor, "rejection_reason": comments})
        elif target_status == "COMPLETED":
            payload.update({"completed_at": created_at, "completed_by": actor})
        elif target_status == "ROLLED_BACK":
            payload.update(
                {
                    "rolled_back_at": created_at,
                    "rolled_back_by": actor,
                    "rollback_reason": comments,
                    "rollback_to_status": normalize_status(rollback_to_status),
                }
            )
        return payload

    @staticmethod
    def _write_audit_event(
        *,
        approval_id: str,
        actor: str,
        action: str,
        previous_status: str,
        new_status: str,
        comments: str,
        organization_id: str | None,
        created_at: str,
    ) -> None:
        event = {
            "approval_id": approval_id,
            "org_id": organization_id,
            "actor": actor,
            "action": action,
            "previous_status": previous_status,
            "new_status": new_status,
            "comments": comments,
            "created_at": created_at,
        }
        try:
            ApprovalRepository.insert_audit_event(event)
        except Exception:
            # Audit should never hide the workflow result from the caller.
            pass

    @staticmethod
    def history(approval_id: str) -> list[dict[str, Any]]:
        try:
            return ApprovalRepository.fetch_audit_trail(approval_id)
        except Exception:
            return []

