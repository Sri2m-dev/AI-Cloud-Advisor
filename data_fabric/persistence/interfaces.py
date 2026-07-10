"""Repository interface contracts for Data Fabric persistence adapters."""

from __future__ import annotations

from abc import ABC, abstractmethod

from data_fabric.foundation import TenantContext
from data_fabric.orchestration import IdempotencyState
from data_fabric.persistence.models import (
    AppendOnlyRecord,
    ImmutableRecord,
    MutableRecord,
    PageResult,
    PersistenceRecord,
    RepositoryQuery,
)


class Repository(ABC):
    """Base tenant-scoped repository contract."""

    @abstractmethod
    def get(self, tenant_context: TenantContext, record_id: str, *, include_inactive: bool = False) -> PersistenceRecord | None:
        """Return one record in tenant scope."""

    @abstractmethod
    def exists(self, tenant_context: TenantContext, record_id: str) -> bool:
        """Return whether a record exists in tenant scope."""

    @abstractmethod
    def count(self, query: RepositoryQuery) -> int:
        """Count tenant-scoped records."""

    @abstractmethod
    def search(self, query: RepositoryQuery) -> PageResult:
        """Search tenant-scoped records with stable ordering and paging."""


class MutableRepository(Repository):
    """Repository for mutable current-state records."""

    @abstractmethod
    def add(self, record: MutableRecord) -> MutableRecord:
        """Add a mutable record."""

    @abstractmethod
    def update(self, record: MutableRecord, *, expected_revision: int) -> MutableRecord:
        """Update a mutable record with optimistic concurrency."""

    @abstractmethod
    def deactivate(self, tenant_context: TenantContext, record_id: str, *, deactivated_by: str | None = None) -> MutableRecord:
        """Soft deactivate a mutable record."""


class AppendOnlyRepository(Repository):
    """Repository for immutable append-only records."""

    @abstractmethod
    def append(self, record: AppendOnlyRecord) -> AppendOnlyRecord:
        """Append an immutable record."""

    @abstractmethod
    def update(self, record: ImmutableRecord, *, expected_revision: int | None = None) -> ImmutableRecord:
        """Reject update attempts for immutable records."""


class TemporalRepository(AppendOnlyRepository):
    """Repository for effective-time history records."""

    @abstractmethod
    def history_for_subject(self, tenant_context: TenantContext, subject_id: str) -> tuple[AppendOnlyRecord, ...]:
        """Return deterministic history for one subject."""


class EntityRepository(MutableRepository):
    """Current-state canonical entity repository."""


class RelationshipRepository(MutableRepository):
    """Current-state canonical relationship repository."""


class IdentityRepository(MutableRepository):
    """Source identity repository."""


class OntologyRepository(MutableRepository):
    """Semantic concept repository."""


class SemanticMappingRepository(MutableRepository):
    """Semantic source mapping repository."""


class LineageRepository(AppendOnlyRepository):
    """Append-only lineage repository."""


class ProvenanceRepository(AppendOnlyRepository):
    """Append-only provenance repository."""


class VersionRepository(AppendOnlyRepository):
    """Append-only immutable version repository."""


class QualityAssessmentRepository(AppendOnlyRepository):
    """Append-only quality assessment repository."""


class TemporalHistoryRepository(TemporalRepository):
    """Effective-time temporal history repository."""


class IdempotencyRepository(Repository):
    """Repository for durable idempotency state."""

    @abstractmethod
    def reserve_key(self, tenant_context: TenantContext, key: str, payload_hash: str) -> MutableRecord:
        """Reserve or return an idempotency key for tenant scope."""

    @abstractmethod
    def mark_completed(self, tenant_context: TenantContext, key: str, result_ref: str) -> MutableRecord:
        """Mark an idempotency record complete."""

    @abstractmethod
    def mark_failed(self, tenant_context: TenantContext, key: str, reason: str) -> MutableRecord:
        """Mark an idempotency record failed and retryable."""

    @abstractmethod
    def get_status(self, tenant_context: TenantContext, key: str) -> IdempotencyState | None:
        """Return idempotency status."""
