"""Semantic ontology exceptions."""


class SemanticError(Exception):
    """Base exception for semantic ontology operations."""


class SemanticValidationError(SemanticError, ValueError):
    """Raised when semantic model validation fails."""
