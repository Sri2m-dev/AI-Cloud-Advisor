from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from connectors.connector_registry import get_connector
from connectors.common.tenant_guard import resolve_organization_id
from services.ai_correlation_engine import AICorrelationEngine


OBSERVABILITY_CONNECTORS = ["Datadog", "Dynatrace", "New Relic", "Splunk", "Grafana", "Prometheus"]


class EnterpriseObservabilityService:
    @staticmethod
    def get_dashboard(organization_id: str | None = None) -> dict[str, Any]:
        org_id = resolve_organization_id(organization_id)
        telemetry = EnterpriseObservabilityService.sync_telemetry(org_id, persist=False)
        records = telemetry["telemetry_records"]
        connectors = telemetry["connectors"]
        critical = [row for row in records if str(row.get("severity")).lower() == "critical"]
        return {
            "organization_id": org_id,
            "kpis": {
                "Telemetry Connectors": len(connectors),
                "Gold Certified": len([row for row in connectors if row.get("Certification") == "Gold"]),
                "Telemetry Records": len(records),
                "Critical Alerts": len(critical),
                "Signals": len({row.get("signal_type") for row in records}),
                "Correlations": 1,
                "Average Health": round(sum(float(row.get("Health") or 0) for row in connectors) / len(connectors), 1) if connectors else 0,
            },
            "connectors": connectors,
            "telemetry_records": records,
            "event_bus": EnterpriseObservabilityService.event_bus(records),
            "correlations": [EnterpriseObservabilityService.correlate_checkout_slowdown(org_id)],
            "smartscape": EnterpriseObservabilityService._dynatrace_detail(connectors, "smartscape"),
            "davis_ai": EnterpriseObservabilityService._dynatrace_detail(connectors, "davis_ai"),
            "kubernetes": EnterpriseObservabilityService._dynatrace_detail(connectors, "kubernetes"),
            "slo_health": EnterpriseObservabilityService._dynatrace_detail(connectors, "slo"),
            "new_relic": {
                "apm": EnterpriseObservabilityService._connector_detail(connectors, "New Relic", "apm"),
                "alerts": EnterpriseObservabilityService._connector_detail(connectors, "New Relic", "alerts"),
                "errors": EnterpriseObservabilityService._connector_detail(connectors, "New Relic", "errors"),
                "service_levels": EnterpriseObservabilityService._connector_detail(connectors, "New Relic", "service_levels"),
                "synthetics": EnterpriseObservabilityService._connector_detail(connectors, "New Relic", "synthetics"),
                "workloads": EnterpriseObservabilityService._connector_detail(connectors, "New Relic", "workloads"),
            },
            "splunk": {
                "logs": EnterpriseObservabilityService._connector_detail(connectors, "Splunk", "logs"),
                "searches": EnterpriseObservabilityService._connector_detail(connectors, "Splunk", "searches"),
                "dashboards": EnterpriseObservabilityService._connector_detail(connectors, "Splunk", "dashboards"),
                "alerts": EnterpriseObservabilityService._connector_detail(connectors, "Splunk", "alerts"),
                "enterprise_security": EnterpriseObservabilityService._connector_detail(connectors, "Splunk", "enterprise_security"),
                "soar": EnterpriseObservabilityService._connector_detail(connectors, "Splunk", "soar"),
                "security_risk": EnterpriseObservabilityService._connector_detail(connectors, "Splunk", "security_risk"),
            },
            "prometheus": {
                "targets": EnterpriseObservabilityService._connector_detail(connectors, "Prometheus", "targets"),
                "promql": EnterpriseObservabilityService._connector_detail(connectors, "Prometheus", "promql"),
                "alertmanager": EnterpriseObservabilityService._connector_detail(connectors, "Prometheus", "alertmanager"),
                "rules": EnterpriseObservabilityService._connector_detail(connectors, "Prometheus", "rules"),
                "kubernetes": EnterpriseObservabilityService._connector_detail(connectors, "Prometheus", "kubernetes"),
                "slo": EnterpriseObservabilityService._connector_detail(connectors, "Prometheus", "slo"),
            },
            "grafana": {
                "dashboards": EnterpriseObservabilityService._connector_detail(connectors, "Grafana", "dashboards"),
                "alerts": EnterpriseObservabilityService._connector_detail(connectors, "Grafana", "alerts"),
                "data_sources": EnterpriseObservabilityService._connector_detail(connectors, "Grafana", "data_sources"),
                "loki": EnterpriseObservabilityService._connector_detail(connectors, "Grafana", "loki"),
                "tempo": EnterpriseObservabilityService._connector_detail(connectors, "Grafana", "tempo"),
                "mimir": EnterpriseObservabilityService._connector_detail(connectors, "Grafana", "mimir"),
                "slo": EnterpriseObservabilityService._connector_detail(connectors, "Grafana", "slo"),
            },
            "observability_kpis": EnterpriseObservabilityService.gold_observability_kpis(connectors),
            "executive_summary": "Enterprise Observability is receiving live telemetry from Datadog, Dynatrace, New Relic, Splunk, Prometheus, and Grafana, normalizing metrics, logs, traces, alerts, events, dashboards, SLOs, Kubernetes signals, APM, service levels, security analytics, and audit signals into the Telemetry Fabric.",
        }

    @staticmethod
    def sync_telemetry(organization_id: str | None = None, persist: bool = False) -> dict[str, Any]:
        del persist
        org_id = resolve_organization_id(organization_id)
        connectors = []
        telemetry_records = []
        for name in OBSERVABILITY_CONNECTORS:
            try:
                connector = get_connector(name, org_id=org_id)
            except Exception:
                connectors.append(
                    {
                        "Connector": name,
                        "Status": "Planned",
                        "Certification": "Uncertified",
                        "Health": 0,
                        "Coverage": {},
                    }
                )
                continue
            certification = connector.certification_metadata() if hasattr(connector, "certification_metadata") else {}
            normalized = connector.normalize_telemetry() if hasattr(connector, "normalize_telemetry") else []
            connectors.append(
                {
                    "Connector": name,
                    "Status": "Connected",
                    "Certification": certification.get("certification_level", "Uncertified"),
                    "Health": certification.get("health_score", 0),
                    "Coverage": certification.get("coverage", {}),
                    "Records Synced": certification.get("records_synced", 0),
                    "Details": certification.get("details", {}),
                }
            )
            telemetry_records.extend(normalized)
        return {
            "organization_id": org_id,
            "connectors": connectors,
            "telemetry_records": telemetry_records,
            "synced_at": datetime.now(timezone.utc).isoformat(),
        }

    @staticmethod
    def event_bus(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        events = []
        for index, row in enumerate(records, start=1):
            if row.get("signal_type") in {"alert", "event", "slo"} or str(row.get("severity")).lower() in {"critical", "warning"}:
                events.append(
                    {
                        "event_id": f"evt-{index:04d}",
                        "source_system": row.get("source_system"),
                        "event_type": row.get("signal_type"),
                        "entity": row.get("entity"),
                        "business_service": row.get("business_service"),
                        "severity": row.get("severity"),
                        "payload": row.get("payload", {}),
                        "published_at": row.get("observed_at"),
                    }
                )
        return events

    @staticmethod
    def correlate_checkout_slowdown(organization_id: str | None = None) -> dict[str, Any]:
        org_id = resolve_organization_id(organization_id)
        correlation = AICorrelationEngine.correlate_checkout_slowdown(org_id)
        return {
            "Question": "Why is Checkout slow?",
            "Asset": correlation["asset"],
            "Telemetry": (
                f"Dynatrace response time increased {correlation['dynatrace']['response_time']}; "
                f"Datadog CPU is {correlation['datadog']['cpu']}; "
                f"New Relic APM latency is {correlation['new_relic']['apm_latency']} with error rate {correlation['new_relic']['error_rate']}."
            ),
            "Change Context": f"GitHub deployment {correlation['github']['deployment']}; Jira {correlation['jira']['release']}.",
            "ITSM Context": correlation["servicenow"]["p1_status"],
            "Davis AI": correlation["dynatrace"]["root_cause"],
            "New Relic": f"{correlation['new_relic']['browser_impact']}; {correlation['new_relic']['service_level']}.",
            "Splunk": f"{correlation['splunk']['security_alert']}; failed logins {correlation['splunk']['failed_logins']} ({correlation['splunk']['failed_login_increase']} increase).",
            "Prometheus": (
                f"CPU {correlation['prometheus']['cpu']}, memory {correlation['prometheus']['memory']}, "
                f"pod restarts {correlation['prometheus']['pod_restarts']}, Alertmanager state {correlation['prometheus']['alert_state']}."
            ),
            "Grafana": (
                f"{correlation['grafana']['dashboard_annotation']}; Loki logs: {correlation['grafana']['loki_error_logs']}; "
                f"Tempo latency {correlation['grafana']['tempo_latency']}; dashboard health {correlation['grafana']['dashboard_health']}."
            ),
            "Timeline": correlation["timeline"],
            "Customer Impact": "Elevated checkout response time for web customers.",
            "Revenue Risk / Hour": 342000,
            "Recommendation": correlation["recommendation"],
            "Confidence": correlation["confidence"],
        }

    @staticmethod
    def gold_observability_kpis(connectors: list[dict[str, Any]]) -> dict[str, Any]:
        prometheus = lambda key: EnterpriseObservabilityService._connector_detail(connectors, "Prometheus", key)
        grafana = lambda key: EnterpriseObservabilityService._connector_detail(connectors, "Grafana", key)
        return {
            "Prometheus targets": int((prometheus("targets") or {}).get("count") or 0),
            "PromQL query health": f"{float((prometheus('promql') or {}).get('success_rate') or 0):.1f}%",
            "Alertmanager alerts": int((prometheus("alertmanager") or {}).get("firing") or 0),
            "Recording rules": int((prometheus("rules") or {}).get("recording") or 0),
            "Kubernetes metrics": int((prometheus("kubernetes") or {}).get("pods") or 0),
            "Grafana dashboards": int((grafana("dashboards") or {}).get("count") or 0),
            "Grafana alerts": int((grafana("alerts") or {}).get("active") or 0),
            "Loki log streams": int((grafana("loki") or {}).get("streams") or 0),
            "Tempo traces": int((grafana("tempo") or {}).get("traces") or 0),
            "Mimir metrics": int((grafana("mimir") or {}).get("metric_series") or 0),
            "SLO compliance": f"{min(float((prometheus('slo') or {}).get('average_compliance') or 0), float((grafana('slo') or {}).get('average_compliance') or 0)):.1f}%",
        }

    @staticmethod
    def _dynatrace_detail(connectors: list[dict[str, Any]], key: str) -> dict[str, Any]:
        return EnterpriseObservabilityService._connector_detail(connectors, "Dynatrace", key)

    @staticmethod
    def _connector_detail(connectors: list[dict[str, Any]], connector_name: str, key: str) -> dict[str, Any]:
        row = next((item for item in connectors if item.get("Connector") == connector_name), {})
        return (row.get("Details") or {}).get(key, {})
