from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class ConnectorHealth:
    status: str
    health_score: int
    last_sync: str | None = None
    next_sync: str | None = None
    error_count: int = 0
    records_synced: int = 0
    sync_duration_seconds: float = 0
    data_freshness: str = "Unknown"
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class ConnectorSyncResult:
    connector_name: str
    status: str
    records: list[dict[str, Any]] = field(default_factory=list)
    raw_records: list[dict[str, Any]] = field(default_factory=list)
    normalized_records: list[dict[str, Any]] = field(default_factory=list)
    started_at: str = field(default_factory=utc_now)
    completed_at: str = field(default_factory=utc_now)
    errors: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


class BaseConnector:
    connector_name = "Unknown"
    category = "Other"
    version = "1.0"
    authentication_type = "API Key"

    def __init__(self, credentials: dict[str, Any] | None = None, org_id: str | None = None) -> None:
        self.credentials = credentials or {}
        self.org_id = org_id

    def authenticate(self) -> dict[str, Any]:
        return {"status": "AUTHENTICATED", "connector": self.connector_name, "authenticated_at": utc_now()}

    def refresh_credentials(self) -> dict[str, Any]:
        return {"status": "REFRESHED", "connector": self.connector_name, "refreshed_at": utc_now()}

    def validate_connection(self) -> dict[str, Any]:
        return {"status": "VALID", "connector": self.connector_name, "validated_at": utc_now()}

    def discover(self) -> list[dict[str, Any]]:
        return []

    def sync(self) -> ConnectorSyncResult:
        discovered = self.discover()
        return ConnectorSyncResult(
            connector_name=self.connector_name,
            status="SUCCESS",
            records=discovered,
            raw_records=discovered,
            normalized_records=self.normalize(discovered),
        )

    def normalize(self, records: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
        return records or []

    def health(self) -> ConnectorHealth:
        return ConnectorHealth(status="Configured", health_score=90, last_sync=utc_now(), records_synced=0)

    def disconnect(self) -> dict[str, Any]:
        return {"status": "DISCONNECTED", "connector": self.connector_name, "disconnected_at": utc_now()}
