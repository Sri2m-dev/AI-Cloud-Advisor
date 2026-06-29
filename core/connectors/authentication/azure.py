from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class AzureAuthConfig:
    tenant_id: str
    subscription_id: str
    client_id: str
    client_secret_ref: str

    def masked(self) -> dict[str, str]:
        return {
            "type": "azure",
            "tenant_id": self.tenant_id,
            "subscription_id": self.subscription_id,
            "client_id": self.client_id,
            "client_secret_ref": self.client_secret_ref,
        }
