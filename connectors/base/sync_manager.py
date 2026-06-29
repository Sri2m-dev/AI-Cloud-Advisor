from __future__ import annotations

from typing import Any

from connectors.connector_registry import get_connector, run_connector_sync


class ConnectorSyncManager:
    @staticmethod
    def validate_connection(connector_name: str, credentials: dict[str, Any] | None = None, org_id: str | None = None) -> dict[str, Any]:
        connector = get_connector(connector_name, credentials=credentials, org_id=org_id)
        status = connector.connector_status(status="CONNECTED")
        return {"status": "VALID", "connector": connector_name, "details": status}

    @staticmethod
    def sync(connector_name: str) -> list[dict[str, Any]]:
        return run_connector_sync(connector_name)
