from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timezone


class ConnectorWebhookManager:
    @staticmethod
    def register(connector_name: str, organization_id: str, event_type: str = "sync") -> dict[str, str]:
        webhook_id = str(uuid.uuid4())
        secret = hashlib.sha256(f"{organization_id}:{connector_name}:{webhook_id}".encode()).hexdigest()
        return {
            "id": webhook_id,
            "connector_name": connector_name,
            "organization_id": organization_id,
            "event_type": event_type,
            "secret_ref": secret[:24],
            "created_at": datetime.now(timezone.utc).isoformat(),
            "status": "Registered",
        }
