"""
Audit timeline service: business logic for audit timeline,
compliance, and reporting.
"""

from core.errors.error_handler import with_error_handling
from repositories.audit_repository import SupabaseAuditRepository
from services import audit_service
from services.audit_composition import audit_repository

PRIMARY_AUDIT_TABLE = "audit_events"
LEGACY_AUDIT_TABLES = [
    "audit_log",
    "workspace_activity_log",
]


TIMELINE_EVENT_TYPES = {
    "approvals_assignments": [
        "APPROVAL_CREATED",
        "APPROVAL_APPROVED",
        "APPROVAL_REJECTED",
        "APPROVAL_ESCALATED",
        "USER_LOGIN",
        "USER_LOGOUT",
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


def _normalize_legacy_event(row, table_name):
    event_data = {
        "action": row.get("action") or row.get("event") or row.get("activity"),
        "details": row.get("details") or row.get("metadata") or {},
        "status": row.get("status", "Recorded"),
        "legacy_table": table_name,
        "org_id": row.get("org_id") or row.get("organization_id"),
    }

    return {
        "event_type": str(event_data["action"] or "LEGACY_AUDIT_EVENT").upper(),
        "event_source": row.get("category") or row.get("source") or table_name,
        "entity_id": str(row.get("target") or row.get("entity_id") or row.get("id") or ""),
        "actor_id": row.get("user_email") or row.get("user_id") or row.get("actor_id") or "unknown",
        "event_data": event_data,
        "action": event_data["action"],
        "status": event_data["status"],
        "created_at": row.get("created_at")
        or row.get("timestamp")
        or row.get("recorded_at")
        or row.get("updated_at"),
    }


def _legacy_org_matches(row, org_id):
    if not org_id:
        return True

    org_value = str(org_id)
    return str(row.get("org_id") or row.get("organization_id") or "") == org_value


def _event_matches(event, event_types):
    if not event_types:
        return True

    event_type = str(event.get("event_type") or "").upper()
    action = str(event.get("action") or (event.get("event_data") or {}).get("action") or "").upper()

    return event_type in event_types or action in event_types


def _primary_org_matches(row, org_id):
    if not org_id:
        return True

    organization_id = _coerce_org_id(org_id)
    if organization_id is not None:
        return True

    event_data = row.get("event_data") or {}
    return str(event_data.get("org_id") or "") == str(org_id)


def _get_legacy_events(event_types=None, org_id=None, limit=100):
    repository = audit_repository()
    if not isinstance(repository, SupabaseAuditRepository):
        return []
    supabase = repository.client
    legacy_events = []

    for table_name in LEGACY_AUDIT_TABLES:
        try:
            # Legacy audit tables are read-only fallbacks for historical data.
            # New writes go to audit_events through services.audit_service.
            rows = supabase.table(table_name).select("*").limit(limit).execute().data or []
        except Exception:
            continue

        for row in rows:
            if not _legacy_org_matches(row, org_id):
                continue

            event = _normalize_legacy_event(row, table_name)
            if _event_matches(event, event_types):
                legacy_events.append(event)

    legacy_events = sorted(
        legacy_events,
        key=lambda row: str(row.get("created_at") or ""),
        reverse=True,
    )
    return legacy_events[:limit]


def _get_events(event_types=None, org_id=None, limit=100):
    try:
        primary_events = audit_service.get_events(org_id=org_id, limit=limit)
        primary_events = [row for row in primary_events if _event_matches(row, event_types)]
        if primary_events:
            return primary_events

        return _get_legacy_events(
            event_types=event_types,
            org_id=org_id,
            limit=limit,
        )

    except Exception as e:
        print(f"Audit timeline error: {e}")
        return _get_legacy_events(
            event_types=event_types,
            org_id=org_id,
            limit=limit,
        )


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
