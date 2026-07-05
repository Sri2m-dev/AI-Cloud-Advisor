"""Connector health monitoring contracts."""

from __future__ import annotations

from connector_sdk import BaseConnector, ConnectorHealthStatus


class ConnectorHealthMonitor:
    """Collect health status from registered connector instances."""

    def check(self, connector: BaseConnector) -> ConnectorHealthStatus:
        return connector.health()

    def check_all(self, connectors: list[BaseConnector]) -> list[ConnectorHealthStatus]:
        return [self.check(connector) for connector in connectors]
