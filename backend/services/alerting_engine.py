from __future__ import annotations

from datetime import datetime
from typing import Any
import uuid
import logging

import pandas as pd

from backend.services.cost_service import fetch_cost_data
from backend.services.governance_service import get_governance_summary
from backend.services.recommendation_service import get_recommendations
from backend.services.report_service import list_report_history
from backend.services.tenant_scope import scoped_query
from data.supabase_client import supabase

ALERT_CONFIG_TABLE = "alert_configs"
ALERT_HISTORY_TABLE = "alert_history"
logger = logging.getLogger(__name__)

DEFAULT_ALERT_CONFIG = {
    "spend_spike_pct": 25.0,
    "idle_vm_min_savings": 100.0,
    "savings_opportunity_threshold": 500.0,
    "governance_score_drop_threshold": 10.0,
    "governance_score_floor": 70.0,
    "channels": {
        "email": {"enabled": False, "recipients": []},
        "slack": {"enabled": False, "webhook_url": ""},
        "teams": {"enabled": False, "webhook_url": ""},
        "webhook": {"enabled": False, "url": "", "headers": {}},
    },
    "cooldown_minutes": 180,
}


def _utc_now_iso() -> str:
    return datetime.utcnow().isoformat()


def get_alert_config(tenant_id: str) -> dict[str, Any]:
    try:
        rows = (
            scoped_query(supabase, ALERT_CONFIG_TABLE, tenant_id)
            .order("updated_at", desc=True)
            .limit(1)
            .execute()
            .data
            or []
        )
        if rows:
            merged = dict(DEFAULT_ALERT_CONFIG)
            merged.update(rows[0])
            merged["channels"] = {
                **DEFAULT_ALERT_CONFIG["channels"],
                **(rows[0].get("channels") or {}),
            }
            return merged
    except Exception:
        logger.exception("alert_config_load_failed tenant_id=%s", tenant_id)
    return {"org_id": tenant_id, "tenant_id": tenant_id, **DEFAULT_ALERT_CONFIG}


def save_alert_config(tenant_id: str, config: dict[str, Any], updated_by: str) -> dict[str, Any]:
    payload = {
        "id": str(uuid.uuid4()),
        "organization_id": tenant_id,
        "org_id": tenant_id,
        "tenant_id": tenant_id,
        "channels": config.get("channels") or DEFAULT_ALERT_CONFIG["channels"],
        "spend_spike_pct": float(config.get("spend_spike_pct", DEFAULT_ALERT_CONFIG["spend_spike_pct"])),
        "idle_vm_min_savings": float(config.get("idle_vm_min_savings", DEFAULT_ALERT_CONFIG["idle_vm_min_savings"])),
        "savings_opportunity_threshold": float(config.get("savings_opportunity_threshold", DEFAULT_ALERT_CONFIG["savings_opportunity_threshold"])),
        "governance_score_drop_threshold": float(config.get("governance_score_drop_threshold", DEFAULT_ALERT_CONFIG["governance_score_drop_threshold"])),
        "governance_score_floor": float(config.get("governance_score_floor", DEFAULT_ALERT_CONFIG["governance_score_floor"])),
        "cooldown_minutes": int(config.get("cooldown_minutes", DEFAULT_ALERT_CONFIG["cooldown_minutes"])),
        "updated_by": updated_by,
        "updated_at": _utc_now_iso(),
    }
    try:
        supabase.table(ALERT_CONFIG_TABLE).upsert(payload, on_conflict="org_id").execute()
        return {"saved": True, **payload}
    except Exception:
        logger.exception("alert_config_upsert_failed tenant_id=%s", tenant_id)
        return {"saved": False, **payload}


def list_alert_history(tenant_id: str, limit: int = 50) -> list[dict[str, Any]]:
    try:
        return (
            scoped_query(supabase, ALERT_HISTORY_TABLE, tenant_id)
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
            .data
            or []
        )
    except Exception:
        logger.exception("alert_history_load_failed tenant_id=%s limit=%s", tenant_id, limit)
        return []


def record_alert_event(
    tenant_id: str,
    alert_type: str,
    severity: str,
    message: str,
    channels: list[str],
    status: str,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    event = {
        "id": str(uuid.uuid4()),
        "organization_id": tenant_id,
        "org_id": tenant_id,
        "tenant_id": tenant_id,
        "alert_type": alert_type,
        "severity": severity,
        "message": message,
        "channels": channels,
        "status": status,
        "payload": payload or {},
        "created_at": _utc_now_iso(),
    }
    try:
        supabase.table(ALERT_HISTORY_TABLE).insert(event).execute()
        return {"saved": True, **event}
    except Exception:
        logger.exception("alert_event_insert_failed tenant_id=%s alert_type=%s", tenant_id, alert_type)
        return {"saved": False, **event}


def _recent_duplicate(history: list[dict[str, Any]], alert_type: str, cooldown_minutes: int) -> bool:
    if cooldown_minutes <= 0:
        return False
    for item in history:
        if str(item.get("alert_type")) != alert_type:
            continue
        created_at = item.get("created_at")
        if not created_at:
            continue
        try:
            age_minutes = (datetime.utcnow() - datetime.fromisoformat(str(created_at).replace("Z", "+00:00")).replace(tzinfo=None)).total_seconds() / 60.0
        except Exception:
            continue
        if age_minutes <= cooldown_minutes:
            return True
    return False


def _compute_governance_score(tenant_id: str) -> float:
    summary = get_governance_summary(tenant_id=tenant_id)
    anomaly_count = float(summary.get("anomaly_count", 0))
    severity_rows = summary.get("severity_distribution", []) or []
    severity_weight = 0.0
    for row in severity_rows:
        bucket = str(row.get("severity_bucket", "")).lower()
        count = float(row.get("count", 0) or 0)
        if bucket == "critical":
            severity_weight += count * 8.0
        elif bucket == "anomaly":
            severity_weight += count * 5.0
        elif bucket == "warning":
            severity_weight += count * 2.5
    raw_penalty = min(70.0, (anomaly_count * 1.8) + severity_weight)
    return max(0.0, round(100.0 - raw_penalty, 1))


def _build_spend_spike_alert(tenant_id: str, config: dict[str, Any]) -> dict[str, Any] | None:
    payload = fetch_cost_data(tenant_id=tenant_id)
    trend = payload.get("daily_trend") or []
    if len(trend) < 4:
        return None
    df = pd.DataFrame(trend)
    if "cost" not in df.columns:
        return None
    df["cost"] = pd.to_numeric(df["cost"], errors="coerce").fillna(0)
    current_cost = float(df.iloc[-1]["cost"])
    baseline = float(df.iloc[:-1]["cost"].tail(7).mean() or 0)
    if baseline <= 0:
        return None
    spike_pct = ((current_cost - baseline) / baseline) * 100.0
    if spike_pct < float(config.get("spend_spike_pct", 25.0)):
        return None
    return {
        "alert_type": "spend_spike_detected",
        "severity": "high" if spike_pct >= 50 else "medium",
        "message": f"Spend spike detected: current daily spend is {spike_pct:.1f}% above baseline.",
        "payload": {"current_cost": current_cost, "baseline_cost": baseline, "spike_pct": round(spike_pct, 2)},
    }


def _build_idle_vm_alert(tenant_id: str, config: dict[str, Any]) -> dict[str, Any] | None:
    recommendations = get_recommendations(tenant_id=tenant_id)
    matches = []
    threshold = float(config.get("idle_vm_min_savings", 100.0))
    for rec in recommendations:
        text = " ".join([
            str(rec.get("service", "")),
            str(rec.get("message", "")),
            str(rec.get("description", "")),
        ]).lower()
        savings = float(rec.get("estimated_savings", 0) or 0)
        if ("idle" in text or "unused" in text or "vm" in text or "instance" in text) and savings >= threshold:
            matches.append({
                "service": rec.get("service"),
                "message": rec.get("message"),
                "estimated_savings": savings,
            })
    if not matches:
        return None
    top = sorted(matches, key=lambda item: item["estimated_savings"], reverse=True)[0]
    return {
        "alert_type": "idle_vm_found",
        "severity": "medium",
        "message": f"Idle VM found with estimated savings of {top['estimated_savings']:,.2f}.",
        "payload": {"matches": matches[:5]},
    }


def _build_savings_alert(tenant_id: str, config: dict[str, Any]) -> dict[str, Any] | None:
    recommendations = get_recommendations(tenant_id=tenant_id)
    threshold = float(config.get("savings_opportunity_threshold", 500.0))
    high_value = [
        rec for rec in recommendations
        if float(rec.get("estimated_savings", 0) or 0) >= threshold
    ]
    if not high_value:
        return None
    total = sum(float(rec.get("estimated_savings", 0) or 0) for rec in high_value)
    return {
        "alert_type": "savings_opportunity_threshold",
        "severity": "high" if total >= threshold * 3 else "medium",
        "message": f"Savings opportunity exceeds threshold: {len(high_value)} opportunities totaling {total:,.2f}.",
        "payload": {"opportunities": high_value[:10], "total_estimated_savings": round(total, 2)},
    }


def _build_governance_drop_alert(tenant_id: str, config: dict[str, Any], history: list[dict[str, Any]]) -> dict[str, Any] | None:
    current_score = _compute_governance_score(tenant_id=tenant_id)
    prior_score = None
    for item in history:
        if item.get("alert_type") == "governance_score_dropped":
            prior_score = float((item.get("payload") or {}).get("current_score", 0) or 0)
            break
    floor = float(config.get("governance_score_floor", 70.0))
    drop_threshold = float(config.get("governance_score_drop_threshold", 10.0))
    if prior_score is not None and (prior_score - current_score) >= drop_threshold:
        return {
            "alert_type": "governance_score_dropped",
            "severity": "high" if current_score < floor else "medium",
            "message": f"Governance score dropped from {prior_score:.1f} to {current_score:.1f}.",
            "payload": {"previous_score": prior_score, "current_score": current_score, "score_drop": round(prior_score - current_score, 2)},
        }
    if current_score < floor:
        return {
            "alert_type": "governance_score_dropped",
            "severity": "high",
            "message": f"Governance score dropped below threshold: {current_score:.1f}.",
            "payload": {"previous_score": prior_score, "current_score": current_score, "score_drop": None},
        }
    return None


def evaluate_alerts(tenant_id: str) -> list[dict[str, Any]]:
    config = get_alert_config(tenant_id=tenant_id)
    history = list_alert_history(tenant_id=tenant_id, limit=100)
    candidates = [
        _build_spend_spike_alert(tenant_id, config),
        _build_idle_vm_alert(tenant_id, config),
        _build_savings_alert(tenant_id, config),
        _build_governance_drop_alert(tenant_id, config, history),
    ]
    alerts = []
    cooldown = int(config.get("cooldown_minutes", 180) or 0)
    for item in candidates:
        if not item:
            continue
        if _recent_duplicate(history, item["alert_type"], cooldown):
            continue
        alerts.append(item)
    return alerts

