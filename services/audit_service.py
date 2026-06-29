"""
Audit Service - Centralized event logging and audit trail management.
"""

from typing import Optional, List, Dict, Any
from datetime import datetime
from services.supabase_client import supabase

PRIMARY_AUDIT_TABLE = "audit_events"


def _legacy_organization_id(org_id: Optional[str]) -> int:
    return int(org_id) if str(org_id).isdigit() else 1


def _event_org_matches(row: Dict[str, Any], org_id: Optional[str]) -> bool:
    if not org_id or str(org_id).isdigit():
        return True

    event_data = row.get("event_data") or {}
    return str(event_data.get("org_id") or "") == str(org_id)


def log_event(
    event_type: str,
    user_id: str,
    action: str,
    resource_type: str,
    resource_id: str,
    org_id: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
    status: str = "success",
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None
) -> Dict[str, Any]:

    try:
        audit_record = {
            "organization_id": _legacy_organization_id(org_id),
            "event_type": event_type,
            "event_source": resource_type,
            "entity_id": str(resource_id),
            "actor_id": int(user_id) if str(user_id).isdigit() else 1,
            "event_data": {
                "action": action,
                "details": details or {},
                "status": status,
                "user_id": str(user_id),
                "org_id": str(org_id or ""),
                "ip_address": ip_address,
                "user_agent": user_agent
            },
            "created_at": datetime.utcnow().isoformat()
        }

        response = (
            supabase
            .table(PRIMARY_AUDIT_TABLE)
            .insert(audit_record)
            .execute()
        )

        if response.data:
            return response.data[0]

        return {"error": "No data returned"}

    except Exception as e:
        import traceback

        print("=" * 80)
        print("AUDIT INSERT FAILED")
        print(traceback.format_exc())
        print("=" * 80)

        return {"error": str(e)}


def get_events(
    org_id: Optional[str] = None,
    event_type: Optional[str] = None,
    limit: int = 100
) -> List[Dict[str, Any]]:

    try:
        query = supabase.table(PRIMARY_AUDIT_TABLE).select("*")

        if org_id and str(org_id).isdigit():
            query = query.eq("organization_id", _legacy_organization_id(org_id))

        if event_type:
            query = query.eq("event_type", event_type)

        response = (
            query
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )

        rows = response.data or []
        return [
            row
            for row in rows
            if _event_org_matches(row, org_id)
        ]

    except Exception as e:
        print(f"Error fetching audit events: {e}")
        return []


def get_user_events(user_id: str, limit: int = 100):
    events = get_events(limit=limit)
    return [
        e for e in events
        if str(e.get("actor_id")) == str(user_id)
    ]


def get_org_events(
    org_id: str,
    event_type: Optional[str] = None,
    limit: int = 100
):
    return get_events(
        org_id=org_id,
        event_type=event_type,
        limit=limit
    )


def get_resource_events(
    resource_type: str,
    resource_id: str,
    limit: int = 100
):

    try:
        response = (
            supabase
            .table(PRIMARY_AUDIT_TABLE)
            .select("*")
            .eq("event_source", resource_type)
            .eq("entity_id", str(resource_id))
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )

        return response.data if response.data else []

    except Exception as e:
        print(f"Error fetching resource events: {e}")
        return []


# Approval Events

def log_approval_created(approval_id, created_by, org_id, title, **kwargs):
    return log_event(
        event_type="APPROVAL_CREATED",
        user_id=created_by,
        action="created",
        resource_type="approval",
        resource_id=approval_id,
        org_id=org_id,
        details={
            "title": title,
            "approval_type": kwargs.get("approval_type"),
            "priority": kwargs.get("priority")
        }
    )


def log_approval_approved(approval_id, approved_by, org_id, comments=None, **kwargs):
    return log_event(
        event_type="APPROVAL_APPROVED",
        user_id=approved_by,
        action="approved",
        resource_type="approval",
        resource_id=approval_id,
        org_id=org_id,
        details={"comments": comments}
    )


def log_approval_rejected(approval_id, rejected_by, org_id, reason=None, **kwargs):
    return log_event(
        event_type="APPROVAL_REJECTED",
        user_id=rejected_by,
        action="rejected",
        resource_type="approval",
        resource_id=approval_id,
        org_id=org_id,
        details={"reason": reason}
    )


def log_approval_escalated(
    approval_id,
    escalated_by,
    escalated_to,
    org_id,
    reason=None,
    **kwargs
):
    return log_event(
        event_type="APPROVAL_ESCALATED",
        user_id=escalated_by,
        action="escalated",
        resource_type="approval",
        resource_id=approval_id,
        org_id=org_id,
        details={
            "escalated_to": escalated_to,
            "reason": reason
        }
    )


def log_policy_created(policy_id, created_by, org_id, policy_name=None, **kwargs):
    return log_event(
        event_type="POLICY_CREATED",
        user_id=created_by,
        action="created",
        resource_type="policy",
        resource_id=policy_id,
        org_id=org_id,
        details={
            "policy_name": policy_name,
            **kwargs,
        },
    )


def log_policy_updated(policy_id, updated_by, org_id, policy_name=None, changes=None, **kwargs):
    return log_event(
        event_type="POLICY_UPDATED",
        user_id=updated_by,
        action="updated",
        resource_type="policy",
        resource_id=policy_id,
        org_id=org_id,
        details={
            "policy_name": policy_name,
            "changes": changes or {},
            **kwargs,
        },
    )


def log_status_changed(
    resource_id,
    changed_by,
    org_id,
    resource_type="workflow",
    old_status=None,
    new_status=None,
    notes=None,
    **kwargs
):
    return log_event(
        event_type="STATUS_CHANGED",
        user_id=changed_by,
        action="status_changed",
        resource_type=resource_type,
        resource_id=resource_id,
        org_id=org_id,
        details={
            "old_status": old_status,
            "new_status": new_status,
            "notes": notes,
            **kwargs,
        },
    )


def log_workflow_changed(
    workflow_id,
    changed_by,
    org_id,
    old_state=None,
    new_state=None,
    notes=None,
    **kwargs
):
    return log_event(
        event_type="WORKFLOW_CHANGED",
        user_id=changed_by,
        action="workflow_changed",
        resource_type="workflow",
        resource_id=workflow_id,
        org_id=org_id,
        details={
            "old_state": old_state,
            "new_state": new_state,
            "notes": notes,
            **kwargs,
        },
    )


def log_recommendation_accepted(recommendation_id, accepted_by, org_id, **kwargs):
    return log_event(
        event_type="RECOMMENDATION_ACCEPTED",
        user_id=accepted_by,
        action="accepted",
        resource_type="recommendation",
        resource_id=recommendation_id,
        org_id=org_id,
        details=kwargs,
    )


def log_recommendation_rejected(recommendation_id, rejected_by, org_id, reason=None, **kwargs):
    return log_event(
        event_type="RECOMMENDATION_REJECTED",
        user_id=rejected_by,
        action="rejected",
        resource_type="recommendation",
        resource_id=recommendation_id,
        org_id=org_id,
        details={
            "reason": reason,
            **kwargs,
        },
    )


def log_kpi_updated(kpi_id, updated_by, org_id, old_value=None, new_value=None, **kwargs):
    return log_event(
        event_type="KPI_UPDATED",
        user_id=updated_by,
        action="updated",
        resource_type="kpi",
        resource_id=kpi_id,
        org_id=org_id,
        details={
            "old_value": old_value,
            "new_value": new_value,
            **kwargs,
        },
    )


def log_alert_triggered(alert_id, triggered_by, org_id, title=None, severity=None, **kwargs):
    return log_event(
        event_type="ALERT_TRIGGERED",
        user_id=triggered_by,
        action="triggered",
        resource_type="alert",
        resource_id=alert_id,
        org_id=org_id,
        details={
            "title": title,
            "severity": severity,
            **kwargs,
        },
    )


def log_report_generated(report_id, generated_by, org_id, report_type=None, **kwargs):
    return log_event(
        event_type="REPORT_GENERATED",
        user_id=generated_by,
        action="generated",
        resource_type="report",
        resource_id=report_id,
        org_id=org_id,
        details={
            "report_type": report_type,
            **kwargs,
        },
    )


def log_user_logout(user_id=None, username=None, organization_id=None, org_id=None, **kwargs):
    organization = organization_id or org_id or 1

    return log_event(
        event_type="USER_LOGOUT",
        user_id=str(user_id or username or 1),
        action="logout",
        resource_type="authentication",
        resource_id=str(username or user_id or "unknown"),
        org_id=organization,
        details={
            "username": username or user_id,
            **kwargs,
        },
        status="success",
    )


def get_audit_logs(org_id=None, limit=100):
    return get_events(org_id=org_id, limit=limit)

def log_user_login(
    user_id=None,
    username=None,
    organization_id=None,
    org_id=None,
    **kwargs
):
    try:
        organization = organization_id or org_id or 1
        actor = str(user_id or username or 1)

        return log_event(
            event_type="USER_LOGIN",
            user_id=actor,
            action="login",
            resource_type="authentication",
            resource_id=str(username or user_id or "unknown"),
            org_id=organization,
            details={
                "username": username or user_id,
                **kwargs,
            },
            status="success"
        )

    except Exception as e:
        print(f"Audit login error: {e}")
        return False
