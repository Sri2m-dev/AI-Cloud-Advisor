"""Abstract identity resolver interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterable

from data_fabric.contracts import EnterpriseEntity
from data_fabric.identity.matching import MatchCandidate, MatchResult


class IdentityResolver(ABC):
    """Interface for resolving source identities to canonical entities."""

    @abstractmethod
    def register_entity(self, entity: EnterpriseEntity) -> EnterpriseEntity:
        """Add a canonical entity to the resolver's in-memory match set."""

    @abstractmethod
    def register_entities(
        self,
        entities: Iterable[EnterpriseEntity],
    ) -> list[EnterpriseEntity]:
        """Add multiple canonical entities to the resolver's match set."""

    @abstractmethod
    def resolve(self, candidate: MatchCandidate) -> MatchResult:
        """Resolve a source identity candidate to a canonical entity or no-match."""

    @abstractmethod
    def detect_duplicates(self, candidate: MatchCandidate) -> MatchResult:
        """Return duplicate candidates when multiple entities match explicitly."""
