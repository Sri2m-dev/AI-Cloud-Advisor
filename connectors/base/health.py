from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


class ConnectorHealthEvaluator:
    @staticmethod
    def evaluate(row: dict[str, Any]) -> dict[str, Any]:
        status = str(row.get("status") or "Not Configured")
        error_count = int(row.get("error_count") or 0)
        records = int(row.get("records_synced") or row.get("objects_synced") or 0)
        last_sync = row.get("last_sync") or row.get("last_sync_at")
        score = 0 if status in {"Not Configured", "DISCONNECTED"} else 95
        if status.upper() in {"FAILED", "ERROR", "UNHEALTHY"}:
            score = 25
        score -= min(error_count * 8, 40)
        if records == 0 and score > 0:
            score -= 10
        if ConnectorHealthEvaluator._is_stale(last_sync):
            score -= 15
        return {
            "status": "Healthy" if score >= 85 else "Degraded" if score >= 50 else "Unhealthy",
            "health_score": max(0, min(100, score)),
            "data_freshness": "Fresh" if not ConnectorHealthEvaluator._is_stale(last_sync) else "Stale",
        }

    @staticmethod
    def _is_stale(value: str | None) -> bool:
        if not value:
            return True
        try:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return (datetime.now(timezone.utc) - parsed).total_seconds() > 24 * 60 * 60
        except Exception:
            return True
