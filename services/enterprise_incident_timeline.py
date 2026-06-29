from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from connectors.common.tenant_guard import resolve_organization_id
from services.ai_correlation_engine import AICorrelationEngine


TIMELINE_CAPABILITIES = {
    "multi_source_event_correlation": True,
    "ai_root_cause_generation": True,
    "executive_narrative": True,
    "business_impact_mapping": True,
    "technical_dependency_mapping": True,
    "timeline_replay": True,
    "copilot_integration": True,
    "learning_feedback": True,
}


class EnterpriseIncidentTimeline:
    @staticmethod
    def get_dashboard(
        organization_id: str | None = None,
        incident_id: str = "INC-CHECKOUT-2026-09",
        search: str | None = None,
        category: str | None = None,
    ) -> dict[str, Any]:
        org_id = resolve_organization_id(organization_id)
        incident = EnterpriseIncidentTimeline.build_incident(org_id, incident_id)
        timeline = EnterpriseIncidentTimeline.build_timeline(org_id, incident_id)
        filtered = EnterpriseIncidentTimeline.filter_timeline(timeline, search=search, category=category)
        event_bus = EnterpriseIncidentTimeline.publish_event_bus(timeline)
        root_cause = EnterpriseIncidentTimeline.root_cause(org_id)
        business_impact = EnterpriseIncidentTimeline.business_impact()
        technical_impact = EnterpriseIncidentTimeline.technical_impact()
        recovery = EnterpriseIncidentTimeline.recovery_timeline(timeline)
        recommendation = EnterpriseIncidentTimeline.recommendation(root_cause)
        narrative = EnterpriseIncidentTimeline.incident_narrative(incident, timeline, root_cause, business_impact, recovery)
        replay = EnterpriseIncidentTimeline.replay_frames(timeline)
        learning = EnterpriseIncidentTimeline.learning_feedback(incident, root_cause, recommendation)
        certification = EnterpriseIncidentTimeline.certification_metadata()
        return {
            "organization_id": org_id,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "incident": incident,
            "incident_summary": EnterpriseIncidentTimeline.incident_summary(incident),
            "timeline": filtered,
            "all_timeline": timeline,
            "timeline_graph": EnterpriseIncidentTimeline.timeline_graph(timeline),
            "event_bus": event_bus,
            "root_cause": root_cause,
            "business_impact": business_impact,
            "technical_impact": technical_impact,
            "recommendation": recommendation,
            "recovery_timeline": recovery,
            "executive_replay": replay,
            "executive_timeline": EnterpriseIncidentTimeline.executive_timeline(incident, business_impact, recovery),
            "search_index": EnterpriseIncidentTimeline.search_index(timeline),
            "learning_feedback": learning,
            "certification": certification,
            "executive_narrative": narrative,
            "kpis": {
                "Timeline Events": len(timeline),
                "Correlated Sources": len({row["source"] for row in timeline}),
                "MTTR Minutes": incident["mttr_minutes"],
                "Revenue Impact": incident["revenue_impact"],
                "Customers Impacted": business_impact["customers_impacted"],
                "Confidence": root_cause["confidence"],
                "Certification": certification["level"],
            },
        }

    @staticmethod
    def build_incident(organization_id: str, incident_id: str) -> dict[str, Any]:
        correlation = AICorrelationEngine.correlate_checkout_slowdown(organization_id)
        return {
            "incident_id": incident_id,
            "title": "Checkout Slowdown",
            "severity": "P1",
            "business_service": "Checkout",
            "applications": ["Checkout API", "Checkout Web", "Payment Authorization"],
            "status": "Recovered",
            "started_at": "08:34",
            "detected_at": "08:33",
            "recovered_at": "08:51",
            "duration_minutes": 17,
            "mttr_minutes": 13,
            "revenue_impact": 21000,
            "risk": "High",
            "owner": "Revenue Platform",
            "correlation_confidence": correlation["confidence"],
        }

    @staticmethod
    def build_timeline(organization_id: str | None = None, incident_id: str = "INC-CHECKOUT-2026-09") -> list[dict[str, Any]]:
        org_id = resolve_organization_id(organization_id)
        correlation = AICorrelationEngine.correlate_checkout_slowdown(org_id)
        rows = [
            EnterpriseIncidentTimeline._event(incident_id, "08:30", "GitHub", "DevOps", "Deployment", "Deployment Completed", "Checkout deployment release-2026.09 completed for checkout-api.", "release-2026.09", "Completed", "Info"),
            EnterpriseIncidentTimeline._event(incident_id, "08:31", "Jira", "DevOps", "Release", "Release Activated", "Jira Release 2026.09 moved to active rollout.", "Release 2026.09", "Completed", "Info"),
            EnterpriseIncidentTimeline._event(incident_id, "08:32", "Governance", "Governance", "Approval", "CAB Approval Verified", "Pre-approved deployment window and rollback path verified.", "CAB-8821", "Approved", "Info"),
            EnterpriseIncidentTimeline._event(incident_id, "08:33", "Prometheus", "Monitoring", "Alert", "CPU Threshold Exceeded", f"Checkout pod CPU reached {correlation['prometheus']['cpu']}; pod restarts {correlation['prometheus']['pod_restarts']}.", "checkout-api-pod", "Firing", "Warning"),
            EnterpriseIncidentTimeline._event(incident_id, "08:34", "Datadog", "Monitoring", "Metric", "Memory Spike", f"Datadog detected CPU {correlation['datadog']['cpu']} and checkout latency increase {correlation['datadog']['latency']}.", "checkout-api-prod", "Degraded", "Critical"),
            EnterpriseIncidentTimeline._event(incident_id, "08:34", "AWS", "Cloud", "Metric", "EC2 Host Pressure", "Checkout worker host pressure increased in the production autoscaling group.", "i-0checkout", "Degraded", "Warning"),
            EnterpriseIncidentTimeline._event(incident_id, "08:35", "Dynatrace", "Monitoring", "Alert", "Problem Created", f"Davis AI identified {correlation['dynatrace']['root_cause']}.", "Checkout Service", "Open", "Critical"),
            EnterpriseIncidentTimeline._event(incident_id, "08:36", "Splunk", "Security", "Log", "Authentication Anomaly", f"{correlation['splunk']['security_alert']}; failed logins increased {correlation['splunk']['failed_login_increase']}.", "checkout-auth", "Investigating", "Warning"),
            EnterpriseIncidentTimeline._event(incident_id, "08:37", "Grafana", "Monitoring", "Trace", "Tempo Latency Spike", f"Grafana annotation matched deployment; Tempo latency {correlation['grafana']['tempo_latency']}; Loki logs elevated.", "checkout-dashboard", "Degraded", "Warning"),
            EnterpriseIncidentTimeline._event(incident_id, "08:38", "ServiceNow", "ITSM", "Incident", "P1 Incident Opened", "P1 incident created for Checkout customer-facing latency.", "INC-CHECKOUT-2026-09", "Open", "Critical"),
            EnterpriseIncidentTimeline._event(incident_id, "08:39", "AI Correlation Engine", "AI", "Prediction", "Root Cause Generated", f"Root cause: {correlation['dynatrace']['root_cause']} with {correlation['confidence']}% confidence.", "ai-correlation-checkout", "Generated", "Info"),
            EnterpriseIncidentTimeline._event(incident_id, "08:41", "AI Recommendation", "AI", "Recommendation", "Rollback Recommended", correlation["recommendation"], "REC-CHECKOUT-ROLLBACK", "Recommended", "Info"),
            EnterpriseIncidentTimeline._event(incident_id, "08:42", "Governance", "Governance", "Approval", "Rollback Approved", "Rollback approved under emergency change policy.", "CAB-8821", "Approved", "Info"),
            EnterpriseIncidentTimeline._event(incident_id, "08:44", "Execution", "Governance", "Execution", "Rollback Started", "Automation started rollback to the previous stable Checkout release.", "EXEC-CHECKOUT-ROLLBACK", "Running", "Info"),
            EnterpriseIncidentTimeline._event(incident_id, "08:48", "Validation", "Monitoring", "Metric", "Golden Signals Recovering", "Latency, error rate, CPU, and pod restart signals began returning to baseline.", "checkout-golden-signals", "Recovering", "Info"),
            EnterpriseIncidentTimeline._event(incident_id, "08:51", "Recovery", "ITSM", "Recovery", "Service Recovered", "Checkout response time restored and incident moved to resolved.", "INC-CHECKOUT-2026-09", "Recovered", "Info"),
        ]
        return rows

    @staticmethod
    def incident_summary(incident: dict[str, Any]) -> dict[str, Any]:
        return {
            "Incident ID": incident["incident_id"],
            "Severity": incident["severity"],
            "Business Service": incident["business_service"],
            "Applications": ", ".join(incident["applications"]),
            "Revenue Impact": f"${incident['revenue_impact']:,.0f}",
            "Duration": f"{incident['duration_minutes']} minutes",
            "Status": incident["status"],
            "MTTR": f"{incident['mttr_minutes']} minutes",
            "Owner": incident["owner"],
            "Risk": incident["risk"],
        }

    @staticmethod
    def filter_timeline(
        timeline: list[dict[str, Any]],
        search: str | None = None,
        category: str | None = None,
    ) -> list[dict[str, Any]]:
        rows = timeline
        if category and category != "All":
            rows = [row for row in rows if row.get("category") == category]
        if search:
            text = search.lower()
            rows = [
                row
                for row in rows
                if any(text in str(row.get(key, "")).lower() for key in ["incident_id", "source", "event_type", "title", "summary", "entity"])
            ]
        return rows

    @staticmethod
    def publish_event_bus(timeline: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [
            {
                "event_id": f"bus-{index:04d}",
                "incident_id": row["incident_id"],
                "event_type": row["event_type"],
                "category": row["category"],
                "source_system": row["source"],
                "entity": row["entity"],
                "severity": row["severity"],
                "status": row["status"],
                "published_at": row["timestamp"],
                "payload": row,
            }
            for index, row in enumerate(timeline, start=1)
        ]

    @staticmethod
    def root_cause(organization_id: str | None = None) -> dict[str, Any]:
        correlation = AICorrelationEngine.correlate_checkout_slowdown(organization_id)
        return {
            "summary": correlation["dynatrace"]["root_cause"],
            "confidence": correlation["confidence"],
            "detected_first_by": {"source": "Prometheus", "time": "08:33", "evidence": "CPU threshold exceeded."},
            "contributing_factors": [
                {"Factor": "Deployment", "Evidence": correlation["github"]["deployment"]},
                {"Factor": "CPU", "Evidence": f"Checkout CPU {correlation['prometheus']['cpu']}"},
                {"Factor": "Authentication Failures", "Evidence": f"Splunk failed logins {correlation['splunk']['failed_logins']}"},
                {"Factor": "Latency", "Evidence": f"Tempo latency {correlation['grafana']['tempo_latency']}"},
                {"Factor": "Alert State", "Evidence": f"Alertmanager state {correlation['prometheus']['alert_state']}"},
            ],
            "evidence": correlation["timeline"],
        }

    @staticmethod
    def business_impact() -> dict[str, Any]:
        return {
            "applications": ["Checkout API", "Checkout Web", "Payment Authorization"],
            "customers_impacted": 18400,
            "revenue_exposure": 21000,
            "sla": "Checkout latency SLO breached for 17 minutes",
            "departments": ["Digital Commerce", "Customer Support", "Revenue Operations"],
            "business_services": ["Checkout", "Payments"],
            "business_risk": "High revenue-path risk until rollback completed",
            "savings_opportunity": 90000,
        }

    @staticmethod
    def technical_impact() -> list[dict[str, Any]]:
        return [
            {"Asset": "checkout-api-prod", "Type": "Kubernetes", "Impact": "CPU saturation and pod restarts", "Severity": "Critical"},
            {"Asset": "checkout-db-pool", "Type": "Database", "Impact": "Connection pool exhausted", "Severity": "Critical"},
            {"Asset": "payment-auth-api", "Type": "API", "Impact": "Downstream latency", "Severity": "Warning"},
            {"Asset": "i-0checkout", "Type": "EC2", "Impact": "Elevated host pressure", "Severity": "Warning"},
            {"Asset": "az-vm-checkout-worker", "Type": "Azure VM", "Impact": "Background queue delayed", "Severity": "Warning"},
        ]

    @staticmethod
    def recommendation(root_cause: dict[str, Any]) -> dict[str, list[str]]:
        return {
            "Immediate": [
                "Rollback Checkout API to the previous stable release.",
                "Scale checkout-api pods by two replicas until latency returns to baseline.",
                "Open a database pool saturation bridge with application and database owners.",
            ],
            "Medium-term": [
                "Increase database connection pool limits and add pool exhaustion alerts.",
                "Add pre-release synthetic checkout validation to the CAB package.",
                "Tune Prometheus alert thresholds to detect restart trends earlier.",
            ],
            "Long-term": [
                "Add deployment risk scoring that combines GitHub, Jira, Prometheus, and Grafana signals.",
                "Promote this incident pattern into Learning Engine knowledge memory.",
                f"Train future recommendations on {root_cause['summary']} recurrence signals.",
            ],
        }

    @staticmethod
    def recovery_timeline(timeline: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [
            row
            for row in timeline
            if row["event_type"] in {"Approval", "Execution", "Metric", "Recovery"} and row["time"] >= "08:42"
        ]

    @staticmethod
    def incident_narrative(
        incident: dict[str, Any],
        timeline: list[dict[str, Any]],
        root_cause: dict[str, Any],
        business_impact: dict[str, Any],
        recovery: list[dict[str, Any]],
    ) -> str:
        del timeline
        recovery_done = recovery[-1]["time"] if recovery else incident["recovered_at"]
        return (
            f"{incident['business_service']} experienced elevated response times beginning at {incident['started_at']}. "
            "A deployment completed four minutes earlier. Prometheus detected the first threshold breach at 08:33, "
            "followed by Datadog, Dynatrace, Splunk, Grafana, and ServiceNow signals. "
            f"Dynatrace and the AI Correlation Engine identified {root_cause['summary']}. "
            "AI recommended rollback, Governance approved it, and automation executed recovery. "
            f"Service was restored at {recovery_done}. Total impact was {incident['duration_minutes']} minutes with estimated "
            f"revenue exposure of ${business_impact['revenue_exposure']:,.0f}. Confidence: {root_cause['confidence']}%."
        )

    @staticmethod
    def timeline_graph(timeline: list[dict[str, Any]]) -> list[dict[str, str]]:
        sequence = [
            ("Deployment", "CPU"),
            ("CPU", "Latency"),
            ("Latency", "Errors"),
            ("Errors", "Incident"),
            ("Incident", "Rollback"),
            ("Rollback", "Recovery"),
        ]
        return [
            {"From": source, "To": target, "Evidence": EnterpriseIncidentTimeline._graph_evidence(timeline, target)}
            for source, target in sequence
        ]

    @staticmethod
    def replay_frames(timeline: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [
            {
                "frame": index,
                "time": row["time"],
                "headline": f"{row['source']} - {row['title']}",
                "narration": row["summary"],
                "status": row["status"],
            }
            for index, row in enumerate(timeline, start=1)
        ]

    @staticmethod
    def executive_timeline(
        incident: dict[str, Any],
        business_impact: dict[str, Any],
        recovery: list[dict[str, Any]],
    ) -> dict[str, Any]:
        return {
            "Revenue Impact": incident["revenue_impact"],
            "Customers Impacted": business_impact["customers_impacted"],
            "Business Services": ", ".join(business_impact["business_services"]),
            "Recovery": recovery[-1]["title"] if recovery else "Recovered",
            "Business Risk": business_impact["business_risk"],
            "Savings Opportunity": business_impact["savings_opportunity"],
        }

    @staticmethod
    def search_index(timeline: list[dict[str, Any]]) -> list[dict[str, str]]:
        return [
            {"Type": "Incident", "Value": "INC-CHECKOUT-2026-09"},
            {"Type": "Application", "Value": "Checkout API"},
            {"Type": "Business Service", "Value": "Checkout"},
            {"Type": "Repository", "Value": "checkout-api"},
            {"Type": "Change", "Value": "release-2026.09"},
            {"Type": "User", "Value": "revenue-platform-release-bot"},
            {"Type": "CI", "Value": "GitHub Actions deploy-checkout-prod"},
            *[{"Type": row["event_type"], "Value": row["entity"]} for row in timeline[:5]],
        ]

    @staticmethod
    def learning_feedback(
        incident: dict[str, Any],
        root_cause: dict[str, Any],
        recommendation: dict[str, list[str]],
    ) -> dict[str, Any]:
        return {
            "Root Cause": root_cause["summary"],
            "Recommendation": recommendation["Medium-term"][0],
            "Next Time": "Detect database pool saturation before customer-facing latency breach.",
            "Learning Signal": "Increase confidence for rollback recommendations when deployment, CPU, latency, and pool exhaustion align.",
            "Learning Score": 98,
            "Feeds": ["Learning Engine", "AI Correlation Engine", "Recommendation Engine"],
            "Incident": incident["incident_id"],
        }

    @staticmethod
    def certification_metadata() -> dict[str, Any]:
        return {
            "level": "Gold",
            "health_score": 98,
            "coverage": TIMELINE_CAPABILITIES,
            "certified_at": datetime.now(timezone.utc).isoformat(),
            "quality_standard": "Enterprise Incident Timeline Gold",
        }

    @staticmethod
    def checkout_incident(organization_id: str | None = None) -> dict[str, Any]:
        return EnterpriseIncidentTimeline.get_dashboard(organization_id)

    @staticmethod
    def _event(
        incident_id: str,
        time: str,
        source: str,
        category: str,
        event_type: str,
        title: str,
        summary: str,
        entity: str,
        status: str,
        severity: str,
    ) -> dict[str, Any]:
        return {
            "incident_id": incident_id,
            "time": time,
            "timestamp": f"2026-09-15T{time}:00Z",
            "source": source,
            "category": category,
            "event_type": event_type,
            "title": title,
            "summary": summary,
            "entity": entity,
            "status": status,
            "severity": severity,
        }

    @staticmethod
    def _graph_evidence(timeline: list[dict[str, Any]], target: str) -> str:
        token_map = {
            "CPU": "CPU",
            "Latency": "latency",
            "Errors": "failed logins",
            "Incident": "P1 incident",
            "Rollback": "Rollback",
            "Recovery": "Recovered",
        }
        token = token_map.get(target, target).lower()
        row = next((item for item in timeline if token in item["summary"].lower() or token in item["title"].lower()), {})
        return row.get("summary", "Correlated event sequence")
