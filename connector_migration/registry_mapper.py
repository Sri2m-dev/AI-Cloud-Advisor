"""Map legacy cloud connection records into connector_registry-compatible payloads."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping


class ConnectorRegistryMapper:
    """Create connector_registry-compatible payloads from older connection rows."""

    @staticmethod
    def from_cloud_connection(record: Mapping[str, Any], *, organization_id: str | None = None, configured_by: str | None = None) -> dict[str, Any]:
        provider = ConnectorRegistryMapper._provider(record)
        connector_name = ConnectorRegistryMapper.connector_name(provider)
        metadata = ConnectorRegistryMapper.metadata_for_provider(provider, record)
        return {
            "connector_name": connector_name,
            "connector_type": "CLOUD",
            "provider": ConnectorRegistryMapper.provider_label(provider),
            "status": ConnectorRegistryMapper.status(record),
            "sync_frequency": record.get("sync_frequency") or "DAILY",
            "enabled": ConnectorRegistryMapper.enabled(record),
            "organization_id": organization_id or record.get("organization_id") or record.get("org_id"),
            "configured_by": configured_by or record.get("configured_by"),
            "metadata": metadata,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

    @staticmethod
    def connector_name(provider: str) -> str:
        normalized = provider.upper()
        if normalized == "AWS":
            return "AWS"
        if normalized == "AZURE":
            return "Azure"
        if normalized == "GCP":
            return "GCP"
        return provider.title() if provider else "Unknown"

    @staticmethod
    def provider_label(provider: str) -> str:
        if provider.upper() == "AWS":
            return "AWS"
        if provider.upper() == "AZURE":
            return "Azure"
        if provider.upper() == "GCP":
            return "GCP"
        return provider.title() if provider else "Unknown"

    @staticmethod
    def metadata_for_provider(provider: str, record: Mapping[str, Any]) -> dict[str, Any]:
        normalized = provider.upper()
        if normalized == "AWS":
            return {
                "account_name": record.get("account_name"),
                "account_id": record.get("account_id"),
                "role_arn": record.get("role_arn"),
                "external_id": record.get("external_id"),
                "region": record.get("region") or "us-east-1",
                "source_table": "cloud_connections",
            }
        if normalized == "AZURE":
            return {
                "tenant_id": record.get("tenant_id"),
                "client_id": record.get("client_id") or record.get("account_id"),
                "subscription_id": record.get("subscription_id"),
                "source_table": "cloud_connections",
            }
        if normalized == "GCP":
            return {
                "project_id": record.get("project_id") or record.get("account_id"),
                "source_table": "cloud_connections",
            }
        return {"source_table": "cloud_connections", "raw": dict(record)}

    @staticmethod
    def status(record: Mapping[str, Any]) -> str:
        raw = str(record.get("status") or "NOT_CONFIGURED").upper()
        if raw in {"CONNECTED", "CONFIGURED", "DISABLED", "FAILED", "SYNCING", "NOT_CONFIGURED"}:
            return raw
        if raw == "PENDING":
            return "CONFIGURED"
        return raw

    @staticmethod
    def enabled(record: Mapping[str, Any]) -> bool:
        if "enabled" in record:
            return bool(record.get("enabled"))
        status = str(record.get("status") or "").upper()
        return status not in {"DISABLED", "FAILED"}

    @staticmethod
    def _provider(record: Mapping[str, Any]) -> str:
        return str(record.get("provider") or record.get("cloud_provider") or record.get("cloud") or "").upper()
