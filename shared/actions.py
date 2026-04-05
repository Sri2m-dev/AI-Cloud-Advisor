from datetime import datetime, timezone
import uuid

import pandas as pd

from shared.supabase_client import get_supabase_client

SUPPORTED_EXECUTORS = ["mock", "aws_lambda", "terraform", "api"]

ROLE_PERMISSIONS = {
    "CEO": {"view": True, "approve": False, "execute": False},
    "CTO": {"view": True, "approve": True, "execute": False},
    "FinOps": {"view": True, "approve": False, "execute": True},
}


def can_approve(role):
    return ROLE_PERMISSIONS.get(role, {}).get("approve", False)


def can_execute(role):
    return ROLE_PERMISSIONS.get(role, {}).get("execute", False)


def _safe_executor(executor):
    if executor in SUPPORTED_EXECUTORS:
        return executor
    return "mock"


def log_action(email, action, resource):
    client = get_supabase_client()

    client.table("audit_logs").insert({
        "user_email": email,
        "action": action,
        "resource": resource
    }).execute()


def submit_action_request(client_id, actor_email, recommendation_title, executor="mock", action_type="apply_fix"):
    client = get_supabase_client()
    safe_executor = _safe_executor(executor)

    payload = {
        "id": str(uuid.uuid4()),
        "client_id": client_id,
        "actor_email": actor_email,
        "recommendation_title": recommendation_title,
        "action_type": action_type,
        "executor": safe_executor,
        "status": "pending_approval",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    try:
        data = client.table("action_requests").insert(payload).execute().data
        request_id = data[0].get("id") if data else payload["id"]
        try:
            log_action(actor_email, action_type, recommendation_title)
        except Exception:
            pass
        return {"status": True, "request_id": request_id, "executor": safe_executor}
    except Exception as exc:
        return {"status": False, "error": str(exc), "executor": safe_executor}


def get_action_requests(client_id):
    client = get_supabase_client()

    try:
        data = (
            client.table("action_requests")
            .select("id,recommendation_title,action_type,executor,status,created_at")
            .eq("client_id", client_id)
            .order("created_at", desc=True)
            .limit(50)
            .execute()
            .data
        )
        return pd.DataFrame(data)
    except Exception:
        return pd.DataFrame(
            columns=["id", "recommendation_title", "action_type", "executor", "status", "created_at"]
        )


def _update_action_status(request_id, status):
    client = get_supabase_client()
    client.table("action_requests").update({"status": status}).eq("id", request_id).execute()


def approve_action_request(request_id, approver_email=None):
    approver_email = approver_email or "approver@local"
    try:
        _update_action_status(request_id, "approved")
        try:
            log_action(approver_email, "approve_action", request_id)
        except Exception:
            pass
        return {"status": True, "request_id": request_id}
    except Exception as exc:
        return {"status": False, "error": str(exc)}


def process_pending_actions(client_id, limit=20):
    client = get_supabase_client()
    summary = {"processed": 0, "success": 0, "queued": 0, "failed": 0}

    try:
        pending = (
            client.table("action_requests")
            .select("id,executor")
            .eq("client_id", client_id)
            .eq("status", "approved")
            .order("created_at", desc=False)
            .limit(limit)
            .execute()
            .data
        )
    except Exception:
        return summary

    for req in pending:
        req_id = req.get("id")
        executor = _safe_executor(req.get("executor"))
        if not req_id:
            continue

        summary["processed"] += 1

        try:
            _update_action_status(req_id, "running")

            # Mock actions are executed synchronously here.
            if executor == "mock":
                _update_action_status(req_id, "success")
                summary["success"] += 1
            else:
                # Non-mock executors are marked queued for external worker pickup.
                _update_action_status(req_id, "queued")
                summary["queued"] += 1
        except Exception:
            try:
                _update_action_status(req_id, "failed")
            except Exception:
                pass
            summary["failed"] += 1

    return summary
