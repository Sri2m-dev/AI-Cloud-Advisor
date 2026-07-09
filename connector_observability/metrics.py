"""Connector metrics collection contracts."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from connector_sdk import ConnectorSyncState


@dataclass(frozen=True)
class ConnectorMetricsSnapshot:
    """Aggregated operational metrics for connector execution."""

    connector_id: str | None = None
    executions_started: int = 0
    executions_completed: int = 0
    executions_failed: int = 0
    records_extracted: int = 0
    records_normalized: int = 0
    records_published: int = 0
    retry_count: int = 0
    queue_depth: int = 0
    total_duration_ms: int = 0
    metadata: Mapping[str, Any] = field(default_factory=dict)

    @property
    def success_rate(self) -> float:
        if self.executions_completed == 0:
            return 0.0
        successful = self.executions_completed - self.executions_failed
        return round((successful / self.executions_completed) * 100, 2)

    @property
    def failure_rate(self) -> float:
        if self.executions_completed == 0:
            return 0.0
        return round((self.executions_failed / self.executions_completed) * 100, 2)

    @property
    def average_duration_ms(self) -> int:
        if self.executions_completed == 0:
            return 0
        return int(self.total_duration_ms / self.executions_completed)


@dataclass
class _MutableMetrics:
    connector_id: str | None = None
    executions_started: int = 0
    executions_completed: int = 0
    executions_failed: int = 0
    records_extracted: int = 0
    records_normalized: int = 0
    records_published: int = 0
    retry_count: int = 0
    queue_depth: int = 0
    total_duration_ms: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    def snapshot(self) -> ConnectorMetricsSnapshot:
        return ConnectorMetricsSnapshot(
            connector_id=self.connector_id,
            executions_started=self.executions_started,
            executions_completed=self.executions_completed,
            executions_failed=self.executions_failed,
            records_extracted=self.records_extracted,
            records_normalized=self.records_normalized,
            records_published=self.records_published,
            retry_count=self.retry_count,
            queue_depth=self.queue_depth,
            total_duration_ms=self.total_duration_ms,
            metadata=dict(self.metadata),
        )


class ConnectorMetricsCollector:
    """In-memory metrics collector for connector platform operations."""

    def __init__(self) -> None:
        self._metrics: dict[str | None, _MutableMetrics] = {None: _MutableMetrics()}

    def record_execution_started(self, connector_id: str) -> None:
        self._bucket(connector_id).executions_started += 1
        self._bucket(None).executions_started += 1

    def record_execution_completed(
        self,
        connector_id: str,
        *,
        state: ConnectorSyncState | str,
        duration_ms: int = 0,
        records_extracted: int = 0,
        records_normalized: int = 0,
        records_published: int = 0,
    ) -> None:
        failed = str(getattr(state, "value", state)) == ConnectorSyncState.FAILED.value
        for bucket in (self._bucket(connector_id), self._bucket(None)):
            bucket.executions_completed += 1
            bucket.executions_failed += 1 if failed else 0
            bucket.total_duration_ms += max(duration_ms, 0)
            bucket.records_extracted += max(records_extracted, 0)
            bucket.records_normalized += max(records_normalized, 0)
            bucket.records_published += max(records_published, 0)

    def record_retry(self, connector_id: str, count: int = 1) -> None:
        for bucket in (self._bucket(connector_id), self._bucket(None)):
            bucket.retry_count += max(count, 0)

    def record_queue_depth(self, depth: int, connector_id: str | None = None) -> None:
        self._bucket(connector_id).queue_depth = max(depth, 0)

    def get_metrics(self, connector_id: str | None = None) -> ConnectorMetricsSnapshot:
        return self._bucket(connector_id).snapshot()

    def list_metrics(self) -> list[ConnectorMetricsSnapshot]:
        return [bucket.snapshot() for bucket in self._metrics.values()]

    def clear(self) -> None:
        self._metrics = {None: _MutableMetrics()}

    def _bucket(self, connector_id: str | None) -> _MutableMetrics:
        if connector_id not in self._metrics:
            self._metrics[connector_id] = _MutableMetrics(connector_id=connector_id)
        return self._metrics[connector_id]


metrics_collector = ConnectorMetricsCollector()
