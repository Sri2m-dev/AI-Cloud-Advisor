"""Access key authentication handlers."""

from __future__ import annotations

from connector_auth.credentials import ConnectorAuthContext, ConnectorCredential


class AccessKeyAuthenticator:
    """Creates auth contexts for access-key style credentials."""

    def authenticate(self, credential: ConnectorCredential) -> ConnectorAuthContext:
        return ConnectorAuthContext(
            auth_type=credential.auth_type,
            authenticated=True,
            principal=credential.principal,
            token=credential.secret,
            credential=credential,
            expires_at=credential.expires_at,
            metadata={"scheme": "access_key"},
        )
