"""Quality scoring exceptions."""


class QualityScoringError(Exception):
    """Base exception for data quality and trust scoring."""


class QualityValidationError(QualityScoringError, ValueError):
    """Raised when scoring inputs or weights are invalid."""
