from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any


class ConnectorAuthManager:
    @staticmethod
    def authenticate(connector_name: str, authentication_type: str, credentials: dict[str, Any]) -> dict[str, Any]:
        expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
        return {
            "connector_name": connector_name,
            "authentication_type": authentication_type,
            "status": "AUTHENTICATED",
            "credential_keys": sorted(credentials.keys()),
            "expires_at": expires_at.isoformat(),
            "refresh_required": authentication_type.upper() in {"OAUTH", "MICROSOFT GRAPH OAUTH", "GOOGLE OAUTH"},
        }

    @staticmethod
    def refresh_credentials(connector_name: str, credential_ref: str | None = None) -> dict[str, Any]:
        return {
            "connector_name": connector_name,
            "credential_ref": credential_ref,
            "status": "REFRESHED",
            "refreshed_at": datetime.now(timezone.utc).isoformat(),
        }
