from __future__ import annotations
from services.supabase_client import supabase
import pandas as pd
from config import DEFAULT_ORG_ID

def list_workflow_recommendations(organization_id=DEFAULT_ORG_ID):
    try:
        response = (
            supabase.table("recommendations")
            .select("*")
            .eq("organization_id", organization_id)
            .execute()
        )

        data = response.data if response.data else []

        return pd.DataFrame(data)

    except Exception as e:
        return pd.DataFrame([
            {
                "status": "ERROR",
                "description": str(e)
            }
        ])

    if not response.data:
        return []

    import pandas as pd

    df = pd.DataFrame(response.data)

    df = normalize_recommendations(df)

    return df.to_dict(orient="records")

from datetime import datetime, timezone
from typing import Any

from database.db import (
    can_manage_recommendation,
    is_recommendation_manager_role,
    list_recommendation_events,
    list_recommendations,
    list_users,
    save_recommendation,
    update_recommendation_details,
    update_recommendation_status,
)
from services.workflow_service import assign_owner, can_transition_workflow_state, normalize_workflow_state, transition_workflow_state


def _age_days(created_at: str | None) -> int:
    if not created_at:
        return 0
    try:
        created = datetime.fromisoformat(str(created_at).replace("Z", "+00:00"))
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        return max(0, int((datetime.now(timezone.utc) - created).total_seconds() // 86400))
    except Exception:
        return 0


def _latest_workflow_state(rec_id: int, fallback_status: str | None) -> str:
    events = list_recommendation_events(rec_id, limit=25)
    for event in events:
        if event.get("action") == "workflow_state_changed":
            return str(event.get("new_value") or "NEW")
    return normalize_workflow_state(fallback_status)


def get_assignee_options(username: str) -> list[str]:
    users = [u.get("username") for u in list_users(viewer_username=username) if u.get("username")]
    seen = []
    for user in users:
        if user not in seen:
            seen.append(user)
    return seen


def list_workflow_recommendations(username: str, limit: int = 300, source: str | None = None) -> list[dict[str, Any]]:
    items = list_recommendations(username=username, limit=limit, source=source)
    normalized: list[dict[str, Any]] = []
    for item in items:
        rec_id = item.get("id")
        workflow_state = _latest_workflow_state(rec_id, item.get("status"))
        rec = dict(item)
        rec["workflow_state"] = workflow_state
        rec["aging_days"] = _age_days(item.get("created_at"))
        rec["risk_impact"] = "High" if str(item.get("priority") or "").lower() == "high" else "Medium"
        rec["monthly_savings"] = float(item.get("estimated_savings") or 0)
        rec["yearly_impact"] = rec["monthly_savings"] * 12
        normalized.append(rec)
    return normalized


def approve(recommendation_id: int, username: str) -> bool:
    return transition_workflow_state(recommendation_id, "APPROVED", username=username, notes="Approved from workflow")


def reject(recommendation_id: int, username: str, reason: str | None = None) -> bool:
    return transition_workflow_state(
        recommendation_id,
        "REJECTED",
        username=username,
        notes=reason or "Rejected from workflow",
        dismiss_reason=reason,
    )


def snooze(recommendation_id: int, username: str, days: int = 7) -> bool:
    return transition_workflow_state(
        recommendation_id,
        "SNOOZED",
        username=username,
        notes=f"Snoozed for {int(days)} day(s)",
    )


def escalate(recommendation_id: int, username: str, owner: str | None = None) -> bool:
    return transition_workflow_state(
        recommendation_id,
        "ESCALATED",
        username=username,
        owner=owner,
        notes="Escalated for leadership review",
    )


def assign(recommendation_id: int, username: str, owner: str) -> bool:
    return transition_workflow_state(
        recommendation_id,
        "ASSIGNED",
        username=username,
        owner=owner,
        notes=f"Assigned to {owner}",
    )


def implement(recommendation_id: int, username: str, owner: str | None = None) -> bool:
    return transition_workflow_state(
        recommendation_id,
        "IMPLEMENTED",
        username=username,
        owner=owner,
        notes="Implementation started",
    )


def complete(recommendation_id: int, username: str) -> bool:
    return transition_workflow_state(recommendation_id, "CLOSED", username=username, notes="Implementation completed")


def assign_to_workflow(recommendation_id: int, username: str, owner: str) -> bool:
    return assign_owner(recommendation_id, owner, username=username, notes=f"Assigned to {owner}")


def can_transition(current_state: str | None, target_state: str | None) -> bool:
    return can_transition_workflow_state(current_state, target_state)


def can_user_manage(recommendation: dict[str, Any], username: str, action: str = "view") -> bool:
    return can_manage_recommendation(recommendation, username, action=action)


def is_manager_role(role: str | None) -> bool:
    return is_recommendation_manager_role(role)


def list_events(recommendation_id: int, limit: int = 20) -> list[dict[str, Any]]:
    return list_recommendation_events(recommendation_id, limit=limit)


def update_details(
    *,
    recommendation_id: int,
    username: str,
    owner: str | None = None,
    priority: str | None = None,
    due_date: str | None = None,
    clear_owner: bool = False,
    clear_due_date: bool = False,
    notes: str | None = None,
) -> bool:
    return update_recommendation_details(
        recommendation_id=recommendation_id,
        username=username,
        owner=owner,
        priority=priority,
        due_date=due_date,
        clear_owner=clear_owner,
        clear_due_date=clear_due_date,
        notes=notes,
    )


def update_status(
    recommendation_id: int,
    status: str,
    *,
    username: str,
    owner: str | None = None,
    dismiss_reason: str | None = None,
    notes: str | None = None,
) -> bool:
    return update_recommendation_status(
        recommendation_id,
        status,
        username=username,
        owner=owner,
        dismiss_reason=dismiss_reason,
        notes=notes,
    )


def create_recommendation(
    *,
    username: str,
    category: str,
    title: str,
    description: str,
    source: str,
    resource: str | None = None,
    estimated_savings: float | None = None,
    priority: str = "medium",
    confidence_score: float | None = None,
    rationale: str | None = None,
    effort_level: str | None = None,
    action_steps: list[str] | None = None,
) -> Any:
    return save_recommendation(
        username=username,
        category=category,
        title=title,
        description=description,
        source=source,
        resource=resource,
        estimated_savings=estimated_savings,
        priority=priority,
        confidence_score=confidence_score,
        rationale=rationale,
        effort_level=effort_level,
        action_steps=action_steps,
    )

