from __future__ import annotations

import hashlib
import json
from typing import Any

from database.db import get_recommendation
from data.supabase_client import supabase, supabase_admin
from services.workflow_service import can_transition_workflow_state, normalize_workflow_state


def _build_idempotency_key(
    recommendation_id: str,
    to_status: str,
    actor: str,
    metadata: dict[str, Any] | None,
) -> str:
    base = {
        "recommendation_id": str(recommendation_id or "").strip(),
        "to_status": str(to_status or "").strip().lower(),
        "actor": str(actor or "").strip().lower(),
        "metadata": metadata or {},
    }
    payload = json.dumps(base, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def transition_recommendation_status(
    recommendation_id: str,
    to_status: str,
    actor: str,
    *,
    expected_version: int | None = None,
    metadata: dict[str, Any] | None = None,
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    """Execute an atomic recommendation workflow transition via Supabase RPC."""
    if not recommendation_id or not to_status:
        return {"ok": False, "error": "INVALID_INPUT"}

    current = get_recommendation(int(recommendation_id)) or {}
    current_state = normalize_workflow_state(current.get("status"))
    target_state = normalize_workflow_state(to_status)
    if not can_transition_workflow_state(current_state, target_state):
        return {
            "ok": False,
            "error": "INVALID_TRANSITION",
            "current_state": current_state,
            "target_state": target_state,
        }

    md = metadata or {}
    key = idempotency_key or _build_idempotency_key(recommendation_id, to_status, actor, md)

    params = {
        "p_recommendation_id": str(recommendation_id),
        "p_to_status": str(to_status).lower(),
        "p_actor": str(actor or "workflow"),
        "p_idempotency_key": key,
        "p_expected_version": expected_version,
        "p_metadata": md,
    }

    client = supabase_admin or supabase
    try:
        response = client.rpc("recommendation_transition_txn", params).execute()
        data = response.data

        if isinstance(data, list):
            payload = data[0] if data else {}
        elif isinstance(data, dict):
            payload = data
        else:
            payload = {}

        return payload if isinstance(payload, dict) else {"ok": False, "error": "RPC_INVALID_RESPONSE"}
    except Exception as exc:
        return {"ok": False, "error": "RPC_EXECUTION_FAILED", "message": str(exc)}

