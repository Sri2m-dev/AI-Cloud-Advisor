from __future__ import annotations

from typing import Any

from connectors.common import BaseConnector


class BaseObservabilityConnector(BaseConnector):
    signal_domains = ("metrics", "logs", "traces", "alerts", "events", "dashboards", "apm", "slo", "governance")

    def discover(self) -> list[dict[str, Any]]:
        return []

    def sync_metrics(self) -> dict[str, Any]:
        return self._sync_result("sync_metrics", 0, ["telemetry_fabric"], ["Metrics"])

    def sync_logs(self) -> dict[str, Any]:
        return self._sync_result("sync_logs", 0, ["telemetry_fabric"], ["Logs"])

    def sync_traces(self) -> dict[str, Any]:
        return self._sync_result("sync_traces", 0, ["telemetry_fabric"], ["Traces"])

    def sync_alerts(self) -> dict[str, Any]:
        return self._sync_result("sync_alerts", 0, ["telemetry_fabric"], ["Alerts"])

    def sync_events(self) -> dict[str, Any]:
        return self._sync_result("sync_events", 0, ["telemetry_fabric"], ["Events"])

    def sync_slos(self) -> dict[str, Any]:
        return self._sync_result("sync_slos", 0, ["telemetry_fabric"], ["SLOs"])

    def telemetry(self) -> list[dict[str, Any]]:
        return []

    def normalize_telemetry(self, records: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
        rows = records or self.telemetry()
        return [
            {
                "source_system": row.get("source") or self.connector_name,
                "signal_type": row.get("signal_type"),
                "entity": row.get("entity"),
                "service": row.get("service"),
                "business_service": row.get("business_service"),
                "metric_name": row.get("name"),
                "metric_value": row.get("value"),
                "severity": row.get("severity"),
                "observed_at": row.get("timestamp"),
                "payload": row,
                "quality_score": 100 if row.get("entity") and row.get("signal_type") else 90,
            }
            for row in rows
        ]
