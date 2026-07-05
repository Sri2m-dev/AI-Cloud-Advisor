"""Connector registry for discovering and instantiating connector classes."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Type

from connector_sdk import BaseConnector, ConnectorMetadata


@dataclass
class ConnectorRegistry:
    """In-memory connector registry.

    Future releases can back this with persistent configuration, tenant-level
    enablement, and connector package discovery.
    """

    _connectors: dict[str, Type[BaseConnector]] = field(default_factory=dict)

    def register(self, connector_cls: Type[BaseConnector]) -> None:
        metadata = connector_cls.metadata
        self._connectors[metadata.connector_id] = connector_cls

    def get(self, connector_id: str) -> Type[BaseConnector] | None:
        return self._connectors.get(connector_id)

    def list_metadata(self) -> list[ConnectorMetadata]:
        return [connector_cls.metadata for connector_cls in self._connectors.values()]

    def clear(self) -> None:
        self._connectors.clear()


registry = ConnectorRegistry()
