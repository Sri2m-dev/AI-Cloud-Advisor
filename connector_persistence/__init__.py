"""Connector persistence framework exports."""

from connector_persistence.batch import BatchConfig, BatchManager
from connector_persistence.deduplication import DeduplicationEngine, DeduplicationKey, DeduplicationStrategy
from connector_persistence.metadata import PersistenceMetadata, PersistenceResult
from connector_persistence.publisher import PersistenceCanonicalPublisher
from connector_persistence.repository import CanonicalRepository
from connector_persistence.transaction import TransactionManager

__all__ = [
    "BatchConfig",
    "BatchManager",
    "CanonicalRepository",
    "DeduplicationEngine",
    "DeduplicationKey",
    "DeduplicationStrategy",
    "PersistenceCanonicalPublisher",
    "PersistenceMetadata",
    "PersistenceResult",
    "TransactionManager",
]
