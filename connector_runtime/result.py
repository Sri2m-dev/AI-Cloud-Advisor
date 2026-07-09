"""Connector execution result contracts."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Mapping

from connector_sdk import ConnectorHealthStatus, ConnectorSyncState
from connector_runtime.policy import ConnectorExecutionMode


@dataclass(frozen=True)
class ConnectorExecutionResult:
    """Observable result emitted by the connector execution engine."""

    execution_id: str
    connector_id: str
    mode: ConnectorExecutionMode
    state: ConnectorSyncState
    started_at: datetime
    finished_at: datetime
    records_extracted: int = 0
    records_normalized: int = 0
    records_published: int = 0
    warnings: tuple[str, ...] = field(default_factory=tuple)
    errors: tuple[str, ...] = field(default_factory=tuple)
    health_status: ConnectorHealthStatus | None = None
    next_sync_at: datetime | None = None
    checkpoint: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    @property
    def duration_ms(self) -> int:
        return int((self.finished_at - self.started_at).total_seconds() * 1000)
