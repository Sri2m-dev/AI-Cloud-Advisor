"""Connector secret resolution contracts.

This module intentionally avoids logging secrets. It defines provider interfaces
that future vault, environment, cloud secret manager, or local development
integrations should follow.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping


@dataclass(frozen=True)
class ConnectorSecretReference:
    """Reference to a secret without exposing the secret value."""

    secret_ref: str
    provider: str = "environment"
    description: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)


class SecretProvider(ABC):
    """Abstract secret provider for connector authentication."""

    @abstractmethod
    def resolve(self, secret_ref: str | ConnectorSecretReference) -> str | None:
        """Resolve a secret reference without exposing it in logs."""


class EnvironmentSecretProvider(SecretProvider):
    """Environment variable based secret provider for local development."""

    def resolve(self, secret_ref: str | ConnectorSecretReference) -> str | None:
        import os

        ref = secret_ref.secret_ref if isinstance(secret_ref, ConnectorSecretReference) else secret_ref
        return os.getenv(ref)


class InMemorySecretProvider(SecretProvider):
    """In-memory secret provider for tests and non-production smoke checks."""

    def __init__(self, secrets: Mapping[str, str] | None = None) -> None:
        self._secrets = dict(secrets or {})

    def set(self, secret_ref: str, value: str) -> None:
        self._secrets[secret_ref] = value

    def resolve(self, secret_ref: str | ConnectorSecretReference) -> str | None:
        ref = secret_ref.secret_ref if isinstance(secret_ref, ConnectorSecretReference) else secret_ref
        return self._secrets.get(ref)


class LocalConfigurationSecretProvider(SecretProvider):
    """Simple key=value local configuration provider.

    This is intended for development only. Production environments should use a
    managed secret store such as AWS Secrets Manager, Azure Key Vault,
    HashiCorp Vault, Google Secret Manager, or Kubernetes Secrets.
    """

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self._secrets = self._load()

    def resolve(self, secret_ref: str | ConnectorSecretReference) -> str | None:
        ref = secret_ref.secret_ref if isinstance(secret_ref, ConnectorSecretReference) else secret_ref
        return self._secrets.get(ref)

    def _load(self) -> dict[str, str]:
        if not self.path.exists():
            return {}
        values: dict[str, str] = {}
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if not line or line.strip().startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip()
        return values
