"""Connector execution exception hierarchy."""

from __future__ import annotations


class ConnectorError(Exception):
    """Base exception for connector runtime failures."""


class ConnectorAuthenticationError(ConnectorError):
    """Raised when connector authentication fails."""


class ConnectorDiscoveryError(ConnectorError):
    """Raised when connector discovery fails."""


class ConnectorExtractionError(ConnectorError):
    """Raised when connector extraction fails."""


class ConnectorValidationError(ConnectorError):
    """Raised when connector validation fails."""


class ConnectorPublishError(ConnectorError):
    """Raised when connector publish fails."""


class ConnectorRuntimeError(ConnectorError):
    """Raised when the connector runtime cannot execute a connector."""
