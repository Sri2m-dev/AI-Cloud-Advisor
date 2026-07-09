"""Identity resolution interfaces and in-memory resolver for P3 Data Fabric."""

from data_fabric.identity.exceptions import IdentityResolutionError, IdentityValidationError
from data_fabric.identity.interfaces import IdentityResolver
from data_fabric.identity.matching import MatchCandidate, MatchDecision, MatchResult
from data_fabric.identity.resolver import InMemoryIdentityResolver

__all__ = [
    "IdentityResolutionError",
    "IdentityResolver",
    "IdentityValidationError",
    "InMemoryIdentityResolver",
    "MatchCandidate",
    "MatchDecision",
    "MatchResult",
]
