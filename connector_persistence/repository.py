"""Canonical persistence repository contracts."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Sequence

from connector_normalization import CanonicalEnterpriseRecord
from connector_persistence.metadata import PersistenceMetadata, PersistenceResult


class CanonicalRepository(ABC):
    """Storage-agnostic repository for canonical enterprise records."""

    @abstractmethod
    def save(self, record: CanonicalEnterpriseRecord, metadata: PersistenceMetadata | None = None) -> PersistenceResult:
        """Save a canonical record."""

    @abstractmethod
    def save_batch(self, records: Sequence[CanonicalEnterpriseRecord], metadata: PersistenceMetadata | None = None) -> PersistenceResult:
        """Save a batch of canonical records."""

    @abstractmethod
    def upsert(self, record: CanonicalEnterpriseRecord, metadata: PersistenceMetadata | None = None) -> PersistenceResult:
        """Insert or update a canonical record."""

    @abstractmethod
    def exists(self, record_id: str) -> bool:
        """Return whether a canonical record exists."""

    @abstractmethod
    def delete(self, record_id: str) -> PersistenceResult:
        """Delete a canonical record."""

    @abstractmethod
    def find(self, record_id: str) -> CanonicalEnterpriseRecord | None:
        """Find a canonical record by ID."""

    @abstractmethod
    def list_records(self) -> list[CanonicalEnterpriseRecord]:
        """List all canonical records known to the repository."""
