"""Canonical persistence publisher bridge."""

from __future__ import annotations

from typing import Sequence

from connector_normalization import CanonicalEnterpriseRecord, CanonicalPublisher, CanonicalPublishResult
from connector_persistence.batch import BatchManager
from connector_persistence.metadata import PersistenceMetadata
from connector_persistence.repository import CanonicalRepository


class PersistenceCanonicalPublisher(CanonicalPublisher):
    """Canonical publisher backed by a persistence repository."""

    def __init__(self, repository: CanonicalRepository, batch_manager: BatchManager | None = None, target: str = "data_fabric") -> None:
        self.repository = repository
        self.batch_manager = batch_manager or BatchManager()
        self.target = target

    def publish(self, records: Sequence[CanonicalEnterpriseRecord]) -> CanonicalPublishResult:
        metadata = PersistenceMetadata(source_system="canonical_publisher")
        result = self.batch_manager.save_batch(self.repository, records, metadata=metadata)
        return CanonicalPublishResult(
            published_count=result.succeeded,
            target=self.target,
            warnings=result.warnings + result.errors,
        )
