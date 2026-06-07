from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


RECOMMENDATION_SCHEMA_FIELDS = [
    "id",
    "cloud",
    "category",
    "service",
    "resource_id",
    "priority",
    "savings_monthly",
    "risk_score",
    "effort_score",
    "status",
    "assigned_to",
    "created_at",
    "recommendation",
    "implementation_steps",
]


def _as_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _priority(value: Any) -> str:
    normalized = str(value or "medium").strip().lower()
    if normalized in {"high", "medium", "low"}:
        return normalized
    if normalized in {"critical", "urgent"}:
        return "high"
    return "medium"


def _status(value: Any) -> str:
    normalized = str(value or "new").strip().lower()
    mapping = {
        "pending": "new",
        "approved": "accepted",
        "done": "completed",
    }
    return mapping.get(normalized, normalized or "new")


def _cloud(value: Any) -> str:
    normalized = str(value or "").strip().lower()
    if normalized in {"aws", "amazon web services", "amazon"}:
        return "AWS"
    if normalized in {"azure", "microsoft azure"}:
        return "Azure"
    if normalized in {"gcp", "google cloud", "google cloud platform"}:
        return "GCP"
    return str(value or "") or "Unknown"


def _effort_score(value: Any, effort_level: Any = None) -> float:
    numeric = _as_float(value, default=-1)
    if numeric >= 0:
        return numeric
    level = str(effort_level or "").strip().lower()
    return {
        "low": 2.0,
        "medium": 5.0,
        "high": 8.0,
    }.get(level, 0.0)


def _steps(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(step) for step in value if str(step).strip()]
    if isinstance(value, tuple):
        return [str(step) for step in value if str(step).strip()]
    if value is None:
        return []
    text = str(value).strip()
    return [text] if text else []


def normalize_recommendation(payload: dict[str, Any]) -> dict[str, Any]:
    """Normalize recommendation payloads to one canonical schema."""
    payload = payload or {}
    created_at = str(payload.get("created_at") or payload.get("generated_at") or "").strip()
    if not created_at:
        created_at = datetime.now(timezone.utc).isoformat(timespec="seconds")

    recommendation_text = (
        payload.get("recommendation")
        or payload.get("message")
        or payload.get("description")
        or payload.get("title")
        or ""
    )

    normalized = {
        "id": str(payload.get("id") or "").strip(),
        "cloud": _cloud(payload.get("cloud") or payload.get("provider") or payload.get("cloud_provider")),
        "category": str(payload.get("category") or payload.get("type") or "general").strip().lower(),
        "service": str(payload.get("service") or payload.get("service_name") or "Unknown").strip(),
        "resource_id": str(
            payload.get("resource_id")
            or payload.get("resource")
            or payload.get("account_identifier")
            or ""
        ).strip(),
        "priority": _priority(payload.get("priority") or payload.get("impact")),
        "savings_monthly": round(
            _as_float(payload.get("savings_monthly", payload.get("estimated_savings", 0.0))),
            2,
        ),
        "risk_score": round(_as_float(payload.get("risk_score"), 0.0), 2),
        "effort_score": round(_effort_score(payload.get("effort_score"), payload.get("effort_level")), 2),
        "status": _status(payload.get("status")),
        "assigned_to": str(payload.get("assigned_to") or payload.get("owner") or "").strip(),
        "created_at": created_at,
        "recommendation": str(recommendation_text).strip(),
        "implementation_steps": _steps(payload.get("implementation_steps", payload.get("action_steps"))),
    }
    return normalized


def with_legacy_aliases(normalized: dict[str, Any]) -> dict[str, Any]:
    """Expose legacy keys temporarily so existing UI paths do not break."""
    rec = dict(normalized)
    rec["impact"] = str(rec.get("priority") or "medium").upper()
    rec["estimated_savings"] = rec.get("savings_monthly", 0.0)
    rec["owner"] = rec.get("assigned_to") or None
    rec["message"] = rec.get("recommendation", "")
    rec["description"] = rec.get("recommendation", "")
    rec["action_steps"] = rec.get("implementation_steps", [])
    rec["resource"] = rec.get("resource_id", "")
    rec["provider"] = rec.get("cloud", "")
    return rec


def normalize_recommendation_list(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [with_legacy_aliases(normalize_recommendation(item)) for item in (items or [])]

