"""
Reporting Service
"""

from services.supabase_client import supabase


def _fetch(table_name, limit=1000):
    try:
        response = supabase.table(table_name).select("*").limit(limit).execute()
        return response.data or []
    except Exception:
        return []


def get_executive_summary():
    rows = _fetch("mart_executive_summary", 1)
    return rows[0] if rows else {}


def get_recommendation_summary():
    rows = _fetch("recommendations", 500)

    summary = {}

    for row in rows:
        status = row.get("status", "UNKNOWN")
        summary[status] = summary.get(status, 0) + 1

    return summary


def get_approval_summary():
    rows = _fetch("approval_requests", 500)

    summary = {}

    for row in rows:
        status = row.get("status", "UNKNOWN")
        summary[status] = summary.get(status, 0) + 1

    return summary


def get_saas_summary():
    users = _fetch("saas_users", 500)
    costs = _fetch("saas_cost", 500)

    total_users = len(users)

    total_cost = sum(float(r.get("cost", 0)) for r in costs)

    return {
        "total_users": total_users,
        "total_cost": total_cost,
        "data_available": bool(users or costs),
    }


def get_report_history():
    return _fetch("report_history", 100)
