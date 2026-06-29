"""Shared connector primitives for cloud, SaaS, and AI integrations."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class SyncResult:
    connector_name: str
    status: str
    last_sync: str
    objects_synced: int
    sync_frequency: str
    tables_populated: list[str] = field(default_factory=list)
    sources: list[str] = field(default_factory=list)
    details: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "connector_name": self.connector_name,
            "status": self.status,
            "last_sync": self.last_sync,
            "objects_synced": self.objects_synced,
            "sync_frequency": self.sync_frequency,
            "tables_populated": self.tables_populated,
            "sources": self.sources,
            "details": self.details,
        }


class BaseConnector:
    connector_name = "Unknown"
    status = "NOT_CONFIGURED"
    sync_frequency = "DAILY"
    sources: list[str] = []
    tables_populated: list[str] = []

    def __init__(self, credentials: dict[str, Any] | None = None, org_id: str | None = None):
        self.credentials = credentials or {}
        self.org_id = org_id

    def connector_status(self, objects_synced: int = 0, status: str | None = None) -> dict[str, Any]:
        return SyncResult(
            connector_name=self.connector_name,
            status=status or self.status,
            last_sync=utc_now_iso(),
            objects_synced=objects_synced,
            sync_frequency=self.sync_frequency,
            tables_populated=self.tables_populated,
            sources=self.sources,
        ).as_dict()

    def _sync_result(
        self,
        method: str,
        objects_synced: int,
        tables_populated: list[str] | None = None,
        sources: list[str] | None = None,
    ) -> dict[str, Any]:
        return SyncResult(
            connector_name=self.connector_name,
            status="CONNECTED",
            last_sync=utc_now_iso(),
            objects_synced=objects_synced,
            sync_frequency=self.sync_frequency,
            tables_populated=tables_populated or self.tables_populated,
            sources=sources or self.sources,
            details={"method": method, "mode": "adapter_ready"},
        ).as_dict()

