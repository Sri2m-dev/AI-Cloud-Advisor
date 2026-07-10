"""Abstract orchestration interfaces for P3 Data Fabric."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from data_fabric.foundation import TenantContext
from data_fabric.quality import QualityAssessment
from data_fabric.orchestration.models import (
    BatchIngestionRequest,
    BatchIngestionResult,
    CanonicalizationResult,
    EntityWritePlan,
    IdempotencyKey,
    IdempotencyRecord,
    IngestionRequest,
    LineageEmissionPlan,
    QualityGateDecision,
    RelationshipWritePlan,
    SourceRecord,
    TransactionResult,
    TransactionStatus,
    VersionDecision,
)


class IngestionCoordinator(ABC):
    """Coordinates source-record ingestion across P3 services."""

    @abstractmethod
    def ingest(self, request: IngestionRequest) -> CanonicalizationResult:
        """Ingest one source record and return an explainable result."""

    @abstractmethod
    def ingest_batch(self, request: BatchIngestionRequest) -> BatchIngestionResult:
        """Ingest a tenant-isolated batch with deterministic result ordering."""


class CanonicalizationPipeline(ABC):
    """Creates plans and decisions before any write boundary is committed."""

    @abstractmethod
    def process(self, request: IngestionRequest) -> CanonicalizationResult:
        """Process one request into plans, decisions, and transaction output."""


class UnitOfWork(ABC):
    """Atomic staging boundary for planned Data Fabric writes."""

    @abstractmethod
    def begin(self, tenant_context: TenantContext) -> None:
        """Begin a tenant-scoped unit of work."""

    @abstractmethod
    def stage_entity_write(self, plan: EntityWritePlan) -> None:
        """Stage an entity write plan."""

    @abstractmethod
    def stage_relationship_write(self, plan: RelationshipWritePlan) -> None:
        """Stage a relationship write plan."""

    @abstractmethod
    def stage_lineage_event(self, event: Any) -> None:
        """Stage a lineage event."""

    @abstractmethod
    def stage_provenance_record(self, record: Any) -> None:
        """Stage a provenance record."""

    @abstractmethod
    def stage_version_record(self, record: Any) -> None:
        """Stage a version record."""

    @abstractmethod
    def commit(self) -> TransactionResult:
        """Atomically commit all staged operations."""

    @abstractmethod
    def rollback(self, reason: str) -> TransactionResult:
        """Rollback staged operations while preserving failure explanation."""

    @property
    @abstractmethod
    def status(self) -> TransactionStatus:
        """Return unit-of-work status."""


class IdempotencyStore(ABC):
    """Tenant-isolated idempotency state boundary."""

    @abstractmethod
    def begin(self, key: IdempotencyKey, payload_hash: str) -> IdempotencyRecord:
        """Begin or return an idempotent record for a request."""

    @abstractmethod
    def complete(self, key: IdempotencyKey, result: CanonicalizationResult) -> IdempotencyRecord:
        """Mark a request completed after successful commit."""

    @abstractmethod
    def fail(self, key: IdempotencyKey, reason: str) -> IdempotencyRecord:
        """Mark a request failed and retryable according to policy."""

    @abstractmethod
    def get(self, key: IdempotencyKey) -> IdempotencyRecord | None:
        """Return idempotency state for a tenant-scoped key."""


class QualityGatePolicy(ABC):
    """Decides whether quality assessment permits planned writes."""

    @abstractmethod
    def decide(self, assessment: QualityAssessment) -> QualityGateDecision:
        """Return a deterministic and explainable quality gate decision."""


class LineageEmissionPolicy(ABC):
    """Plans lineage/provenance emission for an orchestration result."""

    @abstractmethod
    def plan(self, request: IngestionRequest, result: CanonicalizationResult | None) -> LineageEmissionPlan:
        """Return event/provenance emission decisions."""


class VersionCreationPolicy(ABC):
    """Determines version creation behavior for planned canonical writes."""

    @abstractmethod
    def decide(self, plan: EntityWritePlan, previous_hash: str | None = None, force: bool = False) -> VersionDecision:
        """Return a deterministic version decision for a write plan."""


class TransactionBoundary(ABC):
    """Executes prepared write plans inside a unit-of-work boundary."""

    @abstractmethod
    def execute(
        self,
        *,
        tenant_context: TenantContext,
        entity_plan: EntityWritePlan,
        relationship_plans: tuple[RelationshipWritePlan, ...],
        lineage_plan: LineageEmissionPlan,
    ) -> TransactionResult:
        """Execute prepared plans atomically."""


class SemanticMappingPort(ABC):
    """Small orchestration-facing semantic mapping port."""

    @abstractmethod
    def map_source_record(self, record: SourceRecord, tenant_context: TenantContext) -> Any:
        """Map source record context into semantic concepts."""
