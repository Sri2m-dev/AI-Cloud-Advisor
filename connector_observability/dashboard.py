"""Connector operations dashboard model."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Mapping

from connector_health import ConnectorHealthStore
from connector_logs import ConnectorLogger
from connector_observability.alerts import ConnectorAlert
from connector_observability.metrics import ConnectorMetricsCollector, ConnectorMetricsSnapshot
from connector_registry import ConnectorRegistry, ConnectorSyncStateStore
from connector_sdk import ConnectorSyncState


@dataclass(frozen=True)
class ConnectorOperationsSnapshot:
    """Standard dashboard-ready connector operations model."""

    connector_id: str
    name: str
    provider: str
    enabled: bool
    status: str = "unknown"
    last_successful_sync: datetime | None = None
    current_queue_state: str = "unknown"
    average_duration_ms: int = 0
    error_summary: tuple[str, ...] = field(default_factory=tuple)
    health_score: float = 0.0
    sla_compliance: str = "unknown"
    metrics: ConnectorMetricsSnapshot | None = None
    alerts: tuple[ConnectorAlert, ...] = field(default_factory=tuple)
    metadata: Mapping[str, Any] = field(default_factory=dict)


class ConnectorDashboardBuilder:
    """Build dashboard snapshots from registry, state, health, logs, and metrics."""

    def __init__(
        self,
        registry: ConnectorRegistry,
        sync_state_store: ConnectorSyncStateStore,
        health_store: ConnectorHealthStore,
        logger: ConnectorLogger,
        metrics_collector: ConnectorMetricsCollector,
    ) -> None:
        self.registry = registry
        self.sync_state_store = sync_state_store
        self.health_store = health_store
        self.logger = logger
        self.metrics_collector = metrics_collector

    def build(self, connector_id: str, *, alerts: list[ConnectorAlert] | None = None, queue_state: str = "unknown") -> ConnectorOperationsSnapshot | None:
        record = self.registry.get_connector(connector_id)
        if record is None:
            return None
        health = self.health_store.get_latest_health(connector_id)
        sync_state = self.sync_state_store.get_sync_state(connector_id)
        logs = self.logger.list_run_logs(connector_id=connector_id)
        errors = tuple(log.message for log in logs if log.level == "error")
        metrics = self.metrics_collector.get_metrics(connector_id)
        status = health.status if health else (sync_state.state.value if sync_state else "unknown")
        health_score = self._health_score(status, health.consecutive_failures if health else 0)
        sla_compliance = "met" if health and health.last_success_at else "unknown"
        if sync_state and sync_state.state == ConnectorSyncState.FAILED:
            sla_compliance = "at_risk"
        return ConnectorOperationsSnapshot(
            connector_id=connector_id,
            name=record.metadata.name,
            provider=record.metadata.provider,
            enabled=record.enabled,
            status=status,
            last_successful_sync=health.last_success_at if health else None,
            current_queue_state=queue_state,
            average_duration_ms=metrics.average_duration_ms,
            error_summary=errors,
            health_score=health_score,
            sla_compliance=sla_compliance,
            metrics=metrics,
            alerts=tuple(alerts or ()),
            metadata={"category": record.metadata.category, "version": record.metadata.version},
        )

    def list_snapshots(self) -> list[ConnectorOperationsSnapshot]:
        snapshots: list[ConnectorOperationsSnapshot] = []
        for record in self.registry.list_connectors():
            snapshot = self.build(record.metadata.connector_id)
            if snapshot is not None:
                snapshots.append(snapshot)
        return snapshots

    def _health_score(self, status: str, consecutive_failures: int) -> float:
        score = 100.0 if status.lower() in {"healthy", "ok", "available", "succeeded"} else 65.0
        return max(score - min(consecutive_failures * 10, 50), 0.0)
