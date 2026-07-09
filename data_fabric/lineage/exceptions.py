"""Lineage and provenance exceptions."""


class LineageError(Exception):
    """Base exception for lineage and provenance operations."""


class LineageValidationError(LineageError, ValueError):
    """Raised when a lineage or provenance record is incomplete."""
