"""Abstract interfaces for versioning and temporal history."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime

from data_fabric.contracts import EnterpriseEntity, EnterpriseRelationship
from data_fabric.versioning.models import (
    EntitySnapshot,
    HistoryQuery,
    HistoryResult,
    RelationshipSnapshot,
    TemporalRecord,
    VersionComparison,
    VersionRecord,
)


class VersionStore(ABC):
    """Interface for immutable canonical snapshot storage."""

    @abstractmethod
    def create_entity_snapshot(
        self,
        entity: EnterpriseEntity,
        *,
        effective_from: datetime | None = None,
        effective_to: datetime | None = None,
        allow_unchanged: bool = False,
        lineage_ref: str | None = None,
        provenance_ref: str | None = None,
    ) -> EntitySnapshot:
        """Create an immutable entity snapshot."""

    @abstractmethod
    def create_relationship_snapshot(
        self,
        relationship: EnterpriseRelationship,
        *,
        effective_from: datetime | None = None,
        effective_to: datetime | None = None,
        allow_unchanged: bool = False,
        lineage_ref: str | None = None,
        provenance_ref: str | None = None,
    ) -> RelationshipSnapshot:
        """Create an immutable relationship snapshot."""

    @abstractmethod
    def get_snapshot(
        self,
        snapshot_id: str,
        *,
        organization_id: str,
        tenant_id: str | None,
    ) -> VersionRecord:
        """Return one snapshot by id inside an organization and tenant partition."""

    @abstractmethod
    def get_latest_entity_snapshot(
        self,
        entity_id: str,
        *,
        organization_id: str,
        tenant_id: str | None,
    ) -> EntitySnapshot | None:
        """Return the latest entity snapshot in a tenant partition."""

    @abstractmethod
    def get_latest_relationship_snapshot(
        self,
        relationship_id: str,
        *,
        organization_id: str,
        tenant_id: str | None,
    ) -> RelationshipSnapshot | None:
        """Return the latest relationship snapshot in a tenant partition."""

    @abstractmethod
    def list_entity_versions(
        self,
        entity_id: str,
        *,
        organization_id: str,
        tenant_id: str | None,
    ) -> list[EntitySnapshot]:
        """List entity versions in stable ascending version order."""

    @abstractmethod
    def list_relationship_versions(
        self,
        relationship_id: str,
        *,
        organization_id: str,
        tenant_id: str | None,
    ) -> list[RelationshipSnapshot]:
        """List relationship versions in stable ascending version order."""

    @abstractmethod
    def compare_entity_versions(
        self,
        first: EntitySnapshot,
        second: EntitySnapshot,
    ) -> VersionComparison:
        """Compare two entity snapshots."""

    @abstractmethod
    def compare_relationship_versions(
        self,
        first: RelationshipSnapshot,
        second: RelationshipSnapshot,
    ) -> VersionComparison:
        """Compare two relationship snapshots."""


class TemporalHistoryStore(ABC):
    """Interface for effective-time temporal history records."""

    @abstractmethod
    def append_record(self, record: TemporalRecord, *, allow_overlap: bool = False) -> TemporalRecord:
        """Append an immutable temporal record."""

    @abstractmethod
    def close_current_record(
        self,
        subject_id: str,
        *,
        organization_id: str,
        tenant_id: str | None,
        effective_to: datetime,
    ) -> TemporalRecord:
        """Close the current open record without mutating its payload."""

    @abstractmethod
    def get_current_record(
        self,
        subject_id: str,
        *,
        organization_id: str,
        tenant_id: str | None,
    ) -> TemporalRecord | None:
        """Return the current open record for a subject partition."""

    @abstractmethod
    def get_record_at_time(
        self,
        subject_id: str,
        *,
        organization_id: str,
        tenant_id: str | None,
        query_time: datetime,
    ) -> TemporalRecord | None:
        """Return the record effective at a point in time."""

    @abstractmethod
    def query_history(self, query: HistoryQuery) -> HistoryResult:
        """Query temporal history for one subject partition."""

    @abstractmethod
    def list_history(
        self,
        subject_id: str,
        *,
        organization_id: str,
        tenant_id: str | None,
    ) -> list[TemporalRecord]:
        """List history records in stable effective-time order."""

    @abstractmethod
    def detect_overlapping_effective_periods(
        self,
        subject_id: str,
        *,
        organization_id: str,
        tenant_id: str | None,
    ) -> list[tuple[TemporalRecord, TemporalRecord]]:
        """Report overlapping effective-time records."""


class VersionComparator(ABC):
    """Interface for deterministic payload comparisons."""

    @abstractmethod
    def compare(self, first: VersionRecord, second: VersionRecord) -> VersionComparison:
        """Compare two version records and return stable differences."""
