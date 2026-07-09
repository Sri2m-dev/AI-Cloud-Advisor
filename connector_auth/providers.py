"""Credential provider abstractions for connector authentication."""

from __future__ import annotations

from abc import ABC, abstractmethod

from connector_auth.credentials import ConnectorCredential, ConnectorCredentialRequest
from connector_secrets import SecretProvider


class CredentialProvider(ABC):
    """Base credential provider."""

    @abstractmethod
    def load(self, request: ConnectorCredentialRequest) -> ConnectorCredential:
        """Load credentials for the requested auth type."""


class SecretBackedCredentialProvider(CredentialProvider):
    """Credential provider backed by a SecretProvider."""

    def __init__(self, secret_provider: SecretProvider) -> None:
        self.secret_provider = secret_provider

    def load(self, request: ConnectorCredentialRequest) -> ConnectorCredential:
        principal = self.secret_provider.resolve(request.principal_ref) if request.principal_ref else None
        secret = self.secret_provider.resolve(request.secret_ref) if request.secret_ref else None
        token = self.secret_provider.resolve(request.token_ref) if request.token_ref else None
        return ConnectorCredential(
            auth_type=request.auth_type,
            principal=principal,
            secret=secret or token,
            scopes=request.scopes,
            metadata=request.metadata,
        )
