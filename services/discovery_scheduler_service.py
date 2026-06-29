from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from connectors.common.persistence import insert_sync_history
from connectors.common.tenant_guard import resolve_organization_id
from services.aws_connector_service import AWSConnectorService
from services.azure_connector_service import AzureConnectorService
from services.enterprise_asset_identity_service import EnterpriseAssetIdentityService
from services.enterprise_relationship_intelligence_service import EnterpriseRelationshipIntelligenceService
from services.supabase_client import supabase


class DiscoverySchedulerService:
    ORCHESTRATOR_NAME = "Discovery Scheduler"

    @staticmethod
    def load_enabled_connectors(organization_id: str | None = None) -> list[dict[str, Any]]:
        try:
            query = (
                supabase.table("connector_registry")
                .select("*")
                .eq("enabled", True)
            )
            if organization_id:
                query = query.eq("organization_id", resolve_organization_id(organization_id))
            response = query.execute()
            return response.data or []
        except Exception as exc:
            print("DISCOVERY SCHEDULER CONNECTOR LOAD FAILED:", exc)
            return []

    @staticmethod
    def run_enabled_connectors(organization_id: str | None = None) -> dict[str, Any]:
        connectors = DiscoverySchedulerService.load_enabled_connectors(organization_id)
        connectors_by_org: dict[str, list[dict[str, Any]]] = {}

        for connector in connectors:
            org_id = resolve_organization_id(connector.get("organization_id") or organization_id)
            connectors_by_org.setdefault(org_id, []).append(connector)

        if organization_id and not connectors_by_org:
            org_id = resolve_organization_id(organization_id)
            result = DiscoverySchedulerService.run_organization_discovery(org_id, [])
            return {
                "status": result["status"],
                "organizations_processed": 1,
                "results": [result],
            }

        results = [
            DiscoverySchedulerService.run_organization_discovery(org_id, org_connectors)
            for org_id, org_connectors in sorted(connectors_by_org.items())
        ]
        failed = sum(1 for result in results if result.get("status") == "FAILED")
        partial = sum(1 for result in results if result.get("status") == "PARTIAL")

        status = "SUCCESS"
        if failed and failed == len(results):
            status = "FAILED"
        elif failed or partial:
            status = "PARTIAL"

        return {
            "status": status,
            "organizations_processed": len(results),
            "results": results,
        }

    @staticmethod
    def run_organization_discovery(
        organization_id: str | None = None,
        connectors: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        organization_id = resolve_organization_id(organization_id)
        started_at = datetime.now(timezone.utc)
        connector_configs = connectors if connectors is not None else DiscoverySchedulerService.load_enabled_connectors(
            organization_id
        )
        connector_results: list[dict[str, Any]] = []

        for connector in connector_configs:
            connector_results.append(
                DiscoverySchedulerService._run_connector(connector, organization_id)
            )

        identity_result = DiscoverySchedulerService._refresh_asset_identities(organization_id)
        quality_result = DiscoverySchedulerService._refresh_relationship_quality(organization_id)
        completed_at = datetime.now(timezone.utc)
        status = DiscoverySchedulerService._batch_status(connector_results, identity_result, quality_result)

        summary = {
            "status": status,
            "organization_id": organization_id,
            "connectors_attempted": len(connector_configs),
            "connectors_succeeded": sum(1 for item in connector_results if item.get("status") == "SUCCESS"),
            "connectors_failed": sum(1 for item in connector_results if item.get("status") == "FAILED"),
            "connectors_skipped": sum(1 for item in connector_results if item.get("status") == "SKIPPED"),
            "connector_results": connector_results,
            "asset_identity_refresh": identity_result,
            "relationship_quality_refresh": quality_result,
            "duration_seconds": (completed_at - started_at).total_seconds(),
        }
        DiscoverySchedulerService._write_sync_result(
            organization_id=organization_id,
            started_at=started_at,
            completed_at=completed_at,
            summary=summary,
        )
        return summary

    @staticmethod
    def run_scheduled_discovery(organization_id: str | None = None) -> dict[str, Any]:
        return DiscoverySchedulerService.run_enabled_connectors(organization_id)

    @staticmethod
    def _run_connector(connector: dict[str, Any], organization_id: str) -> dict[str, Any]:
        connector_name = str(connector.get("connector_name") or "").strip()
        metadata = connector.get("metadata") or {}
        started_at = datetime.now(timezone.utc)

        try:
            if connector_name.lower() == "aws":
                result = AWSConnectorService.sync_all(
                    role_arn=metadata.get("role_arn"),
                    external_id=metadata.get("external_id"),
                    region=metadata.get("region") or "us-east-1",
                    organization_id=organization_id,
                )
            elif connector_name.lower() == "azure":
                result = AzureConnectorService.sync_all(
                    tenant_id=metadata.get("tenant_id"),
                    client_id=metadata.get("client_id"),
                    client_secret=metadata.get("client_secret"),
                    subscription_id=metadata.get("subscription_id"),
                    organization_id=organization_id,
                )
            else:
                return {
                    "connector_name": connector_name or "Unknown",
                    "status": "SKIPPED",
                    "message": "No scheduled sync handler is registered for this connector.",
                }

            status = result.get("status") or "FAILED"
            return {
                "connector_name": connector_name,
                "status": status,
                "objects_synced": int(result.get("objects_synced") or 0),
                "assets_discovered": int(result.get("assets_discovered") or 0),
                "error": result.get("error"),
                "duration_seconds": (datetime.now(timezone.utc) - started_at).total_seconds(),
                "raw_result": result,
            }
        except Exception as exc:
            return {
                "connector_name": connector_name or "Unknown",
                "status": "FAILED",
                "error": str(exc),
                "duration_seconds": (datetime.now(timezone.utc) - started_at).total_seconds(),
            }

    @staticmethod
    def _refresh_asset_identities(organization_id: str) -> dict[str, Any]:
        try:
            return EnterpriseAssetIdentityService.sync_asset_identities(organization_id)
        except Exception as exc:
            return {
                "status": "FAILED",
                "error": str(exc),
            }

    @staticmethod
    def _refresh_relationship_quality(organization_id: str) -> dict[str, Any]:
        try:
            quality = EnterpriseRelationshipIntelligenceService.get_relationship_quality_score(organization_id)
            return {
                "status": "SUCCESS",
                "quality": quality,
            }
        except Exception as exc:
            return {
                "status": "FAILED",
                "error": str(exc),
            }

    @staticmethod
    def _batch_status(
        connector_results: list[dict[str, Any]],
        identity_result: dict[str, Any],
        quality_result: dict[str, Any],
    ) -> str:
        failures = [
            item
            for item in connector_results
            if item.get("status") == "FAILED"
        ]
        refresh_failed = identity_result.get("status") == "FAILED" or quality_result.get("status") == "FAILED"

        if failures and len(failures) == len(connector_results) and refresh_failed:
            return "FAILED"
        if failures or refresh_failed:
            return "PARTIAL"
        return "SUCCESS"

    @staticmethod
    def _write_sync_result(
        organization_id: str,
        started_at: datetime,
        completed_at: datetime,
        summary: dict[str, Any],
    ) -> None:
        error_message = None
        if summary.get("status") != "SUCCESS":
            error_message = json.dumps(
                {
                    "status": summary.get("status"),
                    "connector_results": summary.get("connector_results", []),
                    "asset_identity_refresh": summary.get("asset_identity_refresh"),
                    "relationship_quality_refresh": summary.get("relationship_quality_refresh"),
                },
                default=str,
            )[:4000]

        try:
            insert_sync_history(
                connector_name=DiscoverySchedulerService.ORCHESTRATOR_NAME,
                sync_status=summary.get("status") or "FAILED",
                started_at=started_at,
                completed_at=completed_at,
                duration_seconds=(completed_at - started_at).total_seconds(),
                accounts_synced=0,
                costs_synced=0,
                resources_synced=sum(
                    int(item.get("objects_synced") or 0)
                    for item in summary.get("connector_results", [])
                ),
                recommendations_synced=0,
                assets_discovered=sum(
                    int(item.get("assets_discovered") or 0)
                    for item in summary.get("connector_results", [])
                ),
                error_message=error_message,
                organization_id=organization_id,
            )
        except Exception as exc:
            print("DISCOVERY SCHEDULER RESULT WRITE FAILED:", exc)
