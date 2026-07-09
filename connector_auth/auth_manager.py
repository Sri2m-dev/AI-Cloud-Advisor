"""Connector authentication manager."""

from __future__ import annotations

from connector_auth.access_key import AccessKeyAuthenticator
from connector_auth.api_key import ApiKeyAuthenticator
from connector_auth.certificate import CertificateAuthenticator
from connector_auth.credentials import ConnectorAuthContext, ConnectorAuthType, ConnectorCredentialRequest
from connector_auth.oauth import OAuthAuthenticator
from connector_auth.providers import CredentialProvider
from connector_auth.token_cache import TokenCache
from connector_auth.validator import CredentialValidator


class AuthenticationManager:
    """Provider-agnostic authentication manager for connectors."""

    def __init__(
        self,
        credential_provider: CredentialProvider,
        token_cache: TokenCache | None = None,
        validator: CredentialValidator | None = None,
    ) -> None:
        self.credential_provider = credential_provider
        self.token_cache = token_cache or TokenCache()
        self.validator = validator or CredentialValidator()
        self.api_key_authenticator = ApiKeyAuthenticator()
        self.access_key_authenticator = AccessKeyAuthenticator()
        self.oauth_authenticator = OAuthAuthenticator()
        self.certificate_authenticator = CertificateAuthenticator()

    def authenticate(self, request: ConnectorCredentialRequest, *, cache_key: str | None = None) -> ConnectorAuthContext:
        """Resolve credentials, validate, acquire context, and cache token if applicable."""

        key = cache_key or self._cache_key(request)
        cached = self.token_cache.get(key)
        if cached is not None:
            return cached

        credential = self.credential_provider.load(request)
        validation = self.validator.validate(credential)
        if not validation.valid:
            return ConnectorAuthContext(
                auth_type=request.auth_type,
                authenticated=False,
                credential=credential,
                metadata={"errors": validation.errors},
            )

        context = self._authenticate_credential(credential)
        if context.authenticated and context.token:
            self.token_cache.set(key, context)
        return context

    def _authenticate_credential(self, credential):
        if credential.auth_type == ConnectorAuthType.ANONYMOUS:
            return ConnectorAuthContext(auth_type=credential.auth_type, authenticated=True, credential=credential, metadata={"scheme": "anonymous"})

        if credential.auth_type in {ConnectorAuthType.API_KEY, ConnectorAuthType.BEARER_TOKEN}:
            return self.api_key_authenticator.authenticate(credential)

        if credential.auth_type in {
            ConnectorAuthType.AWS_ACCESS_KEY,
            ConnectorAuthType.AWS_ASSUME_ROLE,
            ConnectorAuthType.AZURE_SERVICE_PRINCIPAL,
            ConnectorAuthType.AZURE_MANAGED_IDENTITY,
            ConnectorAuthType.BASIC,
        }:
            return self.access_key_authenticator.authenticate(credential)

        if credential.auth_type in {ConnectorAuthType.OAUTH2_CLIENT_CREDENTIALS, ConnectorAuthType.OAUTH2_AUTHORIZATION_CODE}:
            return self.oauth_authenticator.authenticate(credential)

        if credential.auth_type == ConnectorAuthType.CERTIFICATE:
            return self.certificate_authenticator.authenticate(credential)

        return ConnectorAuthContext(auth_type=credential.auth_type, authenticated=False, credential=credential, metadata={"errors": ("Unsupported auth type.",)})

    def _cache_key(self, request: ConnectorCredentialRequest) -> str:
        return f"{request.auth_type.value}:{request.secret_ref or ''}:{request.principal_ref or ''}:{request.token_ref or ''}:{','.join(request.scopes)}"
