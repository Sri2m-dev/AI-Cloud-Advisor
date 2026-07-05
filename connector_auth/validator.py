"""Connector credential validation."""

from __future__ import annotations

from dataclasses import dataclass, field

from connector_auth.credentials import ConnectorAuthType, ConnectorCredential


@dataclass(frozen=True)
class CredentialValidationResult:
    valid: bool
    errors: tuple[str, ...] = field(default_factory=tuple)
    warnings: tuple[str, ...] = field(default_factory=tuple)


class CredentialValidator:
    """Validates credentials before authentication context acquisition."""

    def validate(self, credential: ConnectorCredential) -> CredentialValidationResult:
        errors: list[str] = []

        if credential.auth_type == ConnectorAuthType.ANONYMOUS:
            return CredentialValidationResult(valid=True)

        if credential.auth_type in {
            ConnectorAuthType.API_KEY,
            ConnectorAuthType.BEARER_TOKEN,
            ConnectorAuthType.AWS_ACCESS_KEY,
            ConnectorAuthType.CERTIFICATE,
        } and not credential.secret:
            errors.append("Secret value is required.")

        if credential.auth_type in {
            ConnectorAuthType.BASIC,
            ConnectorAuthType.OAUTH2_CLIENT_CREDENTIALS,
            ConnectorAuthType.AZURE_SERVICE_PRINCIPAL,
        } and (not credential.principal or not credential.secret):
            errors.append("Principal and secret are required.")

        if credential.auth_type == ConnectorAuthType.AWS_ASSUME_ROLE and not credential.principal:
            errors.append("Role ARN/principal is required for assume-role authentication.")

        if credential.expired:
            errors.append("Credential has expired.")

        return CredentialValidationResult(valid=not errors, errors=tuple(errors))
