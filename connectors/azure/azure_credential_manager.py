from __future__ import annotations

import uuid
from typing import Any

from azure.identity import ClientSecretCredential, DefaultAzureCredential
from azure.mgmt.resource.resources import ResourceManagementClient

from connector_secrets import EnvironmentSecretProvider, SecretProvider

RUNTIME_IDENTITY = "runtime_identity"
SERVICE_PRINCIPAL = "service_principal"
AUTH_METHODS = (RUNTIME_IDENTITY, SERVICE_PRINCIPAL)

_ARM_SCOPE = "https://management.azure.com/.default"


class AzureConnectionConfigurationError(ValueError):
    """Raised when the selected Azure authentication method cannot be satisfied."""


class AzureCredentialManager:
    def __init__(
        self,
        tenant_id: str | None = None,
        client_id: str | None = None,
        client_secret: str | None = None,
        subscription_id: str | None = None,
        *,
        auth_method: str | None = None,
        secret_ref: str | None = None,
        secret_provider: SecretProvider | None = None,
    ):
        if auth_method is not None and auth_method not in AUTH_METHODS:
            raise AzureConnectionConfigurationError("Unsupported Azure authentication method.")
        self.auth_method = auth_method
        if auth_method == RUNTIME_IDENTITY:
            # Runtime identity never consumes service-principal material.
            tenant_id = client_id = client_secret = secret_ref = None
        self.tenant_id = tenant_id
        self.client_id = client_id
        self.client_secret = client_secret
        self.subscription_id = subscription_id
        self.secret_ref = secret_ref
        self.secret_provider = secret_provider or EnvironmentSecretProvider()

    def credential(self):
        if self.auth_method == RUNTIME_IDENTITY:
            return DefaultAzureCredential(exclude_interactive_browser_credential=True)

        if self.auth_method == SERVICE_PRINCIPAL:
            secret = self.client_secret or self._resolve_secret_ref()
            if not (self.tenant_id and self.client_id and secret):
                raise AzureConnectionConfigurationError(
                    "Service principal access requires a Tenant ID, a Client ID and a "
                    "credential reference that this environment can resolve."
                )
            return ClientSecretCredential(
                tenant_id=self.tenant_id,
                client_id=self.client_id,
                client_secret=secret,
            )

        if self.tenant_id and self.client_id and self.client_secret:
            return ClientSecretCredential(
                tenant_id=self.tenant_id,
                client_id=self.client_id,
                client_secret=self.client_secret,
            )
        return DefaultAzureCredential(exclude_interactive_browser_credential=True)

    def _resolve_secret_ref(self) -> str | None:
        if not self.secret_ref:
            return None
        return self.secret_provider.resolve(self.secret_ref)

    def test_connection(self) -> dict[str, Any]:
        """Read-only: authenticate, then read the exact subscription. Never persists."""
        checks = {
            "authentication": "NOT_TESTED",
            "subscription_access": "NOT_TESTED",
            "resource_discovery": "NOT_TESTED",
            "cost_management": "NOT_TESTED",
        }

        def failed(message: str) -> dict[str, Any]:
            return {
                "status": "FAILED",
                "error": message,
                "checks": checks,
                "subscription_id": self.subscription_id,
            }

        subscription_id = (self.subscription_id or "").strip()
        try:
            uuid.UUID(subscription_id)
        except ValueError:
            return failed("A valid Azure Subscription ID is required.")

        try:
            credential = self.credential()
            token = credential.get_token(_ARM_SCOPE)
        except AzureConnectionConfigurationError as exc:
            checks["authentication"] = "FAIL"
            return failed(str(exc))
        except Exception:  # noqa: BLE001 - provider errors can carry sensitive detail
            checks["authentication"] = "FAIL"
            return failed("Azure authentication failed for the selected authentication method.")
        checks["authentication"] = "PASS"

        client = ResourceManagementClient(credential, subscription_id)
        try:
            next(iter(client.resource_groups.list()), None)
        except Exception:  # noqa: BLE001
            checks["subscription_access"] = "FAIL"
            return failed(
                "The subscription could not be read with this identity. Check the "
                "Subscription ID and that read-only access has been granted."
            )
        checks["subscription_access"] = "PASS"

        try:
            next(iter(client.resources.list()), None)
        except Exception:  # noqa: BLE001
            checks["resource_discovery"] = "FAIL"
            return failed("This identity cannot list resources in the subscription.")
        checks["resource_discovery"] = "PASS"

        return {
            "status": "CONNECTED",
            "subscription_id": subscription_id,
            "expires_on": token.expires_on,
            "checks": checks,
        }
