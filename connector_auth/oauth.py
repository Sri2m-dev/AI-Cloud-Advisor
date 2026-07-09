"""OAuth authentication handlers."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from connector_auth.credentials import ConnectorAuthContext, ConnectorCredential


class OAuthAuthenticator:
    """Mock-safe OAuth authenticator.

    This does not call external token endpoints. It creates a deterministic
    context from resolved credentials so providers can be tested without network
    access. Production token exchange can replace this class behind the same
    interface.
    """

    def authenticate(self, credential: ConnectorCredential) -> ConnectorAuthContext:
        token = f"oauth:{credential.principal or 'client'}"
        return ConnectorAuthContext(
            auth_type=credential.auth_type,
            authenticated=True,
            principal=credential.principal,
            token=token,
            credential=credential,
            expires_at=credential.expires_at or datetime.now(timezone.utc) + timedelta(minutes=55),
            metadata={"scheme": "oauth2", "scopes": credential.scopes},
        )
