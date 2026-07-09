"""Connector authentication credential contracts."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Mapping


class ConnectorAuthType(str, Enum):
    AWS_ACCESS_KEY = "aws_access_key"
    AWS_ASSUME_ROLE = "aws_assume_role"
    AZURE_SERVICE_PRINCIPAL = "azure_service_principal"
    AZURE_MANAGED_IDENTITY = "azure_managed_identity"
    OAUTH2_CLIENT_CREDENTIALS = "oauth2_client_credentials"
    OAUTH2_AUTHORIZATION_CODE = "oauth2_authorization_code"
    API_KEY = "api_key"
    BEARER_TOKEN = "bearer_token"
    BASIC = "basic"
    CERTIFICATE = "certificate"
    ANONYMOUS = "anonymous"


@dataclass(frozen=True)
class ConnectorCredential:
    """Base credential payload.

    Values should be resolved from a secret provider and kept out of logs.
    """

    auth_type: ConnectorAuthType
    principal: str | None = None
    secret: str | None = None
    scopes: tuple[str, ...] = field(default_factory=tuple)
    expires_at: datetime | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    @property
    def expired(self) -> bool:
        return self.expires_at is not None and self.expires_at <= datetime.now(timezone.utc)


@dataclass(frozen=True)
class ConnectorAuthContext:
    """Authenticated context returned to connectors and runtimes."""

    auth_type: ConnectorAuthType
    authenticated: bool
    principal: str | None = None
    token: str | None = None
    credential: ConnectorCredential | None = None
    expires_at: datetime | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    @property
    def expired(self) -> bool:
        return self.expires_at is not None and self.expires_at <= datetime.now(timezone.utc)


@dataclass(frozen=True)
class ConnectorCredentialRequest:
    """Credential acquisition request."""

    auth_type: ConnectorAuthType
    secret_ref: str | None = None
    principal_ref: str | None = None
    token_ref: str | None = None
    scopes: tuple[str, ...] = field(default_factory=tuple)
    metadata: Mapping[str, Any] = field(default_factory=dict)
