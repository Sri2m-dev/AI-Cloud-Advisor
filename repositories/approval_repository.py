"""Repository layer for enterprise approval workflow persistence."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from services.supabase_client import supabase


APPROVAL_QUEUE_TABLE = "approval_requests"
APPROVAL_AUDIT_TABLE = "approval_audit"


def utc_now() -> str:
    return datetime.utcnow().isoformat()


class ApprovalRepository:
    @staticmethod
    def fetch_approval(approval_id: str, organization_id: str | None = None) -> dict[str, Any] | None:
        query = supabase.table(APPROVAL_QUEUE_TABLE).select("*").eq("id", approval_id)
        if organization_id:
            query = query.eq("organization_id", organization_id)
        response = query.limit(1).execute()
        rows = response.data or []
        return rows[0] if rows else None

    @staticmethod
    def fetch_pending_approvals(organization_id: str) -> list[dict[str, Any]]:
        response = (
            supabase.table(APPROVAL_QUEUE_TABLE)
            .select("*")
            .eq("organization_id", organization_id)
            .in_("status", ["PENDING", "PENDING_APPROVAL", "ESCALATED"])
            .order("created_at", desc=True)
            .execute()
        )
        return response.data or []

    @staticmethod
    def update_approval(approval_id: str, payload: dict[str, Any], organization_id: str | None = None) -> bool:
        query = supabase.table(APPROVAL_QUEUE_TABLE).update(payload).eq("id", approval_id)
        if organization_id:
            query = query.eq("organization_id", organization_id)
        query.execute()
        return True

    @staticmethod
    def insert_audit_event(event: dict[str, Any]) -> None:
        supabase.table(APPROVAL_AUDIT_TABLE).insert(event).execute()

    @staticmethod
    def fetch_audit_trail(approval_id: str) -> list[dict[str, Any]]:
        response = (
            supabase.table(APPROVAL_AUDIT_TABLE)
            .select("*")
            .eq("approval_id", approval_id)
            .order("created_at", desc=True)
            .execute()
        )
        return response.data or []

