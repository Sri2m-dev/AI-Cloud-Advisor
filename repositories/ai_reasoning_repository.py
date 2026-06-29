from __future__ import annotations

from typing import Any

from connectors.common.tenant_guard import resolve_organization_id
from services.supabase_client import supabase


class AIReasoningRepository:
    @staticmethod
    def get_policy_rules(organization_id: str | None = None) -> list[dict[str, Any]]:
        del organization_id
        try:
            return (
                supabase.table("policy_rules")
                .select("*")
                .eq("enabled", True)
                .execute()
                .data
                or []
            )
        except Exception:
            return []

    @staticmethod
    def get_history(organization_id: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
        org_id = resolve_organization_id(organization_id)
        try:
            return (
                supabase.table("ai_reasoning_history")
                .select("*")
                .eq("organization_id", org_id)
                .order("created_at", desc=True)
                .limit(limit)
                .execute()
                .data
                or []
            )
        except Exception:
            return []

    @staticmethod
    def save_history(payload: dict[str, Any]) -> bool:
        try:
            supabase.table("ai_reasoning_history").insert(payload).execute()
            return True
        except Exception:
            return False
