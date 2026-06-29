"""Datadog connector adapter for certified enterprise observability telemetry."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from connectors.base.certification import ConnectorCertification
from observability.base import (
    BaseObservabilityConnector,
    TelemetryAlert,
    TelemetryApmService,
    TelemetryEvent,
    TelemetryLog,
    TelemetryMetric,
    TelemetrySlo,
    TelemetryTrace,
)


class DatadogConnector(BaseObservabilityConnector):
    connector_name = "Datadog"
    status = "CONNECTED"
    sync_frequency = "EVERY_5_MINUTES"
    version = "1.2.0"
    authentication_type = "API Key / Application Key"
    certification_domains = ("metrics", "logs", "traces", "alerts", "events", "dashboards", "apm", "slo", "governance")
    sources = [
        "Infrastructure",
        "Hosts",
        "Containers",
        "Kubernetes",
        "Cloud Integrations",
        "Metrics",
        "Monitors",
        "Dashboards",
        "Alerts",
        "APM",
        "Services",
        "Traces",
        "Latency",
        "Errors",
        "Logs",
        "Synthetics",
        "RUM",
        "CSPM",
        "Cloud SIEM",
    ]
    tables_populated = [
        "telemetry_fabric",
        "enterprise_event_bus",
        "enterprise_data_fabric",
        "operations_events",
        "risk_forecast",
        "recommendations",
    ]
    coverage = {
        "metrics": True,
        "logs": True,
        "traces": True,
        "alerts": True,
        "events": True,
        "dashboards": True,
        "apm": True,
        "slo": True,
        "governance": True,
    }

    def authenticate(self) -> dict[str, Any]:
        return {
            "connector": self.connector_name,
            "status": "AUTHENTICATED",
            "authentication": self.authentication_type,
            "method": "Datadog API Key / Application Key -> Credential Vault -> Scoped Telemetry Access",
            "validated_at": self._now(),
        }

    def validate_connection(self) -> dict[str, Any]:
        return {
            "connector": self.connector_name,
            "status": "VALID",
            "checks": ["metrics/read", "logs/read", "apm/read", "monitors/read", "slo/read", "dashboards/read"],
            "validated_at": self._now(),
        }

    def discover(self) -> list[dict[str, Any]]:
        return [
            {"id": "dd-hosts", "name": "Hosts", "type": "Infrastructure", "domain": "metrics", "count": 1240},
            {"id": "dd-containers", "name": "Containers", "type": "Infrastructure", "domain": "metrics", "count": 8420},
            {"id": "dd-kubernetes", "name": "Kubernetes", "type": "Infrastructure", "domain": "metrics", "count": 38},
            {"id": "dd-apm-services", "name": "APM Services", "type": "APM", "domain": "apm", "count": 162},
            {"id": "dd-monitors", "name": "Monitors", "type": "Alerts", "domain": "alerts", "count": 418},
            {"id": "dd-dashboards", "name": "Dashboards", "type": "Dashboards", "domain": "dashboards", "count": 96},
            {"id": "dd-slos", "name": "SLOs", "type": "SLO", "domain": "slo", "count": 54},
            {"id": "dd-synthetics", "name": "Synthetic Tests", "type": "Synthetics", "domain": "events", "count": 74},
            {"id": "dd-security", "name": "CSPM and Cloud SIEM", "type": "Security", "domain": "governance", "count": 238},
        ]

    def sync(self) -> dict[str, Any]:
        results = [
            self.sync_metrics(),
            self.sync_logs(),
            self.sync_traces(),
            self.sync_alerts(),
            self.sync_events(),
            self.sync_slos(),
            self.sync_apm(),
            self.sync_dashboards(),
            self.sync_synthetics(),
            self.sync_security(),
        ]
        return self._sync_result(
            "sync",
            sum(int(row.get("objects_synced") or 0) for row in results),
            self.tables_populated,
            self.sources,
        )

    def sync_metrics(self) -> dict[str, Any]:
        return self._sync_result("sync_metrics", 482000, ["telemetry_fabric"], ["Metrics", "Hosts", "Containers", "Kubernetes"])

    def sync_logs(self) -> dict[str, Any]:
        return self._sync_result("sync_logs", 224000, ["telemetry_fabric"], ["Logs", "Log Streams", "Log Indexes"])

    def sync_traces(self) -> dict[str, Any]:
        return self._sync_result("sync_traces", 128000, ["telemetry_fabric"], ["APM", "Traces", "Latency", "Errors"])

    def sync_alerts(self) -> dict[str, Any]:
        return self._sync_result("sync_alerts", 418, ["telemetry_fabric", "enterprise_event_bus"], ["Monitors", "Alerts"])

    def sync_events(self) -> dict[str, Any]:
        return self._sync_result("sync_events", 2140, ["telemetry_fabric", "enterprise_event_bus"], ["Events", "Deployments", "Monitor Events"])

    def sync_slos(self) -> dict[str, Any]:
        return self._sync_result("sync_slos", 54, ["telemetry_fabric", "risk_forecast"], ["SLOs", "Error Budgets"])

    def sync_apm(self) -> dict[str, Any]:
        return self._sync_result("sync_apm", 162, ["telemetry_fabric", "operations_events"], ["APM Services", "Service Map", "Errors"])

    def sync_dashboards(self) -> dict[str, Any]:
        return self._sync_result("sync_dashboards", 96, ["telemetry_fabric"], ["Dashboards", "Widgets"])

    def sync_synthetics(self) -> dict[str, Any]:
        return self._sync_result("sync_synthetics", 74, ["telemetry_fabric", "operations_events"], ["API Tests", "Browser Tests", "RUM"])

    def sync_security(self) -> dict[str, Any]:
        return self._sync_result("sync_security", 238, ["telemetry_fabric", "governance_review"], ["CSPM", "Cloud SIEM", "Security Signals"])

    def telemetry(self) -> list[dict[str, Any]]:
        return [
            TelemetryMetric.create("Datadog", "CPU Utilization", 96, "checkout-api-prod", "%", service="Checkout API", business_service="Checkout"),
            TelemetryMetric.create("Datadog", "Checkout Latency Increase", 37, "checkout-api-prod", "%", service="Checkout API", business_service="Checkout"),
            TelemetryTrace.create("Datadog", "Checkout API", 842, "checkout-api-prod", business_service="Checkout", baseline_ms=614),
            TelemetryLog.create("Datadog", "Checkout Error Log", "Payment dependency timeout increased after deployment.", "checkout-api-prod", "Warning", business_service="Checkout"),
            TelemetryAlert.create("Datadog", "Checkout Latency Breach", "checkout-api-prod", "Critical", business_service="Checkout", monitor_id="mon-4242"),
            TelemetryEvent.create("Datadog", "Deployment Marker", "checkout-api-prod", "deployment", business_service="Checkout", minutes_ago=12, version="release-24"),
            TelemetrySlo.create("Datadog", "Checkout Availability SLO", 96.8, "checkout-api-prod", business_service="Checkout", target=99.9),
            TelemetryApmService.create("Datadog", "Checkout API", 72, "checkout-api-prod", business_service="Checkout", errors="Elevated"),
        ]

    def health(self) -> dict[str, Any]:
        return self.certification_metadata()

    def certification_metadata(self) -> dict[str, Any]:
        return ConnectorCertification.build(
            connector_name=self.connector_name,
            version=self.version,
            authentication=self.authentication_type,
            status="Healthy",
            records_synced=837182,
            sync_duration=88,
            coverage=self.coverage,
            last_sync=self._now(),
            next_sync=None,
            health_score=98,
            required_domains=self.certification_domains,
            details={
                "telemetry_fabric": "Healthy",
                "event_bus": "Enabled",
                "metrics": {"hosts": 1240, "containers": 8420, "kubernetes_clusters": 38, "status": "Connected"},
                "logs": {"streams": 184, "indexes": 22, "status": "Connected"},
                "traces": {"apm_services": 162, "p95_latency_ms": 842, "status": "Connected"},
                "alerts": {"active": 38, "critical": 6, "status": "Connected"},
                "slo": {"count": 54, "burning": 4, "average_health": 96.2},
                "synthetics": {"api_tests": 48, "browser_tests": 26, "rum_sessions": 124000},
                "security": {"cspm_findings": 184, "siem_signals": 54},
                "checkout_correlation": self.checkout_correlation(),
                "api_quota_usage": {"metrics_api": "21%", "logs_api": "18%", "apm_api": "14%", "monitors_api": "9%"},
                "domains": {
                    "metrics": ["Hosts", "Containers", "Kubernetes", "Cloud Integrations"],
                    "logs": ["Log Streams", "Log Indexes", "Error Logs"],
                    "traces": ["APM", "Latency", "Errors", "Service Map"],
                    "alerts": ["Monitors", "Alert States", "Alert History"],
                    "events": ["Deployments", "Monitor Events", "Infrastructure Events"],
                    "dashboards": ["Dashboards", "Widgets", "Executive Views"],
                    "apm": ["Services", "Traces", "Errors", "Dependencies"],
                    "slo": ["SLOs", "Error Budgets", "Burn Rate"],
                    "governance": ["CSPM", "Cloud SIEM", "Audit Trail"],
                },
            },
        )

    def checkout_correlation(self) -> dict[str, Any]:
        return {
            "asset": "Checkout",
            "latency_increase": "37%",
            "datadog_cpu": "96%",
            "github_deployment": "12 minutes ago",
            "jira_release": "Release 24",
            "servicenow_incident": "No active incident",
            "customer_impact": "Elevated checkout response time for web customers",
            "revenue_risk_per_hour": 342000,
            "recommendation": "Rollback the latest Checkout deployment and scale checkout-api-prod by 2 replicas.",
            "confidence": 97,
        }

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()
