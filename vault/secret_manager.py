from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timezone
from typing import Any


class SecretManager:
    @staticmethod
    def create_secret_ref(organization_id: str, connector_name: str, secret_payload: dict[str, Any]) -> dict[str, Any]:
        secret_id = str(uuid.uuid4())
        fingerprint = hashlib.sha256(repr(sorted(secret_payload.items())).encode()).hexdigest()
        return {
            "id": secret_id,
            "organization_id": organization_id,
            "connector_name": connector_name,
            "secret_ref": f"vault://connector/{connector_name.lower().replace(' ', '-')}/{secret_id}",
            "fingerprint": fingerprint,
            "masked_keys": sorted(secret_payload.keys()),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "provider": "Supabase encrypted secrets",
        }

    @staticmethod
    def mask(secret_payload: dict[str, Any]) -> dict[str, str]:
        return {key: "***stored-in-vault***" for key in secret_payload}
