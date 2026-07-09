"""Certificate authentication handlers."""

from __future__ import annotations

from connector_auth.credentials import ConnectorAuthContext, ConnectorCredential


class CertificateAuthenticator:
    """Creates auth contexts for certificate-style credentials."""

    def authenticate(self, credential: ConnectorCredential) -> ConnectorAuthContext:
        return ConnectorAuthContext(
            auth_type=credential.auth_type,
            authenticated=True,
            principal=credential.principal,
            token="certificate-authenticated" if credential.secret else None,
            credential=credential,
            expires_at=credential.expires_at,
            metadata={"scheme": "certificate"},
        )
