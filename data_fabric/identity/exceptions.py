"""Identity resolution exceptions."""


class IdentityResolutionError(Exception):
    """Base exception for identity resolution operations."""


class IdentityValidationError(IdentityResolutionError, ValueError):
    """Raised when an identity candidate cannot be evaluated."""
