"""Connector authentication framework exports."""

from connector_auth.auth_manager import AuthenticationManager
from connector_auth.credentials import (
    ConnectorAuthContext,
    ConnectorAuthType,
    ConnectorCredential,
    ConnectorCredentialRequest,
)
from connector_auth.providers import CredentialProvider, SecretBackedCredentialProvider
from connector_auth.token_cache import TokenCache
from connector_auth.validator import CredentialValidationResult, CredentialValidator

__all__ = [
    "AuthenticationManager",
    "ConnectorAuthContext",
    "ConnectorAuthType",
    "ConnectorCredential",
    "ConnectorCredentialRequest",
    "CredentialProvider",
    "CredentialValidationResult",
    "CredentialValidator",
    "SecretBackedCredentialProvider",
    "TokenCache",
]
