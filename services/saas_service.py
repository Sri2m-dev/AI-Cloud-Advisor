"""
SaaS service for license, renewal, and vendor spend analytics.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

from services.supabase_client import supabase


ORG_KEYS = ("organization_id", "org_id", "tenant_id")


def _response(data=None, errors=None):
    return {
        "success": errors is None,
        "data": data or [],
        "message": "",
        "errors": errors,
    }


def _to_float(value, default=0.0):
    try:
        if value in (None, ""):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _to_int(value, default=0):
    return int(_to_float(value, default))


def _first(row: dict[str, Any], *keys, default=None):
    for key in keys:
        value = row.get(key)
        if value not in (None, ""):
            return value
    return default


def _parse_date(value):
    if not value:
        return None
    try:
        text = str(value).replace("Z", "+00:00")
        parsed = datetime.fromisoformat(text)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed
    except ValueError:
        return None


def _days_since(value):
    parsed = _parse_date(value)
    if not parsed:
        return None
    return max(0, int((datetime.now(timezone.utc) - parsed).total_seconds() // 86400))


def _days_until(value):
    parsed = _parse_date(value)
    if not parsed:
        return None
    return int((parsed - datetime.now(timezone.utc)).total_seconds() // 86400)


def _matches_org(row: dict[str, Any], org_id):
    if org_id in (None, ""):
        return True
    for key in ORG_KEYS:
        if key in row and str(row.get(key)) == str(org_id):
            return True
    return not any(key in row for key in ORG_KEYS)


def _fetch_table(table_name: str, org_id=None, limit=1000):
    try:
        response = (
            supabase
            .table(table_name)
            .select("*")
            .limit(limit)
            .execute()
        )
        rows = [row for row in response.data or [] if _matches_org(row, org_id)]
        return rows, None
    except Exception as exc:
        return [], f"{table_name}: {exc}"


def _fetch_first_available(table_names: tuple[str, ...], org_id=None):
    errors = []
    for table_name in table_names:
        rows, error = _fetch_table(table_name, org_id=org_id)
        if rows:
            return rows, None
        if error:
            errors.append(error)
    return [], "; ".join(errors) if errors else None


def _vendor(row: dict[str, Any]):
    return str(_first(row, "vendor", "vendor_name", "provider", "supplier", "service_name", default="Unknown"))


def _application(row: dict[str, Any]):
    return str(
        _first(
            row,
            "application",
            "app_name",
            "tool_name",
            "product",
            "software_name",
            "service",
            "service_name",
            default=_vendor(row),
        )
    )


def _category(row: dict[str, Any]):
    category = _first(
        row,
        "category",
        "tool_category",
        "function",
        "department",
    )

    if category:
        return str(category)

    text = " ".join(
        str(value).lower()
        for value in (
            _vendor(row),
            _application(row),
        )
    )

    category_keywords = {
        "Collaboration": [
            "slack",
            "teams",
            "zoom",
            "meet",
            "webex",
            "collaboration",
            "chat",
        ],
        "Project Mgmt": [
            "jira",
            "azure devops",
            "ado",
            "asana",
            "trello",
            "monday",
            "project",
        ],
        "CRM": [
            "salesforce",
            "hubspot",
            "crm",
        ],
        "Productivity": [
            "microsoft 365",
            "office",
            "google workspace",
            "workspace",
            "docs",
        ],
        "Security": [
            "okta",
            "crowdstrike",
            "sentinel",
            "security",
            "sso",
        ],
        "Analytics": [
            "tableau",
            "power bi",
            "looker",
            "analytics",
            "bi",
        ],
    }

    for category_name, keywords in category_keywords.items():
        if any(keyword in text for keyword in keywords):
            return category_name

    return _application(row)


def get_saas_license_utilization(org_id):
    rows, error = _fetch_first_available(
        ("saas_licenses", "license_cost", "saas_subscriptions", "saas_cost"),
        org_id=org_id,
    )
    if error and not rows:
        return _response(errors=error)

    grouped = {}
    for row in rows:
        key = (_vendor(row), _application(row))
        item = grouped.setdefault(
            key,
            {
                "vendor": key[0],
                "application": key[1],
                "total_licenses": 0,
                "assigned_licenses": 0,
                "active_users": 0,
                "monthly_cost": 0.0,
            },
        )
        total = _to_int(_first(row, "total_licenses", "license_count", "purchased_licenses", "licenses_purchased", "seats", "quantity"))
        assigned = _to_int(_first(row, "assigned_licenses", "assigned_seats", "used_licenses", "licenses_used", "licensed_users"))
        active = _to_int(_first(row, "active_users", "utilized_licenses", "usage_count", "users_active"))
        monthly = _to_float(_first(row, "monthly_cost", "cost", "amount", "spend", "total_cost"))

        item["total_licenses"] += total
        item["assigned_licenses"] += assigned or active
        item["active_users"] += active
        item["monthly_cost"] += monthly

    data = []
    for item in grouped.values():
        total = item["total_licenses"]
        active = item["active_users"] or item["assigned_licenses"]
        wasted = max(total - active, 0) if total else 0
        cost_per_license = item["monthly_cost"] / total if total else 0
        item["utilization_pct"] = round((active / total) * 100, 1) if total else 0
        item["wasted_licenses"] = wasted
        item["estimated_waste"] = round(wasted * cost_per_license, 2)
        item["monthly_cost"] = round(item["monthly_cost"], 2)
        data.append(item)

    return _response(sorted(data, key=lambda row: row["estimated_waste"], reverse=True))


def get_inactive_saas_users(org_id):
    rows, error = _fetch_first_available(("saas_users", "saas_license_assignments"), org_id=org_id)
    if error and not rows:
        return _response(errors=error)

    data = []
    for row in rows:
        last_seen = _first(row, "last_login_at", "last_activity_at", "last_used_at", "last_seen_at", "last_active")
        inactive_days = _days_since(last_seen)
        status = str(_first(row, "status", "user_status", default="")).lower()
        is_inactive = status in {"inactive", "disabled", "suspended"} or (inactive_days is not None and inactive_days >= 30)
        if not is_inactive:
            continue
        data.append(
            {
                "user": _first(row, "user_email", "email", "username", "user_id", default="Unknown"),
                "vendor": _vendor(row),
                "application": _application(row),
                "last_activity": last_seen or "N/A",
                "inactive_days": inactive_days if inactive_days is not None else "N/A",
                "monthly_license_cost": _to_float(_first(row, "license_cost", "monthly_cost", "seat_cost")),
            }
        )

    return _response(sorted(data, key=lambda row: row["inactive_days"] if isinstance(row["inactive_days"], int) else -1, reverse=True))


def get_duplicate_saas_tools(org_id):
    rows, error = _fetch_first_available(("saas_tools", "saas_applications", "saas_licenses", "saas_cost"), org_id=org_id)
    if error and not rows:
        return _response(errors=error)

    grouped = defaultdict(list)
    for row in rows:
        grouped[_category(row).lower()].append(row)

    data = []
    for category, tools in grouped.items():
        apps = sorted({_application(row) for row in tools})
        vendors = sorted({_vendor(row) for row in tools})
        if len(apps) < 2 and len(vendors) < 2:
            continue
        monthly_cost = sum(_to_float(_first(row, "monthly_cost", "cost", "amount", "spend", "total_cost")) for row in tools)
        data.append(
            {
                "category": category.title(),
                "tool_count": len(apps),
                "tools": ", ".join(apps),
                "vendors": ", ".join(vendors),
                "monthly_cost": round(monthly_cost, 2),
            }
        )

    return _response(sorted(data, key=lambda row: row["monthly_cost"], reverse=True))


def get_renewal_forecasting(org_id):
    rows, error = _fetch_first_available(("saas_renewals", "saas_contracts", "saas_subscriptions", "saas_licenses"), org_id=org_id)
    if error and not rows:
        return _response(errors=error)

    data = []
    for row in rows:
        renewal_date = _first(row, "renewal_date", "contract_end_date", "expires_at", "current_period_end")
        days_until = _days_until(renewal_date)
        annual_cost = _to_float(_first(row, "annual_cost", "contract_value", "yearly_cost"))
        if not annual_cost:
            annual_cost = _to_float(_first(row, "monthly_cost", "cost", "amount", "spend", "total_cost")) * 12
        data.append(
            {
                "vendor": _vendor(row),
                "application": _application(row),
                "renewal_date": renewal_date or "N/A",
                "days_until_renewal": days_until if days_until is not None else "N/A",
                "annual_cost": round(annual_cost, 2),
                "risk": "High" if days_until is not None and days_until <= 30 else "Medium" if days_until is not None and days_until <= 90 else "Low",
            }
        )

    return _response(sorted(data, key=lambda row: row["days_until_renewal"] if isinstance(row["days_until_renewal"], int) else 99999))


def get_vendor_cost_trends(org_id):
    rows, error = _fetch_first_available(("saas_cost", "saas_spend", "saas_subscriptions"), org_id=org_id)
    if error and not rows:
        return _response(errors=error)

    grouped = defaultdict(float)
    for row in rows:
        period = str(_first(row, "month", "billing_month", "period", "date", "created_at", default="Unknown"))[:10]
        if len(period) >= 7:
            period = period[:7]
        key = (_vendor(row), period)
        grouped[key] += _to_float(_first(row, "cost", "amount", "spend", "total_cost", "monthly_cost"))

    data = [
        {
            "vendor": vendor,
            "period": period,
            "cost": round(cost, 2),
        }
        for (vendor, period), cost in grouped.items()
    ]
    return _response(sorted(data, key=lambda row: (row["vendor"], row["period"])))
