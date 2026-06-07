from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from database.db import (
    add_recommendation_event,
    get_recommendation,
    list_recommendation_events,
)
from data.supabase_client import supabase
from config import DEFAULT_ORG_ID
from services.workflow_service import normalize_workflow_state, transition_workflow_state


# SLA Configuration (in hours)
SLA_RULES = {
    "PENDING_APPROVAL": 48,
    "APPROVED": 72,
    "ASSIGNED": 120,
    "IN_PROGRESS": 168,
}


def _get_stale_cutoff(sla_hours: int) -> str:
    cutoff = datetime.utcnow() - timedelta(hours=sla_hours)
    return cutoff.isoformat()


def find_stale_approvals(sla_hours: int = 48, organization_id: str = DEFAULT_ORG_ID) -> list[dict[str, Any]]:
    """Find all recommendations pending approval longer than SLA."""
    cutoff = _get_stale_cutoff(sla_hours)
    try:
        response = supabase.table("recommendations").select("*").eq("organization_id", organization_id).eq("status", "pending").lt("updated_at", cutoff).execute()
        return response.data or []
    except Exception as e:
        return []


def find_stale_by_state(workflow_state: str, sla_hours: int | None = None, organization_id: str = DEFAULT_ORG_ID) -> list[dict[str, Any]]:
    """Find all recommendations in a state longer than configured SLA."""
    hours = sla_hours or SLA_RULES.get(workflow_state, 168)
    cutoff = _get_stale_cutoff(hours)

    try:
        response = supabase.table("recommendations").select("*").eq("organization_id", organization_id).lt("updated_at", cutoff).execute()
        data = response.data or []

        stale_items = []
        for item in data:
            current_state = normalize_workflow_state(item.get("status"))
            if current_state == workflow_state:
                stale_items.append(item)

        return stale_items
    except Exception:
        return []


def _notify_approvers(recommendation_id: int, title: str, aging_hours: int, approvers: list[str] | None = None) -> bool:
    """Queue notification to approvers (hook for email/slack integration)."""
    # This is a placeholder for integration with notification service
    # In production, would call notification_service.send_escalation_notice(...)
    try:
        notification_data = {
            "organization_id": DEFAULT_ORG_ID,
            "recommendation_id": recommendation_id,
            "title": title,
            "aging_hours": aging_hours,
            "approvers": approvers or [],
            "created_at": datetime.utcnow().isoformat(),
            "status": "pending",
        }
        response = supabase.table("notification_queue").insert(notification_data).execute()
        return bool(response.data)
    except Exception:
        return False


def _compute_aging(created_at: str | None) -> int:
    """Compute hours since creation."""
    if not created_at:
        return 0
    try:
        created = datetime.fromisoformat(str(created_at).replace("Z", "+00:00"))
        if created.tzinfo is None:
            created = created.replace(tzinfo=datetime.now().astimezone().tzinfo)
        now = datetime.now(created.tzinfo) if created.tzinfo else datetime.utcnow()
        return int((now - created).total_seconds() // 3600)
    except Exception:
        return 0


def escalate_stale_approval(
    recommendation_id: int,
    actor: str = "escalation_engine",
    dry_run: bool = False,
) -> dict[str, Any]:
    """
    Escalate a single stale approval to leadership.

    Returns:
        {
            "ok": bool,
            "escalated": bool,
            "recommendation_id": int,
            "previous_state": str,
            "new_state": str,
            "reason": str,
        }
    """
    try:
        rec = get_recommendation(recommendation_id)
        if not rec:
            return {
                "ok": False,
                "escalated": False,
                "recommendation_id": recommendation_id,
                "reason": "Recommendation not found",
            }

        current_state = normalize_workflow_state(rec.get("status"))
        if current_state not in {"PENDING_APPROVAL", "APPROVED", "ASSIGNED", "IN_PROGRESS"}:
            return {
                "ok": True,
                "escalated": False,
                "recommendation_id": recommendation_id,
                "previous_state": current_state,
                "new_state": current_state,
                "reason": f"Already in state {current_state}, no escalation needed",
            }

        aging_hours = _compute_aging(rec.get("updated_at") or rec.get("created_at"))
        sla_hours = SLA_RULES.get(current_state, 168)

        if aging_hours < sla_hours:
            return {
                "ok": True,
                "escalated": False,
                "recommendation_id": recommendation_id,
                "previous_state": current_state,
                "new_state": current_state,
                "reason": f"Only {aging_hours}h old (SLA: {sla_hours}h)",
            }

        if dry_run:
            return {
                "ok": True,
                "escalated": False,
                "recommendation_id": recommendation_id,
                "previous_state": current_state,
                "new_state": "ESCALATED",
                "reason": f"DRY_RUN: Would escalate {aging_hours}h stale {current_state}",
            }

        # Execute escalation
        title = rec.get("title") or f"Recommendation {recommendation_id}"
        escalation_ok = transition_workflow_state(
            recommendation_id,
            "ESCALATED",
            username=actor,
            owner=rec.get("owner"),
            notes=f"Auto-escalated after {aging_hours}h in {current_state} (SLA: {sla_hours}h)",
        )

        if escalation_ok:
            # Queue notifications
            approvers = [rec.get("owner")] if rec.get("owner") else []
            _notify_approvers(recommendation_id, title, aging_hours, approvers)

            return {
                "ok": True,
                "escalated": True,
                "recommendation_id": recommendation_id,
                "previous_state": current_state,
                "new_state": "ESCALATED",
                "reason": f"Escalated after {aging_hours}h in {current_state}",
                "aging_hours": aging_hours,
                "sla_hours": sla_hours,
            }
        else:
            return {
                "ok": False,
                "escalated": False,
                "recommendation_id": recommendation_id,
                "previous_state": current_state,
                "reason": "Transition to ESCALATED failed (invalid state transition)",
            }

    except Exception as e:
        return {
            "ok": False,
            "escalated": False,
            "recommendation_id": recommendation_id,
            "reason": f"Exception: {str(e)}",
        }


def batch_escalate_stale(
    workflow_state: str = "PENDING_APPROVAL",
    sla_hours: int | None = None,
    actor: str = "escalation_engine",
    dry_run: bool = False,
    organization_id: str = DEFAULT_ORG_ID,
) -> dict[str, Any]:
    """
    Find and escalate all stale items in a given workflow state.

    Returns:
        {
            "ok": bool,
            "total_stale": int,
            "escalated_count": int,
            "failed_count": int,
            "dry_run": bool,
            "results": [escalation result dicts],
        }
    """
    stale_items = find_stale_by_state(workflow_state, sla_hours, organization_id)

    results = []
    escalated_count = 0
    failed_count = 0

    for item in stale_items:
        rec_id = item.get("id")
        result = escalate_stale_approval(rec_id, actor=actor, dry_run=dry_run)
        results.append(result)

        if result.get("ok"):
            if result.get("escalated"):
                escalated_count += 1
        else:
            failed_count += 1

    return {
        "ok": True,
        "total_stale": len(stale_items),
        "escalated_count": escalated_count,
        "failed_count": failed_count,
        "dry_run": dry_run,
        "results": results,
    }


def get_escalation_report(days: int = 7, organization_id: str = DEFAULT_ORG_ID) -> dict[str, Any]:
    """Generate escalation activity report for the last N days."""
    cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()

    try:
        # Get all escalation events in the period
        response = supabase.table("recommendation_events").select("*").eq("organization_id", organization_id).eq("action", "workflow_state_changed").gte("created_at", cutoff).execute()

        events = response.data or []
        escalations = [e for e in events if str(e.get("new_value", "")).upper() == "ESCALATED"]

        # Summarize by state
        state_summary = {}
        for state in SLA_RULES:
            state_summary[state] = 0

        for event in escalations:
            old_value = str(event.get("old_value", "")).upper()
            if old_value in state_summary:
                state_summary[old_value] += 1

        return {
            "ok": True,
            "period_days": days,
            "total_escalations": len(escalations),
            "by_previous_state": state_summary,
            "recent_events": escalations[:20],
        }
    except Exception as e:
        return {
            "ok": False,
            "period_days": days,
            "error": str(e),
        }


def get_aging_summary(organization_id: str = DEFAULT_ORG_ID) -> dict[str, Any]:
    """Get summary of recommendations by age and state."""
    try:
        response = supabase.table("recommendations").select("id,status,created_at,updated_at").eq("organization_id", organization_id).execute()
        recs = response.data or []

        summary = {
            "total": len(recs),
            "by_state": {},
            "aging_distribution": {
                "0_24h": 0,
                "1_3d": 0,
                "3_7d": 0,
                "7_30d": 0,
                "30plus_d": 0,
            },
            "sla_violations": {},
        }

        for rec in recs:
            state = normalize_workflow_state(rec.get("status"))
            if state not in summary["by_state"]:
                summary["by_state"][state] = 0
            summary["by_state"][state] += 1

            aging_hours = _compute_aging(rec.get("updated_at") or rec.get("created_at"))
            aging_days = aging_hours / 24

            if aging_days < 1:
                summary["aging_distribution"]["0_24h"] += 1
            elif aging_days < 3:
                summary["aging_distribution"]["1_3d"] += 1
            elif aging_days < 7:
                summary["aging_distribution"]["3_7d"] += 1
            elif aging_days < 30:
                summary["aging_distribution"]["7_30d"] += 1
            else:
                summary["aging_distribution"]["30plus_d"] += 1

            sla_hours = SLA_RULES.get(state, 168)
            if aging_hours > sla_hours:
                if state not in summary["sla_violations"]:
                    summary["sla_violations"][state] = 0
                summary["sla_violations"][state] += 1

        return {
            "ok": True,
            "summary": summary,
            "timestamp": datetime.utcnow().isoformat(),
        }
    except Exception as e:
        return {
            "ok": False,
            "error": str(e),
        }

