"""In-memory unit-of-work boundary for orchestration contracts."""

from __future__ import annotations

from data_fabric.foundation import TenantContext
from data_fabric.orchestration.exceptions import OrchestrationTransactionError
from data_fabric.orchestration.interfaces import TransactionBoundary, UnitOfWork
from data_fabric.orchestration.models import (
    EntityWritePlan,
    LineageEmissionPlan,
    ProcessingIssue,
    RelationshipWritePlan,
    TransactionResult,
    TransactionStatus,
)


class InMemoryUnitOfWork(UnitOfWork):
    """Reference unit-of-work with atomic staged commit and rollback semantics."""

    def __init__(self, fail_commit: bool = False) -> None:
        self._status = TransactionStatus.NOT_STARTED
        self._tenant_context: TenantContext | None = None
        self._fail_commit = fail_commit
        self.committed_entities: list[EntityWritePlan] = []
        self.committed_relationships: list[RelationshipWritePlan] = []
        self.committed_lineage_events: list[object] = []
        self.committed_provenance_records: list[object] = []
        self.committed_version_records: list[object] = []
        self._clear_staged()

    @property
    def status(self) -> TransactionStatus:
        return self._status

    def begin(self, tenant_context: TenantContext) -> None:
        if self._status is TransactionStatus.ACTIVE:
            raise OrchestrationTransactionError("unit of work is already active")
        self._tenant_context = tenant_context
        self._status = TransactionStatus.ACTIVE
        self._clear_staged()

    def stage_entity_write(self, plan: EntityWritePlan) -> None:
        self._require_active()
        if plan.entity is not None:
            self._tenant_context.assert_record_matches(plan.entity, "entity plan")
        self._entity_writes.append(plan)

    def stage_relationship_write(self, plan: RelationshipWritePlan) -> None:
        self._require_active()
        if plan.relationship is not None:
            self._tenant_context.assert_record_matches(plan.relationship, "relationship plan")
        self._relationship_writes.append(plan)

    def stage_lineage_event(self, event: object) -> None:
        self._require_active()
        self._tenant_context.assert_record_matches(event, "lineage event")
        self._lineage_events.append(event)

    def stage_provenance_record(self, record: object) -> None:
        self._require_active()
        self._tenant_context.assert_record_matches(record, "provenance record")
        self._provenance_records.append(record)

    def stage_version_record(self, record: object) -> None:
        self._require_active()
        self._tenant_context.assert_record_matches(record, "version record")
        self._version_records.append(record)

    def commit(self) -> TransactionResult:
        self._require_active()
        if self._fail_commit:
            return self.rollback("simulated commit failure")
        entity_writes = tuple(self._entity_writes)
        relationship_writes = tuple(self._relationship_writes)
        lineage_events = tuple(self._lineage_events)
        provenance_records = tuple(self._provenance_records)
        version_records = tuple(self._version_records)
        self.committed_entities.extend(entity_writes)
        self.committed_relationships.extend(relationship_writes)
        self.committed_lineage_events.extend(lineage_events)
        self.committed_provenance_records.extend(provenance_records)
        self.committed_version_records.extend(version_records)
        self._status = TransactionStatus.COMMITTED
        self._clear_staged()
        return TransactionResult(
            TransactionStatus.COMMITTED,
            entity_writes,
            relationship_writes,
            lineage_events,
            provenance_records,
            version_records,
        )

    def rollback(self, reason: str) -> TransactionResult:
        self._require_active()
        self._status = TransactionStatus.ROLLED_BACK
        self._clear_staged()
        return TransactionResult(
            TransactionStatus.ROLLED_BACK,
            issues=(ProcessingIssue("transaction_rolled_back", reason),),
        )

    def _clear_staged(self) -> None:
        self._entity_writes: list[EntityWritePlan] = []
        self._relationship_writes: list[RelationshipWritePlan] = []
        self._lineage_events: list[object] = []
        self._provenance_records: list[object] = []
        self._version_records: list[object] = []

    def _require_active(self) -> None:
        if self._status is not TransactionStatus.ACTIVE or self._tenant_context is None:
            raise OrchestrationTransactionError("unit of work is not active")


class InMemoryTransactionBoundary(TransactionBoundary):
    """Executes prepared plans through an in-memory unit-of-work."""

    def __init__(self, unit_of_work: InMemoryUnitOfWork | None = None) -> None:
        self.unit_of_work = unit_of_work or InMemoryUnitOfWork()

    def execute(
        self,
        *,
        tenant_context: TenantContext,
        entity_plan: EntityWritePlan,
        relationship_plans: tuple[RelationshipWritePlan, ...],
        lineage_plan: LineageEmissionPlan,
    ) -> TransactionResult:
        self.unit_of_work.begin(tenant_context)
        try:
            self.unit_of_work.stage_entity_write(entity_plan)
            for plan in relationship_plans:
                self.unit_of_work.stage_relationship_write(plan)
            for event in lineage_plan.events:
                self.unit_of_work.stage_lineage_event(event)
            for record in lineage_plan.provenance_records:
                self.unit_of_work.stage_provenance_record(record)
            return self.unit_of_work.commit()
        except Exception as exc:
            if self.unit_of_work.status is TransactionStatus.ACTIVE:
                self.unit_of_work.rollback(str(exc))
            raise
