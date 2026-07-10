"""Persistence unit-of-work interfaces and in-memory compliance implementation."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable

from data_fabric.foundation import TenantContext
from data_fabric.persistence.exceptions import PersistenceTransactionError
from data_fabric.persistence.models import AppendOnlyRecord, MutableRecord
from data_fabric.persistence.repositories import (
    InMemoryEntityRepository,
    InMemoryIdempotencyRepository,
    InMemoryLineageRepository,
    InMemoryOntologyRepository,
    InMemoryProvenanceRepository,
    InMemoryQualityAssessmentRepository,
    InMemoryRelationshipRepository,
    InMemorySemanticMappingRepository,
    InMemoryTemporalHistoryRepository,
    InMemoryVersionRepository,
)


class PersistenceTransactionState(str, Enum):
    NOT_STARTED = "not_started"
    ACTIVE = "active"
    COMMITTED = "committed"
    ROLLED_BACK = "rolled_back"
    FAILED = "failed"


@dataclass(slots=True)
class RepositoryProvider:
    """Container for persistence repositories participating in a unit of work."""

    entities: InMemoryEntityRepository = field(default_factory=InMemoryEntityRepository)
    relationships: InMemoryRelationshipRepository = field(default_factory=InMemoryRelationshipRepository)
    versions: InMemoryVersionRepository = field(default_factory=InMemoryVersionRepository)
    lineage: InMemoryLineageRepository = field(default_factory=InMemoryLineageRepository)
    provenance: InMemoryProvenanceRepository = field(default_factory=InMemoryProvenanceRepository)
    quality: InMemoryQualityAssessmentRepository = field(default_factory=InMemoryQualityAssessmentRepository)
    ontology: InMemoryOntologyRepository = field(default_factory=InMemoryOntologyRepository)
    semantic_mappings: InMemorySemanticMappingRepository = field(default_factory=InMemorySemanticMappingRepository)
    idempotency: InMemoryIdempotencyRepository = field(default_factory=InMemoryIdempotencyRepository)
    temporal_history: InMemoryTemporalHistoryRepository = field(default_factory=InMemoryTemporalHistoryRepository)

    def all_repositories(self) -> tuple[Any, ...]:
        return (
            self.entities,
            self.relationships,
            self.versions,
            self.lineage,
            self.provenance,
            self.quality,
            self.ontology,
            self.semantic_mappings,
            self.idempotency,
            self.temporal_history,
        )


class PersistenceTransaction:
    """Base transaction contract for persistence unit-of-work implementations."""

    def begin(self, tenant_context: TenantContext) -> None: ...
    def commit(self) -> None: ...
    def rollback(self, reason: str) -> None: ...


class PersistenceUnitOfWork(PersistenceTransaction):
    """Persistence unit-of-work contract."""

    @property
    def repositories(self) -> RepositoryProvider: ...
    @property
    def tenant_context(self) -> TenantContext | None: ...
    @property
    def state(self) -> PersistenceTransactionState: ...
    @property
    def staged_operation_count(self) -> int: ...
    @property
    def failure_reason(self) -> str | None: ...


class InMemoryPersistenceUnitOfWork(PersistenceUnitOfWork):
    """In-memory compliance unit of work with atomic snapshot rollback."""

    def __init__(self, repositories: RepositoryProvider | None = None) -> None:
        self._repositories = repositories or RepositoryProvider()
        self._tenant_context: TenantContext | None = None
        self._state = PersistenceTransactionState.NOT_STARTED
        self._failure_reason: str | None = None
        self._staged: list[Callable[[], Any]] = []
        self._snapshots: dict[int, Any] = {}

    @property
    def repositories(self) -> RepositoryProvider:
        return self._repositories

    @property
    def tenant_context(self) -> TenantContext | None:
        return self._tenant_context

    @property
    def state(self) -> PersistenceTransactionState:
        return self._state

    @property
    def staged_operation_count(self) -> int:
        return len(self._staged)

    @property
    def failure_reason(self) -> str | None:
        return self._failure_reason

    def begin(self, tenant_context: TenantContext) -> None:
        if self._state is PersistenceTransactionState.ACTIVE:
            if tenant_context != self._tenant_context:
                raise PersistenceTransactionError("tenant cannot change inside an open transaction")
            raise PersistenceTransactionError("transaction already active")
        self._tenant_context = tenant_context
        self._state = PersistenceTransactionState.ACTIVE
        self._failure_reason = None
        self._staged = []
        self._snapshots = {id(repo): repo._snapshot() for repo in self._repositories.all_repositories()}

    def stage_add(self, repository: Any, record: MutableRecord) -> None:
        self._require_active(record.tenant_context)
        self._staged.append(lambda: repository.add(record))

    def stage_update(self, repository: Any, record: MutableRecord, *, expected_revision: int) -> None:
        self._require_active(record.tenant_context)
        self._staged.append(lambda: repository.update(record, expected_revision=expected_revision))

    def stage_append(self, repository: Any, record: AppendOnlyRecord) -> None:
        self._require_active(record.tenant_context)
        self._staged.append(lambda: repository.append(record))

    def commit(self) -> None:
        self._require_active(self._tenant_context)
        try:
            for operation in self._staged:
                operation()
        except Exception as exc:
            self._restore_snapshots()
            self._state = PersistenceTransactionState.FAILED
            self._failure_reason = str(exc)
            self._staged = []
            raise
        self._state = PersistenceTransactionState.COMMITTED
        self._staged = []
        self._snapshots = {}

    def rollback(self, reason: str) -> None:
        self._require_active(self._tenant_context)
        self._restore_snapshots()
        self._state = PersistenceTransactionState.ROLLED_BACK
        self._failure_reason = reason
        self._staged = []

    def _restore_snapshots(self) -> None:
        for repo in self._repositories.all_repositories():
            snapshot = self._snapshots.get(id(repo))
            if snapshot is not None:
                repo._restore(snapshot)

    def _require_active(self, tenant_context: TenantContext | None) -> None:
        if self._state is not PersistenceTransactionState.ACTIVE or self._tenant_context is None:
            raise PersistenceTransactionError("transaction is not active")
        if tenant_context != self._tenant_context:
            raise PersistenceTransactionError("tenant cannot change inside an open transaction")
