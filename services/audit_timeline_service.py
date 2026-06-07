"""
Audit timeline service: business logic for audit timeline,
compliance, and reporting.
"""

from services.supabase_client import supabase
from core.errors.error_handler import with_error_handling


TIMELINE_EVENT_TYPES = {
    "approvals_assignments": [
        "APPROVAL_CREATED",
        "APPROVAL_APPROVED",
        "APPROVAL_REJECTED",
        "APPROVAL_ESCALATED",
        "USER_LOGIN",
    ],
    "governance_changes": [
        "POLICY_CREATED",
        "POLICY_UPDATED",
    ],
    "workflow_transitions": [
        "STATUS_CHANGED",
        "WORKFLOW_CHANGED",
    ],
    "ai_recommendation_actions": [
        "RECOMMENDATION_ACCEPTED",
        "RECOMMENDATION_REJECTED",
    ],
    "kpi_changes": [
        "KPI_UPDATED",
    ],
    "alerts_reports": [
        "ALERT_TRIGGERED",
        "REPORT_GENERATED",
    ],
}


def _coerce_org_id(org_id):
    return int(org_id) if str(org_id).isdigit() else None


def _get_events(event_types=None, org_id=None, limit=100):
    try:
        query = (
            supabase
            .table("audit_events")
            .select("*")
        )

        organization_id = _coerce_org_id(org_id)
        if organization_id is not None:
            query = query.eq("organization_id", organization_id)

        if event_types:
            query = query.in_("event_type", event_types)

        response = (
            query
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )

        return response.data or []

    except Exception as e:
        print(f"Audit timeline error: {e}")
        return []


@with_error_handling
def get_approvals_assignments_timeline(org_id):

    events = _get_events(
        TIMELINE_EVENT_TYPES["approvals_assignments"],
        org_id=org_id,
    )

    return {
        "success": True,
        "data": events,
        "message": "",
        "errors": None,
    }


@with_error_handling
def get_governance_changes_timeline(org_id):

    events = _get_events(
        TIMELINE_EVENT_TYPES["governance_changes"],
        org_id=org_id,
    )

    return {
        "success": True,
        "data": events,
        "message": "",
        "errors": None,
    }


@with_error_handling
def get_workflow_transitions_timeline(org_id):

    events = _get_events(
        TIMELINE_EVENT_TYPES["workflow_transitions"],
        org_id=org_id,
    )

    return {
        "success": True,
        "data": events,
        "message": "",
        "errors": None,
    }


@with_error_handling
def get_ai_recommendation_actions_timeline(org_id):

    events = _get_events(
        TIMELINE_EVENT_TYPES["ai_recommendation_actions"],
        org_id=org_id,
    )

    return {
        "success": True,
        "data": events,
        "message": "",
        "errors": None,
    }


@with_error_handling
def get_kpi_changes_timeline(org_id):

    events = _get_events(
        TIMELINE_EVENT_TYPES["kpi_changes"],
        org_id=org_id,
    )

    return {
        "success": True,
        "data": events,
        "message": "",
        "errors": None,
    }


@with_error_handling
def get_alerts_reports_timeline(org_id):

    events = _get_events(
        TIMELINE_EVENT_TYPES["alerts_reports"],
        org_id=org_id,
    )

    return {
        "success": True,
        "data": events,
        "message": "",
        "errors": None,
    }
