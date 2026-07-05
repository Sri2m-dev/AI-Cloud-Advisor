"""Core connector data contracts for Nexora Enterprise Data Fabric ingestion."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Mapping, Sequence


class ConnectorSyncState(str, Enum):
    """Standard lifecycle states for connector sync execution."""

    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    PARTIAL = "partial"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass(frozen=True)
class ConnectorMetadata:
    """Describes a connector and its supported capabilities."""

    connector_id: str
    name: str
    provider: str
    category: str
    version: str = "0.1.0"
    description: str = ""
    supports_full_sync: bool = True
    supports_incremental_sync: bool = False
    supports_webhooks: bool = False
    supported_entities: tuple[str, ...] = field(default_factory=tuple)
    owner: str = "Nexora"


@dataclass(frozen=True)
class ConnectorAuthConfig:
    """Authentication configuration reference for a connector.

    Secret values should not be stored directly in this object. Use
    secret_ref to point to a secret manager, environment variable, or vault
    entry resolved by the connector_secrets layer.
    """

    auth_type: str
    secret_ref: str | None = None
    tenant_id: str | None = None
    account_id: str | None = None
    scopes: tuple[str, ...] = field(default_factory=tuple)
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ConnectorRecord:
    """Canonical raw-to-normalized connector record envelope."""

    source_id: str
    entity_type: str
    payload: Mapping[str, Any]
    observed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    source_updated_at: datetime | None = None
    checksum: str | None = None


@dataclass(frozen=True)
class ConnectorHealthStatus:
    """Health payload emitted by every connector."""

    connector_id: str
    status: str
    checked_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    message: str = ""
    last_success_at: datetime | None = None
    last_failure_at: datetime | None = None
    consecutive_failures: int = 0
    latency_ms: int | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ConnectorSyncResult:
    """Standard result returned by full and incremental sync operations."""

    connector_id: str
    state: ConnectorSyncState
    started_at: datetime
    finished_at: datetime
    records_extracted: int = 0
    records_normalized: int = 0
    records_published: int = 0
    errors: tuple[str, ...] = field(default_factory=tuple)
    warnings: tuple[str, ...] = field(default_factory=tuple)
    checkpoint: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    @property
    def duration_ms(self) -> int:
        """Return elapsed sync duration in milliseconds."""

        return int((self.finished_at - self.started_at).total_seconds() * 1000)

    @classmethod
    def skipped(cls, connector_id: str, reason: str) -> "ConnectorSyncResult":
        """Create a skipped result for unsupported sync paths."""

        now = datetime.now(timezone.utc)
        return cls(
            connector_id=connector_id,
            state=ConnectorSyncState.SKIPPED,
            started_at=now,
            finished_at=now,
            warnings=(reason,),
        )


ConnectorRecords = Sequence[ConnectorRecord]
