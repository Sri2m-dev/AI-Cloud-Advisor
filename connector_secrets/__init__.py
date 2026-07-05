"""Connector secret resolution contracts.

This module intentionally avoids storing secrets. It defines the interface that
future vault, environment, or cloud secret manager integrations should follow.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class SecretProvider(ABC):
    """Abstract secret provider for connector authentication."""

    @abstractmethod
    def resolve(self, secret_ref: str) -> str | None:
        """Resolve a secret reference without exposing it in logs."""


class EnvironmentSecretProvider(SecretProvider):
    """Environment variable based secret provider for local development."""

    def resolve(self, secret_ref: str) -> str | None:
        import os

        return os.getenv(secret_ref)
