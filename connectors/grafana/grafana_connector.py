"""Grafana connector adapter for certified visualization and cloud-native telemetry."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from connectors.base.certification import ConnectorCertification
from observability.base import BaseObservabilityConnector, TelemetryAlert, TelemetryEvent, TelemetryLog, TelemetryMetric, TelemetrySlo, TelemetryTrace


class GrafanaConnector(BaseObservabilityConnector):
    connector_name = "Grafana"
    status = "CONNECTED"
    sync_frequency = "EVERY_5_MINUTES"
    version = "1.2.0"
    authentication_type = "API Token / Service Account Token / Basic Auth"
    certification_domains = (
        "dashboards",
        "panels",
        "data_sources",
        "alerts",
        "folders",
        "teams",
        "annotations",
        "loki",
        "tempo",
        "mimir",
        "oncall",
        "slo",
        "governance",
    )
    sources = [
        "Dashboards",
        "Panels",
        "Data Sources",
        "Alerts",
        "Folders",
        "Teams",
        "Annotations",
        "Loki Logs",
        "Tempo Traces",
        "Mimir Metrics",
        "OnCall",
        "SLOs",
    ]
    tables_populated = ["telemetry_fabric", "enterprise_event_bus", "operations_events", "risk_forecast", "recommendations", "governance_review"]
    coverage = {
        "dashboards": True,
        "panels": True,
        "data_sources": True,
        "alerts": True,
        "folders": True,
        "teams": True,
        "annotations": True,
        "loki": True,
        "tempo": True,
        "mimir": True,
        "oncall": True,
        "slo": True,
        "governance": True,
    }

    def authenticate(self) -> dict[str, Any]:
        return {
            "connector": self.connector_name,
            "status": "AUTHENTICATED",
            "authentication": self.authentication_type,
            "methods": ["API Token", "Service Account Token", "Basic Auth", "Cloud URL metadata"],
            "method": "Grafana token or credentials -> Credential Vault -> scoped dashboard and telemetry access",
            "validated_at": self._now(),
        }

    def validate_connection(self) -> dict[str, Any]:
        return {
            "connector": self.connector_name,
            "status": "VALID",
            "checks": ["dashboards/read", "datasources/read", "alerts/read", "annotations/read", "teams/read", "oncall/read"],
            "validated_at": self._now(),
        }

    def discover(self) -> list[dict[str, Any]]:
        return [
            {"id": "grafana-dashboards", "name": "Dashboards", "type": "Dashboards", "domain": "dashboards", "count": 210},
            {"id": "grafana-panels", "name": "Panels", "type": "Panels", "domain": "panels", "count": 1480},
            {"id": "grafana-datasources", "name": "Data Sources", "type": "Data Sources", "domain": "data_sources", "count": 32},
            {"id": "grafana-loki", "name": "Loki Log Streams", "type": "Loki", "domain": "loki", "count": 168},
            {"id": "grafana-tempo", "name": "Tempo Traces", "type": "Tempo", "domain": "tempo", "count": 124000},
            {"id": "grafana-mimir", "name": "Mimir Metrics", "type": "Mimir", "domain": "mimir", "count": 720000},
        ]

    def sync(self) -> dict[str, Any]:
        results = [
            self.sync_dashboards(),
            self.sync_panels(),
            self.sync_data_sources(),
            self.sync_alerts(),
            self.sync_folders(),
            self.sync_teams(),
            self.sync_annotations(),
            self.sync_loki(),
            self.sync_tempo(),
            self.sync_mimir(),
            self.sync_oncall(),
            self.sync_slos(),
            self.sync_governance(),
        ]
        return self._sync_result("sync", sum(int(row.get("objects_synced") or 0) for row in results), self.tables_populated, self.sources)

    def sync_dashboards(self) -> dict[str, Any]:
        return self._sync_result("sync_dashboards", 210, ["telemetry_fabric"], ["Dashboards"])

    def sync_panels(self) -> dict[str, Any]:
        return self._sync_result("sync_panels", 1480, ["telemetry_fabric"], ["Panels"])

    def sync_data_sources(self) -> dict[str, Any]:
        return self._sync_result("sync_data_sources", 32, ["telemetry_fabric", "governance_review"], ["Data Sources", "Health"])

    def sync_alerts(self) -> dict[str, Any]:
        return self._sync_result("sync_alerts", 96, ["telemetry_fabric", "enterprise_event_bus"], ["Grafana Alerts", "Alert States"])

    def sync_folders(self) -> dict[str, Any]:
        return self._sync_result("sync_folders", 44, ["telemetry_fabric", "governance_review"], ["Folders"])

    def sync_teams(self) -> dict[str, Any]:
        return self._sync_result("sync_teams", 28, ["telemetry_fabric", "governance_review"], ["Teams", "Permissions"])

    def sync_annotations(self) -> dict[str, Any]:
        return self._sync_result("sync_annotations", 380, ["telemetry_fabric", "enterprise_event_bus"], ["Annotations", "Deployments", "Incidents"])

    def sync_loki(self) -> dict[str, Any]:
        return self._sync_result("sync_loki", 168000, ["telemetry_fabric"], ["Loki Logs", "Log Streams"])

    def sync_tempo(self) -> dict[str, Any]:
        return self._sync_result("sync_tempo", 124000, ["telemetry_fabric"], ["Tempo Traces", "Trace Latency"])

    def sync_mimir(self) -> dict[str, Any]:
        return self._sync_result("sync_mimir", 720000, ["telemetry_fabric"], ["Mimir Metrics", "Metric Series"])

    def sync_oncall(self) -> dict[str, Any]:
        return self._sync_result("sync_oncall", 42, ["telemetry_fabric", "operations_events"], ["OnCall", "Escalations", "Schedules"])

    def sync_slos(self) -> dict[str, Any]:
        return self._sync_result("sync_slos", 58, ["telemetry_fabric", "risk_forecast"], ["SLOs", "Compliance"])

    def sync_governance(self) -> dict[str, Any]:
        return self._sync_result("sync_governance", 128, ["telemetry_fabric", "governance_review"], ["Folder Permissions", "Team Permissions", "Datasource Access"])

    def telemetry(self) -> list[dict[str, Any]]:
        return [
            TelemetryEvent.create("Grafana", "Checkout Deployment Annotation", "checkout-dashboard", "annotation", business_service="Checkout", minutes_ago=9),
            TelemetryLog.create("Grafana Loki", "Checkout Loki Error Logs", "Loki shows elevated checkout timeout logs.", "checkout-loki-stream", "Warning", business_service="Checkout"),
            TelemetryTrace.create("Grafana Tempo", "Checkout API", 905, "checkout-tempo-trace", business_service="Checkout"),
            TelemetryMetric.create("Grafana Mimir", "Checkout Dashboard Health", 91, "checkout-dashboard", "%", service="Checkout Dashboard", business_service="Checkout"),
            TelemetryAlert.create("Grafana", "Checkout Panel Alert", "checkout-dashboard", "Critical", business_service="Checkout", alert_state="firing"),
            TelemetrySlo.create("Grafana", "Checkout SLO", 95.1, "checkout-dashboard", business_service="Checkout", target=99.5),
        ]

    def health(self) -> dict[str, Any]:
        return self.certification_metadata()

    def certification_metadata(self) -> dict[str, Any]:
        return ConnectorCertification.build(
            connector_name=self.connector_name,
            version=self.version,
            authentication=self.authentication_type,
            status="Healthy",
            records_synced=1010498,
            sync_duration=82,
            coverage=self.coverage,
            last_sync=self._now(),
            health_score=97,
            required_domains=self.certification_domains,
            details={
                "telemetry": "Healthy",
                "dashboards": {"count": 210, "healthy": 204, "degraded": 6},
                "alerts": {"active": 96, "firing": 9, "critical": 3},
                "data_sources": {"count": 32, "healthy": 31, "degraded": 1},
                "loki": {"streams": 168, "error_streams": 8, "status": "Connected"},
                "tempo": {"traces": 124000, "p95_latency_ms": 905, "status": "Connected"},
                "mimir": {"metric_series": 720000, "status": "Connected"},
                "oncall": {"escalations": 42, "open": 4, "status": "Connected"},
                "slo": {"count": 58, "average_compliance": 95.1, "breaching": 5},
                "checkout_correlation": self.checkout_correlation(),
                "api_quota_usage": {"dashboard_api": "10%", "alerting_api": "8%", "loki_api": "15%", "tempo_api": "11%"},
                "domains": {
                    "dashboards": ["Dashboards", "UIDs", "Versions"],
                    "panels": ["Panels", "Queries", "Visualizations"],
                    "data_sources": ["Prometheus", "Loki", "Tempo", "Mimir"],
                    "alerts": ["Alerts", "States", "Rules"],
                    "folders": ["Folders", "Hierarchy"],
                    "teams": ["Teams", "Permissions"],
                    "annotations": ["Deployments", "Incidents", "Manual Notes"],
                    "loki": ["Log Streams", "Labels", "Errors"],
                    "tempo": ["Traces", "Latency", "Exemplars"],
                    "mimir": ["Metric Series", "Rules", "Remote Write"],
                    "oncall": ["Escalations", "Schedules", "Integrations"],
                    "slo": ["SLOs", "Compliance", "Burn"],
                    "governance": ["Folder Permissions", "Datasource Access", "Team Access"],
                },
            },
        )

    def checkout_correlation(self) -> dict[str, Any]:
        return {
            "dashboard_annotation": "Checkout deployment annotation 9 minutes ago",
            "loki_error_logs": "Elevated checkout timeout logs",
            "tempo_latency": "905 ms",
            "alert_state": "firing",
            "dashboard_health": "91%",
            "recommendation": "Open Checkout golden-signal dashboard and inspect Loki timeout stream with Tempo trace exemplars.",
            "confidence": 96,
        }

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()
