"""API key and bearer token authentication handlers."""

from __future__ import annotations

from connector_auth.credentials import ConnectorAuthContext, ConnectorAuthType, ConnectorCredential


class ApiKeyAuthenticator:
    """Creates auth contexts for API key and bearer token credentials."""

    def authenticate(self, credential: ConnectorCredential) -> ConnectorAuthContext:
        return ConnectorAuthContext(
            auth_type=credential.auth_type,
            authenticated=True,
            principal=credential.principal,
            token=credential.secret,
            credential=credential,
            expires_at=credential.expires_at,
            metadata={"scheme": "bearer" if credential.auth_type == ConnectorAuthType.BEARER_TOKEN else "api_key"},
        )
