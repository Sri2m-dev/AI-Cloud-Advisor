"""WP-005 stewardship domain and repository errors."""

from data_fabric.foundation import DataFabricError, DataFabricValidationError


class StewardshipPolicyScopeError(DataFabricValidationError):
    """Raised when a policy is evaluated outside its canonical scope."""


class StewardshipRepositoryInvariantError(DataFabricError):
    """Raised when an RPC result cannot be verified through scoped persistence."""
