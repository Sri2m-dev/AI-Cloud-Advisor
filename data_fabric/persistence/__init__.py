"""Persistence foundation contracts for the P3 Data Fabric."""

from data_fabric.persistence.compliance import (
    AppendOnlyRepositoryComplianceSuite,
    MutableRepositoryComplianceSuite,
    RepositoryComplianceSuite,
    TenantIsolationComplianceSuite,
    TemporalRepositoryComplianceSuite,
    TransactionComplianceSuite,
)
from data_fabric.persistence.exceptions import (
    PersistenceConflictError,
    PersistenceDuplicateError,
    PersistenceImmutableStateError,
    PersistenceNotFoundError,
    PersistenceTenantBoundaryError,
    PersistenceTransactionError,
    PersistenceValidationError,
)
from data_fabric.persistence.interfaces import (
    EntityRepository,
    IdempotencyRepository,
    IdentityRepository,
    LineageRepository,
    OntologyRepository,
    ProvenanceRepository,
    QualityAssessmentRepository,
    RelationshipRepository,
    SemanticMappingRepository,
    TemporalHistoryRepository,
    VersionRepository,
)
from data_fabric.persistence.mappers import (
    EntityPersistenceMapper,
    IdentityPersistenceMapper,
    LineagePersistenceMapper,
    OntologyPersistenceMapper,
    ProvenancePersistenceMapper,
    QualityPersistenceMapper,
    RelationshipPersistenceMapper,
    SemanticMappingPersistenceMapper,
    VersionPersistenceMapper,
)
from data_fabric.persistence.models import (
    AppendOnlyRecord,
    ConcurrencyToken,
    ImmutableRecord,
    MutableRecord,
    PageRequest,
    PageResult,
    PersistenceOperationResult,
    PersistenceRecord,
    RepositoryQuery,
    SoftDeleteState,
    SortSpecification,
)
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
from data_fabric.persistence.unit_of_work import (
    InMemoryPersistenceUnitOfWork,
    PersistenceTransaction,
    PersistenceTransactionState,
    PersistenceUnitOfWork,
    RepositoryProvider,
)

__all__ = [name for name in globals() if not name.startswith("_")]
