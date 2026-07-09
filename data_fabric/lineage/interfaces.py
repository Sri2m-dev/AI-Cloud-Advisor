"""Abstract lineage and provenance tracker interfaces."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from data_fabric.lineage.provenance import ProvenanceRecord
    from data_fabric.lineage.tracker import LineageEvent, LineagePath


class LineageTracker(ABC):
    """Interface for recording and explaining canonical lineage events."""

    @abstractmethod
    def record_source_event(self, event: LineageEvent) -> LineageEvent:
        """Record raw source collection or connector ingestion lineage."""

    @abstractmethod
    def record_normalization_event(self, event: LineageEvent) -> LineageEvent:
        """Record source-to-normalized transformation lineage."""

    @abstractmethod
    def record_canonicalization_event(self, event: LineageEvent) -> LineageEvent:
        """Record normalized-to-canonical entity lineage."""

    @abstractmethod
    def record_relationship_event(self, event: LineageEvent) -> LineageEvent:
        """Record canonical relationship derivation lineage."""

    @abstractmethod
    def trace_lineage_by_entity_id(self, entity_id: str) -> LineagePath:
        """Trace lineage events associated with a canonical entity."""

    @abstractmethod
    def explain_entity_origin(self, entity_id: str) -> str:
        """Return a compact human-readable explanation for entity origin."""

    @abstractmethod
    def explain_relationship_origin(self, relationship_id: str) -> str:
        """Return a compact explanation for relationship origin."""


class ProvenanceTracker(ABC):
    """Interface for recording source authority and derivation context."""

    @abstractmethod
    def record_provenance(self, record: ProvenanceRecord) -> ProvenanceRecord:
        """Record provenance for a canonical entity or relationship."""

    @abstractmethod
    def trace_provenance_by_source(
        self,
        source_system: str,
        source_identifier: str,
    ) -> list[ProvenanceRecord]:
        """Trace provenance by source identity."""

    @abstractmethod
    def explain_entity_origin(self, entity_id: str) -> str:
        """Return a compact provenance explanation for an entity."""

    @abstractmethod
    def explain_relationship_origin(self, relationship_id: str) -> str:
        """Return a compact provenance explanation for a relationship."""
