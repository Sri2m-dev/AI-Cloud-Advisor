from __future__ import annotations

from typing import Any

from azure.core.exceptions import AzureError
from azure.identity import ClientSecretCredential, DefaultAzureCredential


class AzureCredentialManager:
    def __init__(
        self,
        tenant_id: str | None = None,
        client_id: str | None = None,
        client_secret: str | None = None,
        subscription_id: str | None = None,
    ):
        self.tenant_id = tenant_id
        self.client_id = client_id
        self.client_secret = client_secret
        self.subscription_id = subscription_id

    def credential(self):
        if self.tenant_id and self.client_id and self.client_secret:
            return ClientSecretCredential(
                tenant_id=self.tenant_id,
                client_id=self.client_id,
                client_secret=self.client_secret,
            )
        return DefaultAzureCredential(exclude_interactive_browser_credential=True)

    def test_connection(self) -> dict[str, Any]:
        try:
            credential = self.credential()
            token = credential.get_token("https://management.azure.com/.default")
            return {
                "status": "CONNECTED",
                "subscription_id": self.subscription_id,
                "expires_on": token.expires_on,
            }
        except AzureError as exc:
            return {
                "status": "FAILED",
                "error": str(exc),
            }
