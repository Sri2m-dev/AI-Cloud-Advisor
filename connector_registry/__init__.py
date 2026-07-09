"""Connector registry and sync state foundation."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Type

from connector_sdk import BaseConnector, ConnectorMetadata, ConnectorSyncResult, ConnectorSyncState


@dataclass(frozen=True)
class RegisteredConnector:
    """Connector registration record."""

    metadata: ConnectorMetadata
    connector_cls: Type[BaseConnector]
    enabled: bool = True
    registered_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class ConnectorRegistry:
    """In-memory connector registry.

    Future releases can back this with persistent configuration, tenant-level
    enablement, and connector package discovery.
    """

    _connectors: dict[str, RegisteredConnector] = field(default_factory=dict)

    def register_connector(self, connector_cls: Type[BaseConnector], *, enabled: bool = True) -> RegisteredConnector:
        """Register a connector class with its metadata."""

        metadata = connector_cls.metadata
        record = RegisteredConnector(metadata=metadata, connector_cls=connector_cls, enabled=enabled)
        self._connectors[metadata.connector_id] = record
        return record

    def get_connector(self, connector_id: str) -> RegisteredConnector | None:
        """Return a registered connector by ID."""

        return self._connectors.get(connector_id)

    def list_connectors(self, *, enabled_only: bool = False) -> list[RegisteredConnector]:
        """List registered connectors."""

        connectors = list(self._connectors.values())
        if enabled_only:
            return [connector for connector in connectors if connector.enabled]
        return connectors

    def enable_connector(self, connector_id: str) -> bool:
        """Enable a registered connector."""

        record = self._connectors.get(connector_id)
        if record is None:
            return False
        self._connectors[connector_id] = RegisteredConnector(
            metadata=record.metadata,
            connector_cls=record.connector_cls,
            enabled=True,
            registered_at=record.registered_at,
        )
        return True

    def disable_connector(self, connector_id: str) -> bool:
        """Disable a registered connector without removing it."""

        record = self._connectors.get(connector_id)
        if record is None:
            return False
        self._connectors[connector_id] = RegisteredConnector(
            metadata=record.metadata,
            connector_cls=record.connector_cls,
            enabled=False,
            registered_at=record.registered_at,
        )
        return True

    # Backward-compatible aliases from E8.1.1.
    def register(self, connector_cls: Type[BaseConnector]) -> None:
        self.register_connector(connector_cls)

    def get(self, connector_id: str) -> Type[BaseConnector] | None:
        record = self.get_connector(connector_id)
        return record.connector_cls if record else None

    def list_metadata(self) -> list[ConnectorMetadata]:
        return [record.metadata for record in self.list_connectors()]

    def clear(self) -> None:
        self._connectors.clear()


@dataclass
class ConnectorSyncStateStore:
    """In-memory store for latest connector sync state."""

    _states: dict[str, ConnectorSyncResult] = field(default_factory=dict)

    def record_sync_state(self, result: ConnectorSyncResult) -> ConnectorSyncResult:
        self._states[result.connector_id] = result
        return result

    def get_sync_state(self, connector_id: str) -> ConnectorSyncResult | None:
        return self._states.get(connector_id)

    def mark_running(self, connector_id: str) -> ConnectorSyncResult:
        now = datetime.now(timezone.utc)
        result = ConnectorSyncResult(
            connector_id=connector_id,
            state=ConnectorSyncState.RUNNING,
            started_at=now,
            finished_at=now,
        )
        return self.record_sync_state(result)

    def clear(self) -> None:
        self._states.clear()


registry = ConnectorRegistry()
sync_state_store = ConnectorSyncStateStore()

# Functional helpers for callers that prefer module-level access.
def register_connector(connector_cls: Type[BaseConnector], *, enabled: bool = True) -> RegisteredConnector:
    return registry.register_connector(connector_cls, enabled=enabled)


def get_connector(connector_id: str) -> RegisteredConnector | None:
    return registry.get_connector(connector_id)


def list_connectors(*, enabled_only: bool = False) -> list[RegisteredConnector]:
    return registry.list_connectors(enabled_only=enabled_only)


def enable_connector(connector_id: str) -> bool:
    return registry.enable_connector(connector_id)


def disable_connector(connector_id: str) -> bool:
    return registry.disable_connector(connector_id)


def record_sync_state(result: ConnectorSyncResult) -> ConnectorSyncResult:
    return sync_state_store.record_sync_state(result)


def get_sync_state(connector_id: str) -> ConnectorSyncResult | None:
    return sync_state_store.get_sync_state(connector_id)
