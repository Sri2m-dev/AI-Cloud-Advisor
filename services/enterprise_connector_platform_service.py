from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from connectors.base import (
    ConnectorAuthManager,
    ConnectorHealthEvaluator,
    ConnectorNormalizer,
    ConnectorScheduler,
    ConnectorWebhookManager,
)
from connectors.base.sync_manager import ConnectorSyncManager
from connectors.common.tenant_guard import resolve_organization_id
from connectors.connector_registry import CONNECTOR_CLASSES
from connectors.connector_registry import get_connector
from repositories.enterprise_connector_repository import EnterpriseConnectorRepository
from vault.credential_store import CredentialStore
from vault.token_rotation import TokenRotation


MARKETPLACE_CONNECTORS = [
    ("AWS", "Cloud", "IAM Role", 5, "Finish remaining services", "Hourly"),
    ("Azure", "Cloud", "OAuth", 5, "Enterprise cloud", "Hourly"),
    ("GCP", "Cloud", "OAuth", 4, "Complete multi-cloud", "Daily"),
    ("Microsoft 365", "Productivity", "Microsoft Graph OAuth", 5, "Identity, licenses, collaboration, security, SaaS intelligence", "Daily"),
    ("ServiceNow", "ITSM", "OAuth", 5, "CMDB, incidents, CAB", "Every 15 min"),
    ("GitHub", "DevOps", "OAuth App / GitHub App / PAT", 5, "Software delivery, Actions, security, releases, and ownership", "Event driven"),
    ("Jira", "Delivery & ITSM", "Atlassian OAuth / API Token", 5, "Jira Software, JSM, Assets, SLAs, delivery risk, and ownership", "Every 15 min"),
    ("Google Workspace", "Identity", "Google OAuth", 3, "Identity and collaboration", "Daily"),
    ("Datadog", "Observability", "API Key / Application Key", 5, "Metrics, logs, traces, alerts, APM, SLOs, synthetics, and security telemetry", "Every 5 min"),
    ("Dynatrace", "Observability", "Dynatrace API Token / OAuth", 5, "Smartscape, Davis AI, problems, Kubernetes, security, and live topology", "Every 5 min"),
    ("New Relic", "Observability", "API Key / User Key / Ingest License Key", 5, "APM, infrastructure, browser, mobile, logs, alerts, workloads, and service levels", "Every 5 min"),
    ("Splunk", "Observability", "Splunk Token / Username Password", 5, "Logs, searches, dashboards, alerts, Enterprise Security, SOAR, audit, and governance", "Every 5 min"),
    ("Prometheus", "Observability", "Basic Auth / Bearer Token", 5, "Metrics, PromQL, targets, scrape jobs, rules, Alertmanager, Kubernetes, and SLO signals", "Every 1 min"),
    ("Grafana", "Observability", "API Token / Service Account Token", 5, "Dashboards, panels, data sources, alerts, Loki, Tempo, Mimir, OnCall, and SLOs", "Every 5 min"),
    ("Kubernetes", "Infrastructure", "Service Account", 3, "Capacity and workload inventory", "Hourly"),
    ("VMware", "Infrastructure", "API Key", 3, "Private cloud inventory", "Daily"),
    ("Salesforce", "SaaS", "OAuth", 3, "Revenue system context", "Daily"),
    ("CrowdStrike", "Security", "API Key", 3, "Endpoint security posture", "Hourly"),
    ("Slack", "Productivity", "OAuth", 2, "Collaboration signals", "Event driven"),
    ("Zoom", "Productivity", "OAuth", 2, "Usage and license signals", "Daily"),
]


class EnterpriseConnectorPlatformService:
    @staticmethod
    def get_marketplace(organization_id: str | None = None) -> dict[str, Any]:
        org_id = resolve_organization_id(organization_id)
        registry = {row.get("connector_name"): row for row in EnterpriseConnectorRepository.list_registry(org_id)}
        connectors = []
        for name, category, auth_type, priority, reason, schedule in MARKETPLACE_CONNECTORS:
            row = registry.get(name, {})
            health = ConnectorHealthEvaluator.evaluate(row)
            certification = EnterpriseConnectorPlatformService._certification(name)
            health_score = health["health_score"] if row else certification.get("health_score", 0)
            if (
                row
                and certification.get("certification_level") == "Gold"
                and str(row.get("status") or "").upper() not in {"FAILED", "ERROR", "UNHEALTHY"}
            ):
                health_score = max(health_score, int(certification.get("health_score") or 0))
            connectors.append(
                {
                    "Connector": name,
                    "Category": category,
                    "Authentication": auth_type,
                    "Priority": priority,
                    "Reason": reason,
                    "Default Schedule": schedule,
                    "SDK Available": name in CONNECTOR_CLASSES,
                    "Status": row.get("status", "Not Configured"),
                    "Enabled": bool(row.get("enabled", False)),
                    "Health": health_score,
                    "Certification": certification.get("certification_level", "Uncertified"),
                    "Certification Details": certification,
                    "Coverage": certification.get("coverage", {}),
                    "Last Sync": row.get("last_sync"),
                    "Next Sync": row.get("next_sync") or ConnectorScheduler.next_sync(schedule),
                },
            )
        return {
            "organization_id": org_id,
            "connectors": connectors,
            "categories": sorted({row["Category"] for row in connectors}),
            "summary": EnterpriseConnectorPlatformService._summary(connectors),
        }

    @staticmethod
    def connect_once(
        connector_name: str,
        credentials: dict[str, Any] | None = None,
        organization_id: str | None = None,
        schedule: str | None = None,
        configured_by: str = "system",
    ) -> dict[str, Any]:
        org_id = resolve_organization_id(organization_id)
        definition = EnterpriseConnectorPlatformService._definition(connector_name)
        if not definition:
            return {"status": "FAILED", "message": f"{connector_name} is not in the marketplace."}
        name, category, auth_type, priority, reason, default_schedule = definition
        credentials = credentials or EnterpriseConnectorPlatformService._demo_credentials(name, auth_type)
        credential_ref = CredentialStore.store(name, credentials, org_id)
        auth = ConnectorAuthManager.authenticate(name, auth_type, credentials)
        rotation = TokenRotation.rotation_plan(auth_type)
        selected_schedule = schedule or default_schedule
        webhook = ConnectorWebhookManager.register(name, org_id) if selected_schedule == "Event driven" else {}
        certification = EnterpriseConnectorPlatformService._certification(name)
        registry_row = {
            "id": str(uuid.uuid4()),
            "organization_id": org_id,
            "connector_name": name,
            "category": category,
            "version": certification.get("version", "1.0"),
            "authentication_type": auth_type,
            "status": "Connected",
            "health": certification.get("health_score", 95),
            "certification_level": certification.get("certification_level", "Uncertified"),
            "coverage": certification.get("coverage", {}),
            "enabled": True,
            "last_sync": None,
            "next_sync": ConnectorScheduler.next_sync(selected_schedule),
            "sync_schedule": selected_schedule,
            "credential_ref": credential_ref["secret_ref"],
            "configured_by": configured_by,
            "metadata": {
                "priority": priority,
                "reason": reason,
                "auth": auth,
                "rotation": rotation,
                "webhook": webhook,
                "certification": certification,
            },
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        EnterpriseConnectorRepository.upsert_registry(registry_row)
        EnterpriseConnectorPlatformService._save_certification(org_id, certification)
        return {
            "status": "CONNECTED",
            "connector": name,
            "credential_ref": credential_ref["secret_ref"],
            "schedule": selected_schedule,
            "next_sync": registry_row["next_sync"],
            "auth": auth,
            "rotation": rotation,
            "webhook": webhook,
        }

    @staticmethod
    def run_sync(connector_name: str, organization_id: str | None = None) -> dict[str, Any]:
        org_id = resolve_organization_id(organization_id)
        started = datetime.now(timezone.utc)
        registry = EnterpriseConnectorPlatformService._registry_row(connector_name, org_id)
        try:
            results = ConnectorSyncManager.sync(connector_name) if connector_name in CONNECTOR_CLASSES else []
            raw_records = EnterpriseConnectorPlatformService._records_from_results(connector_name, results)
            normalized = ConnectorNormalizer.normalize_records(connector_name, raw_records)
            fabric_rows = [
                {
                    **row,
                    "id": str(uuid.uuid4()),
                    "organization_id": org_id,
                    "raw_payload": row.get("normalized_payload", {}),
                    "business_context": EnterpriseConnectorPlatformService._business_context(row),
                    "relationship_hints": EnterpriseConnectorPlatformService._relationship_hints(row),
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                }
                for row in normalized
            ]
            EnterpriseConnectorRepository.upsert_fabric_records(fabric_rows)
            completed = datetime.now(timezone.utc)
            status = "SUCCESS"
            error = ""
        except Exception as exc:
            results = []
            raw_records = []
            normalized = []
            fabric_rows = []
            completed = datetime.now(timezone.utc)
            status = "FAILED"
            error = str(exc)
        duration = round((completed - started).total_seconds(), 2)
        next_sync = ConnectorScheduler.next_sync(registry.get("sync_schedule") or "Daily")
        health = ConnectorHealthEvaluator.evaluate(
            {
                "status": "Connected" if status == "SUCCESS" else "FAILED",
                "records_synced": len(normalized),
                "last_sync": completed.isoformat(),
                "error_count": 1 if error else 0,
            },
        )
        certification = EnterpriseConnectorPlatformService._certification(connector_name)
        EnterpriseConnectorRepository.insert_sync_run(
            {
                "organization_id": org_id,
                "connector_name": connector_name,
                "status": status,
                "started_at": started.isoformat(),
                "completed_at": completed.isoformat(),
                "duration_seconds": duration,
                "records_synced": len(normalized),
                "raw_records": len(raw_records),
                "normalized_records": len(normalized),
                "fabric_records": len(fabric_rows),
                "error_message": error,
                "sync_payload": {"results": results[:5]},
            },
        )
        EnterpriseConnectorRepository.upsert_registry(
            {
                **registry,
                "id": registry.get("id") or str(uuid.uuid4()),
                "organization_id": org_id,
                "connector_name": connector_name,
                "category": registry.get("category") or EnterpriseConnectorPlatformService._category(connector_name),
                "version": registry.get("version") or "1.0",
                "authentication_type": registry.get("authentication_type") or EnterpriseConnectorPlatformService._auth_type(connector_name),
                "status": "Connected" if status == "SUCCESS" else "Failed",
                "health": health["health_score"],
                "certification_level": certification.get("certification_level", "Uncertified"),
                "coverage": certification.get("coverage", {}),
                "enabled": True,
                "last_sync": completed.isoformat(),
                "next_sync": next_sync,
                "records_synced": len(normalized),
                "error_count": 1 if error else 0,
                "last_error": error,
                "metadata": {**(registry.get("metadata") or {}), "certification": certification},
                "updated_at": completed.isoformat(),
            },
        )
        EnterpriseConnectorPlatformService._save_certification(org_id, certification)
        EnterpriseConnectorPlatformService._record_quality(connector_name, org_id, normalized, error)
        EnterpriseConnectorPlatformService._record_observability(connector_name, org_id, normalized, certification, health, duration, status)
        return {
            "connector": connector_name,
            "status": status,
            "records_synced": len(normalized),
            "fabric_records": len(fabric_rows),
            "duration_seconds": duration,
            "health": health,
            "next_sync": next_sync,
            "error": error,
        }

    @staticmethod
    def get_health_dashboard(organization_id: str | None = None) -> dict[str, Any]:
        org_id = resolve_organization_id(organization_id)
        marketplace = EnterpriseConnectorPlatformService.get_marketplace(org_id)
        runs = EnterpriseConnectorRepository.list_sync_runs(org_id)
        fabric = EnterpriseConnectorRepository.list_fabric(org_id)
        quality = EnterpriseConnectorRepository.list_quality_events(org_id)
        certifications = EnterpriseConnectorRepository.list_certifications(org_id)
        resource_summary = EnterpriseConnectorRepository.list_generic("connector_resource_summary", org_id)
        api_usage = EnterpriseConnectorRepository.list_generic("connector_api_usage", org_id)
        certification_history = EnterpriseConnectorRepository.list_generic("connector_certification_history", org_id)
        health_metrics = EnterpriseConnectorRepository.list_generic("connector_health_metrics", org_id)
        rows = []
        for connector in marketplace["connectors"]:
            latest = next((row for row in runs if row.get("connector_name") == connector["Connector"]), {})
            rows.append(
                {
                    "Connector": connector["Connector"],
                    "Category": connector["Category"],
                    "Status": connector["Status"],
                    "Authentication": connector["Authentication"],
                    "Last Sync": connector["Last Sync"] or latest.get("completed_at"),
                    "Next Sync": connector["Next Sync"],
                    "Health": connector["Health"],
                    "Certification": connector.get("Certification", "Uncertified"),
                    "Certification Details": connector.get("Certification Details", {}),
                    "Coverage": EnterpriseConnectorPlatformService._coverage_summary(connector.get("Coverage", {})),
                    "Error Count": int(latest.get("error_count") or 0),
                    "Records Synced": int(latest.get("records_synced") or 0),
                    "Sync Duration": latest.get("duration_seconds", 0),
                    "Data Freshness": ConnectorHealthEvaluator.evaluate({"status": connector["Status"], "last_sync": connector["Last Sync"] or latest.get("completed_at")})["data_freshness"],
                },
            )
        connected = [row for row in rows if row["Status"] == "Connected"]
        return {
            "organization_id": org_id,
            "kpis": {
                "Total Connectors": len(rows),
                "Connected": len(connected),
                "Unhealthy": len([row for row in rows if row["Health"] < 50]),
                "Fabric Records": len(fabric),
                "Quality Events": len(quality),
                "Average Health": round(sum(row["Health"] for row in rows) / len(rows), 1) if rows else 0,
                "Gold Certified": len([row for row in rows if row.get("Certification") == "Gold"]),
            },
            "connectors": rows,
            "sync_runs": runs,
            "fabric_records": fabric,
            "quality_events": quality,
            "certifications": certifications,
            "resource_summary": resource_summary,
            "api_usage": api_usage,
            "certification_history": certification_history,
            "health_metrics": health_metrics,
            "executive_summary": EnterpriseConnectorPlatformService._health_summary(rows, fabric, quality),
        }

    @staticmethod
    def _definition(connector_name: str) -> tuple[str, str, str, int, str, str] | None:
        return next((row for row in MARKETPLACE_CONNECTORS if row[0].lower() == connector_name.lower()), None)

    @staticmethod
    def _category(connector_name: str) -> str:
        row = EnterpriseConnectorPlatformService._definition(connector_name)
        return row[1] if row else "Other"

    @staticmethod
    def _auth_type(connector_name: str) -> str:
        row = EnterpriseConnectorPlatformService._definition(connector_name)
        return row[2] if row else "API Key"

    @staticmethod
    def _registry_row(connector_name: str, org_id: str) -> dict[str, Any]:
        return next((row for row in EnterpriseConnectorRepository.list_registry(org_id) if row.get("connector_name") == connector_name), {})

    @staticmethod
    def _records_from_results(connector_name: str, results: list[dict[str, Any]]) -> list[dict[str, Any]]:
        records = []
        for index, result in enumerate(results or []):
            records.append(
                {
                    "id": f"{connector_name.lower().replace(' ', '-')}-{index + 1}",
                    "name": f"{connector_name} {result.get('details', {}).get('method', 'sync')} record",
                    "type": "Connector Sync Result",
                    "connector_status": result.get("status"),
                    "objects_synced": result.get("objects_synced", 0),
                    "tables_populated": result.get("tables_populated", []),
                    "sources": result.get("sources", []),
                },
            )
        if not records:
            records.append({"id": f"{connector_name.lower()}-connection", "name": f"{connector_name} Connection", "type": "Connector"})
        return records

    @staticmethod
    def _certification(connector_name: str) -> dict[str, Any]:
        try:
            connector = get_connector(connector_name)
            if hasattr(connector, "certification_metadata"):
                return connector.certification_metadata()
        except Exception:
            pass
        return {
            "connector": connector_name,
            "certification_level": "Uncertified",
            "coverage": {
                "organization": False,
                "billing": False,
                "inventory": False,
                "governance": False,
                "operations": False,
                "identity": False,
            },
        }

    @staticmethod
    def _save_certification(org_id: str, certification: dict[str, Any]) -> None:
        EnterpriseConnectorRepository.upsert_certification(
            {
                "organization_id": org_id,
                "connector_name": certification.get("connector"),
                "connector_version": certification.get("version", "1.0"),
                "status": certification.get("status", "Unknown"),
                "authentication": certification.get("authentication", "Unknown"),
                "last_sync": certification.get("last_sync"),
                "next_sync": certification.get("next_sync"),
                "records_synced": certification.get("records_synced", 0),
                "sync_duration": certification.get("sync_duration", 0),
                "coverage": certification.get("coverage", {}),
                "health_score": certification.get("health_score", 0),
                "certification_level": certification.get("certification_level", "Uncertified"),
                "details": certification.get("details", {}),
                "certified_at": certification.get("certified_at"),
            },
        )

    @staticmethod
    def _coverage_summary(coverage: dict[str, bool]) -> str:
        if not coverage:
            return "No certified domains"
        complete = [name.title() for name, enabled in coverage.items() if enabled]
        return ", ".join(complete) if complete else "No certified domains"

    @staticmethod
    def _business_context(row: dict[str, Any]) -> dict[str, Any]:
        return {
            "feeds": ["Knowledge Graph", "Digital Twin", "Predictive Intelligence", "Agentic AI"],
            "owner": "Integration Platform",
            "quality_score": row.get("quality_score", 0),
        }

    @staticmethod
    def _relationship_hints(row: dict[str, Any]) -> list[dict[str, str]]:
        return [
            {"source": row.get("source_system", "Connector"), "relationship": "PRODUCES", "target": row.get("entity_type", "Record")},
            {"source": row.get("entity_type", "Record"), "relationship": "FEEDS", "target": "Enterprise Data Fabric"},
        ]

    @staticmethod
    def _record_quality(connector_name: str, org_id: str, normalized: list[dict[str, Any]], error: str) -> None:
        missing = sum(1 for row in normalized if int(row.get("quality_score") or 0) < 70)
        EnterpriseConnectorRepository.insert_quality_event(
            {
                "organization_id": org_id,
                "connector_name": connector_name,
                "event_type": "Sync Quality",
                "duplicate_records": 0,
                "missing_fields": missing,
                "failed_syncs": 1 if error else 0,
                "api_throttling": 0,
                "authentication_failures": 1 if "auth" in error.lower() else 0,
                "mapping_failures": missing,
                "relationship_coverage": 100 if normalized else 0,
                "sync_latency_seconds": 0,
                "details": {"error": error},
            },
        )

    @staticmethod
    def _record_observability(
        connector_name: str,
        org_id: str,
        normalized: list[dict[str, Any]],
        certification: dict[str, Any],
        health: dict[str, Any],
        duration: float,
        status: str,
    ) -> None:
        now = datetime.now(timezone.utc).isoformat()
        for row in normalized:
            EnterpriseConnectorRepository.insert_generic(
                "connector_discovery",
                {
                    "organization_id": org_id,
                    "connector_name": connector_name,
                    "discovery_type": row.get("entity_type", "Unknown"),
                    "entity_name": row.get("display_name", "Unknown"),
                    "entity_id": row.get("source_record_id"),
                    "region": (row.get("normalized_payload") or {}).get("region"),
                    "status": "Discovered",
                    "payload": row,
                    "discovered_at": now,
                },
            )
        counts: dict[tuple[str, str], int] = {}
        for row in normalized:
            payload = row.get("normalized_payload") or {}
            resource_type = row.get("entity_type") or "Unknown"
            region = payload.get("region") or "global"
            counts[(resource_type, region)] = counts.get((resource_type, region), 0) + 1
        for (resource_type, region), count in counts.items():
            EnterpriseConnectorRepository.upsert_generic(
                "connector_resource_summary",
                {
                    "organization_id": org_id,
                    "connector_name": connector_name,
                    "resource_type": resource_type,
                    "resource_count": count,
                    "region": region,
                    "health_score": health.get("health_score", 0),
                    "payload": {"certification": certification.get("certification_level")},
                },
                "organization_id,connector_name,resource_type,region",
            )
        api_usage = (certification.get("details") or {}).get("api_quota_usage") or {}
        for api_name, usage in api_usage.items():
            value = float(str(usage).replace("%", "") or 0)
            EnterpriseConnectorRepository.insert_generic(
                "connector_api_usage",
                {
                    "organization_id": org_id,
                    "connector_name": connector_name,
                    "api_name": api_name,
                    "quota_used": value,
                    "quota_limit": 100,
                    "calls": max(1, len(normalized)),
                    "throttled_calls": 0,
                    "measured_at": now,
                },
            )
        EnterpriseConnectorRepository.insert_generic(
            "connector_certification_history",
            {
                "organization_id": org_id,
                "connector_name": connector_name,
                "connector_version": certification.get("version", "1.0"),
                "certification_level": certification.get("certification_level", "Uncertified"),
                "health_score": certification.get("health_score", 0),
                "coverage": certification.get("coverage", {}),
                "status": certification.get("status", "Unknown"),
                "certified_at": certification.get("certified_at") or now,
                "payload": certification,
            },
        )
        EnterpriseConnectorRepository.insert_generic(
            "connector_health_metrics",
            {
                "organization_id": org_id,
                "connector_name": connector_name,
                "health_score": health.get("health_score", 0),
                "authentication_status": "Connected",
                "sync_status": status,
                "data_freshness": health.get("data_freshness"),
                "records_discovered": len(normalized),
                "sync_duration": duration,
                "error_count": 0 if status == "SUCCESS" else 1,
                "measured_at": now,
                "payload": {"certification": certification.get("certification_level")},
            },
        )

    @staticmethod
    def _summary(connectors: list[dict[str, Any]]) -> dict[str, Any]:
        return {
            "Total": len(connectors),
            "Connected": len([row for row in connectors if row["Status"] == "Connected"]),
            "SDK Available": len([row for row in connectors if row["SDK Available"]]),
            "Categories": len({row["Category"] for row in connectors}),
            "Wave 1": [row["Connector"] for row in connectors if row["Priority"] >= 4],
        }

    @staticmethod
    def _health_summary(rows: list[dict[str, Any]], fabric: list[dict[str, Any]], quality: list[dict[str, Any]]) -> str:
        connected = len([row for row in rows if row["Status"] == "Connected"])
        return (
            f"{connected} of {len(rows)} marketplace connectors are connected. "
            f"The Enterprise Data Fabric currently contains {len(fabric)} normalized records, "
            f"with {len(quality)} quality or observability events captured."
        )

    @staticmethod
    def _demo_credentials(connector_name: str, auth_type: str) -> dict[str, str]:
        if connector_name == "AWS":
            return {"role_arn": "arn:aws:iam::123456789012:role/NexoraReadOnly", "external_id": "demo"}
        if "OAuth" in auth_type:
            return {"client_id": "demo-client", "refresh_token": "demo-refresh-token"}
        return {"api_key": "demo-api-key"}
