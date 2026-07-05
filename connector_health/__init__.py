"""Connector health monitoring contracts and in-memory health store."""

from __future__ import annotations

from dataclasses import dataclass, field

from connector_sdk import BaseConnector, ConnectorHealthStatus


@dataclass
class ConnectorHealthStore:
    """In-memory store for latest connector health snapshots."""

    _snapshots: dict[str, ConnectorHealthStatus] = field(default_factory=dict)

    def record_health_snapshot(self, status: ConnectorHealthStatus) -> ConnectorHealthStatus:
        self._snapshots[status.connector_id] = status
        return status

    def get_latest_health(self, connector_id: str) -> ConnectorHealthStatus | None:
        return self._snapshots.get(connector_id)

    def list_health(self) -> list[ConnectorHealthStatus]:
        return list(self._snapshots.values())

    def clear(self) -> None:
        self._snapshots.clear()


class ConnectorHealthMonitor:
    """Collect health status from registered connector instances."""

    def __init__(self, store: ConnectorHealthStore | None = None) -> None:
        self.store = store or ConnectorHealthStore()

    def check(self, connector: BaseConnector) -> ConnectorHealthStatus:
        status = connector.health()
        self.store.record_health_snapshot(status)
        return status

    def check_all(self, connectors: list[BaseConnector]) -> list[ConnectorHealthStatus]:
        return [self.check(connector) for connector in connectors]


health_store = ConnectorHealthStore()


def record_health_snapshot(status: ConnectorHealthStatus) -> ConnectorHealthStatus:
    return health_store.record_health_snapshot(status)


def get_latest_health(connector_id: str) -> ConnectorHealthStatus | None:
    return health_store.get_latest_health(connector_id)
