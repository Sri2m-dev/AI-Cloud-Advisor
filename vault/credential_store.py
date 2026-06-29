from __future__ import annotations

from typing import Any

from connectors.common.tenant_guard import resolve_organization_id
from repositories.enterprise_connector_repository import EnterpriseConnectorRepository
from vault.secret_manager import SecretManager


class CredentialStore:
    @staticmethod
    def store(connector_name: str, credentials: dict[str, Any], organization_id: str | None = None) -> dict[str, Any]:
        org_id = resolve_organization_id(organization_id)
        secret = SecretManager.create_secret_ref(org_id, connector_name, credentials)
        EnterpriseConnectorRepository.save_credential_ref(
            {
                **secret,
                "secret_payload": SecretManager.mask(credentials),
                "status": "Active",
            },
        )
        return secret

    @staticmethod
    def retrieve_reference(connector_name: str, organization_id: str | None = None) -> dict[str, Any]:
        return EnterpriseConnectorRepository.get_credential_ref(connector_name, organization_id)
