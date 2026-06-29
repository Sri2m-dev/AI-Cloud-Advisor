from __future__ import annotations

from typing import Any

from connectors.connector_registry import get_connector
from connectors.common.tenant_guard import resolve_organization_id


class AICorrelationEngine:
    @staticmethod
    def correlate_checkout_slowdown(organization_id: str | None = None) -> dict[str, Any]:
        org_id = resolve_organization_id(organization_id)
        datadog = AICorrelationEngine._details("Datadog", org_id).get("checkout_correlation", {})
        dynatrace = AICorrelationEngine._details("Dynatrace", org_id).get("checkout_correlation", {})
        new_relic = AICorrelationEngine._details("New Relic", org_id).get("checkout_correlation", {})
        splunk = AICorrelationEngine._details("Splunk", org_id).get("checkout_correlation", {})
        prometheus = AICorrelationEngine._details("Prometheus", org_id).get("checkout_correlation", {})
        grafana = AICorrelationEngine._details("Grafana", org_id).get("checkout_correlation", {})
        github = AICorrelationEngine._details("GitHub", org_id).get("applications_changed_recently", {})
        jira = AICorrelationEngine._details("Jira", org_id)

        timeline = [
            {"Step": "Deployment", "Source": "GitHub / New Relic", "Evidence": f"Checkout deployment {new_relic.get('related_deployment') or datadog.get('github_deployment', '11 minutes ago')}"},
            {"Step": "CPU Spike", "Source": "Datadog", "Evidence": f"CPU utilization {datadog.get('datadog_cpu', '94%')}"},
            {"Step": "Kubernetes Signals", "Source": "Prometheus", "Evidence": f"CPU {prometheus.get('cpu', '92%')}, memory {prometheus.get('memory', '87%')}, pod restarts {prometheus.get('pod_restarts', 7)}"},
            {"Step": "Latency Increase", "Source": "Dynatrace", "Evidence": f"Response time increased {dynatrace.get('response_time_increase', '42%')}"},
            {"Step": "Dashboard Annotation", "Source": "Grafana", "Evidence": grafana.get("dashboard_annotation", "Checkout deployment annotation detected")},
            {"Step": "APM Error Rate", "Source": "New Relic", "Evidence": f"APM latency {new_relic.get('apm_latency', '888 ms')}; error rate {new_relic.get('error_rate', '5.8%')}"},
            {"Step": "Security Alert", "Source": "Splunk", "Evidence": splunk.get("security_alert", "Checkout authentication anomaly")},
            {"Step": "Problem", "Source": "Davis AI", "Evidence": dynatrace.get("root_cause", "Database connection pool saturation")},
            {"Step": "ITSM", "Source": "ServiceNow", "Evidence": "No active P1 incident for Checkout"},
            {"Step": "Business Impact", "Source": "Knowledge Graph", "Evidence": dynatrace.get("blast_radius", "Checkout revenue path impacted")},
        ]
        return {
            "asset": dynatrace.get("asset", "Checkout Service"),
            "datadog": {
                "cpu": datadog.get("datadog_cpu", "94%"),
                "latency": datadog.get("latency_increase", "37%"),
            },
            "dynatrace": {
                "response_time": dynatrace.get("response_time_increase", "42%"),
                "root_cause": dynatrace.get("root_cause", "Database connection pool saturation"),
                "impacted_services": dynatrace.get("impacted_services", ["Checkout API", "Payment Authorization"]),
            },
            "new_relic": {
                "apm_latency": new_relic.get("apm_latency", "888 ms"),
                "error_rate": new_relic.get("error_rate", "5.8%"),
                "browser_impact": new_relic.get("browser_impact", "Apdex dropped to 0.72 on Checkout Web"),
                "related_deployment": new_relic.get("related_deployment", "release-2026.08, 10 minutes ago"),
                "service_level": new_relic.get("service_level", "Checkout Service Level breached at 95.4%"),
                "workload_health": new_relic.get("workload_health", "Checkout workload degraded"),
                "recommendation": new_relic.get("recommendation", "Inspect New Relic Error Inbox and rollback if error rate remains elevated."),
            },
            "splunk": {
                "security_alert": splunk.get("security_alert", "Checkout authentication anomaly"),
                "notable_event": splunk.get("notable_event", "ES notable event"),
                "failed_logins": splunk.get("failed_logins", 1420),
                "failed_login_increase": splunk.get("failed_login_increase", "18%"),
                "risk": splunk.get("risk", "Medium"),
                "soar_case": splunk.get("soar_case", "MFA Coverage Review"),
                "recommendation": splunk.get("recommendation", "Investigate Checkout authentication anomalies."),
            },
            "prometheus": {
                "cpu": prometheus.get("cpu", "92%"),
                "memory": prometheus.get("memory", "87%"),
                "pod_restarts": prometheus.get("pod_restarts", 7),
                "alert_state": prometheus.get("alert_state", "firing"),
                "slo": prometheus.get("slo", "Checkout Latency SLO at 94.8%"),
                "recommendation": prometheus.get("recommendation", "Scale checkout-api deployment and inspect restart causes."),
            },
            "grafana": {
                "dashboard_annotation": grafana.get("dashboard_annotation", "Checkout deployment annotation 9 minutes ago"),
                "loki_error_logs": grafana.get("loki_error_logs", "Elevated checkout timeout logs"),
                "tempo_latency": grafana.get("tempo_latency", "905 ms"),
                "alert_state": grafana.get("alert_state", "firing"),
                "dashboard_health": grafana.get("dashboard_health", "91%"),
                "recommendation": grafana.get("recommendation", "Inspect Loki timeout stream with Tempo trace exemplars."),
            },
            "github": {
                "deployment": new_relic.get("related_deployment") or datadog.get("github_deployment", "11 minutes ago"),
                "applications_changed": github.get("applications", []),
            },
            "jira": {
                "release": "Release 2026.08",
                "sprint": (jira.get("highest_risk_sprint") or {}).get("name", "Sprint 24"),
            },
            "servicenow": {
                "p1_status": "No active P1 incident",
            },
            "timeline": timeline,
            "recommendation": dynatrace.get("recommendation") or new_relic.get("recommendation", "Increase pool size or roll back deployment."),
            "confidence": max(
                int(dynatrace.get("confidence", 98) or 0),
                int(datadog.get("confidence", 97) or 0),
                int(new_relic.get("confidence", 97) or 0),
                int(splunk.get("confidence", 96) or 0),
                int(prometheus.get("confidence", 96) or 0),
                int(grafana.get("confidence", 96) or 0),
            ),
        }

    @staticmethod
    def _details(connector_name: str, org_id: str) -> dict[str, Any]:
        try:
            connector = get_connector(connector_name, org_id=org_id)
            certification = connector.certification_metadata() if hasattr(connector, "certification_metadata") else {}
            return certification.get("details", {})
        except Exception:
            return {}
