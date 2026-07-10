"""Versioning-specific exceptions."""


class VersioningError(Exception):
    """Base exception for versioning and temporal history operations."""


class VersioningValidationError(VersioningError, ValueError):
    """Raised when a versioning or temporal-history invariant is violated."""
