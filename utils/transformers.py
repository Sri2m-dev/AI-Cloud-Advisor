from __future__ import annotations

import ast
import json
from typing import Any

from shared.recommendation_schema import RECOMMENDATION_SCHEMA_FIELDS, normalize_recommendation_list


RECOMMENDATION_REQUIRED_FIELDS = list(RECOMMENDATION_SCHEMA_FIELDS)
RECOMMENDATION_TYPE_MAP = {
    "id": (str,),
    "cloud": (str,),
    "category": (str,),
    "service": (str,),
    "resource_id": (str,),
    "priority": (str,),
    "savings_monthly": (int, float),
    "risk_score": (int, float),
    "effort_score": (int, float),
    "status": (str,),
    "assigned_to": (str,),
    "created_at": (str,),
    "recommendation": (str,),
    "implementation_steps": (list,),
}

ANOMALY_REQUIRED_FIELDS = ["id", "cloud_provider", "service", "severity", "confidence"]
ANOMALY_TYPE_MAP = {
    "id": (str,),
    "cloud_provider": (str,),
    "service": (str,),
    "service_name": (str,),
    "anomaly_type": (str,),
    "detected_signals": (list,),
    "confidence": (int, float),
    "severity": (str,),
    "current_cost": (int, float),
    "detected_value": (int, float),
    "expected_value": (int, float),
    "score": (int, float),
    "reason": (str,),
}

UNIFIED_CLOUD_COST_REQUIRED_FIELDS = ["cloud", "service_name", "cost"]
UNIFIED_CLOUD_COST_TYPE_MAP = {
    "cloud": (str,),
    "account_name": (str,),
    "service_name": (str,),
    "region": (str,),
    "resource_id": (str, type(None)),
    "usage_date": (str, type(None)),
    "usage_quantity": (int, float),
    "cost": (int, float),
    "currency": (str,),
    "environment": (str, type(None)),
    "application": (str, type(None)),
    "tags": (dict, list, str, type(None)),
}

COSTS_REQUIRED_FIELDS = ["org_id", "cloud", "service_name", "total_cost"]
COSTS_TYPE_MAP = {
    "org_id": (str,),
    "cloud": (str,),
    "service_name": (str,),
    "total_cost": (int, float),
}

GOVERNANCE_SNAPSHOT_REQUIRED_FIELDS = ["id", "org_id", "raw_score", "smoothed_score", "recorded_at"]
GOVERNANCE_SNAPSHOT_TYPE_MAP = {
    "id": (str,),
    "org_id": (str,),
    "tenant_id": (str,),
    "raw_score": (int, float),
    "smoothed_score": (int, float),
    "score_model_version": (str,),
    "weights": (dict,),
    "components": (dict,),
    "recorded_at": (str,),
}

RECOMMENDATION_UPDATE_ALLOWED_FIELDS = {
    "status",
    "approved_at",
    "owner",
    "snoozed_at",
    "snooze_until",
    "completed_at",
}
RECOMMENDATION_UPDATE_TYPE_MAP = {
    "status": (str,),
    "approved_at": (str,),
    "owner": (str,),
    "snoozed_at": (str,),
    "snooze_until": (str,),
    "completed_at": (str,),
}


def clean_api_response(payload: Any, default: Any = None) -> Any:
    """Best-effort parse/clean for malformed API payloads.

    Handles plain dict/list values, JSON strings, fenced JSON, and lightly malformed
    Python-literal-like strings. Returns `default` if parsing fails.
    """
    if payload is None:
        return default

    if isinstance(payload, (dict, list)):
        return payload

    if isinstance(payload, (bytes, bytearray)):
        payload = payload.decode("utf-8", errors="ignore")

    text = str(payload).strip()
    if not text:
        return default

    # Strip markdown code fences if present.
    if text.startswith(""):
        lines = text.splitlines()
        if len(lines) >= 2:
            text = "\n".join(lines[1:-1]).strip()

    # Parse as JSON first.
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Try to recover embedded JSON object/array.
    candidates = []
    obj_l, obj_r = text.find("{"), text.rfind("}")
    if obj_l >= 0 and obj_r > obj_l:
        candidates.append(text[obj_l : obj_r + 1])
    arr_l, arr_r = text.find("["), text.rfind("]")
    if arr_l >= 0 and arr_r > arr_l:
        candidates.append(text[arr_l : arr_r + 1])

    for chunk in candidates:
        try:
            return json.loads(chunk)
        except json.JSONDecodeError:
            continue

    # Last resort: allow Python-literal-ish payloads.
    try:
        parsed = ast.literal_eval(text)
        if isinstance(parsed, (dict, list)):
            return parsed
    except Exception:
        pass

    return default


def normalize_recommendations(payload: Any) -> list[dict[str, Any]]:
    """Normalize recommendation payloads into the canonical schema.

    Accepts one record, list of records, or envelope dict with
    `recommendations` key.
    """
    cleaned = clean_api_response(payload, default=[])
    if isinstance(cleaned, dict):
        items = cleaned.get("recommendations", cleaned)
        if isinstance(items, dict):
            items = [items]
    elif isinstance(cleaned, list):
        items = cleaned
    else:
        items = []

    dict_items = [item for item in items if isinstance(item, dict)]
    return normalize_recommendation_list(dict_items)


def flatten_metrics(payload: Any, parent_key: str = "", sep: str = "_") -> dict[str, Any]:
    """Flatten nested metric dictionaries/lists into a single-level dict."""
    out: dict[str, Any] = {}

    if isinstance(payload, dict):
        for key, value in payload.items():
            next_key = f"{parent_key}{sep}{key}" if parent_key else str(key)
            if isinstance(value, (dict, list)):
                out.update(flatten_metrics(value, next_key, sep=sep))
            else:
                out[next_key] = value
        return out

    if isinstance(payload, list):
        for idx, value in enumerate(payload):
            next_key = f"{parent_key}{sep}{idx}" if parent_key else str(idx)
            if isinstance(value, (dict, list)):
                out.update(flatten_metrics(value, next_key, sep=sep))
            else:
                out[next_key] = value
        return out

    if parent_key:
        out[parent_key] = payload
    return out


def validate_schema(
    payload: dict[str, Any],
    required_fields: list[str] | None = None,
    type_map: dict[str, tuple[type, ...]] | None = None,
    allow_extra: bool = True,
) -> dict[str, Any]:
    """Validate dict payload against required keys and optional type map."""
    record = payload if isinstance(payload, dict) else {}
    required = required_fields or list(RECOMMENDATION_SCHEMA_FIELDS)
    missing = [field for field in required if field not in record]

    type_errors = {}
    for field, expected_types in (type_map or {}).items():
        if field in record and record[field] is not None and not isinstance(record[field], expected_types):
            type_errors[field] = {
                "expected": [t.__name__ for t in expected_types],
                "actual": type(record[field]).__name__,
            }

    unexpected = []
    if not allow_extra:
        expected_set = set(required)
        unexpected = [key for key in record.keys() if key not in expected_set]

    return {
        "valid": not missing and not type_errors and (allow_extra or not unexpected),
        "missing_fields": missing,
        "type_errors": type_errors,
        "unexpected_fields": unexpected,
    }

