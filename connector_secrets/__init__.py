"""Connector secret resolution contracts.

This module intentionally avoids storing secrets. It defines the interface that
future vault, environment, or cloud secret manager integrations should follow.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
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
