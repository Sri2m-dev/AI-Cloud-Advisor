"""Reusable persistence adapter compliance suites."""

from __future__ import annotations

from dataclasses import replace

from data_fabric.foundation import TenantContext
from data_fabric.persistence.exceptions import PersistenceConflictError, PersistenceImmutableStateError, PersistenceTenantBoundaryError
from data_fabric.persistence.models import AppendOnlyRecord, MutableRecord, RepositoryQuery
from data_fabric.persistence.unit_of_work import InMemoryPersistenceUnitOfWork, PersistenceTransactionState


class RepositoryComplianceSuite:
    """Base compliance checks shared by persistence repositories."""

    def run(self, repository, tenant_context: TenantContext) -> None:
        record = MutableRecord("record-1", tenant_context.organization_id, tenant_context.tenant_id)
        repository.add(record)
        assert repository.exists(tenant_context, "record-1")
        assert repository.get(tenant_context, "record-1") is not None
        assert repository.count(RepositoryQuery(tenant_context)) == 1


class MutableRepositoryComplianceSuite:
    """Compliance checks for mutable current-state repositories."""

    def run(self, repository, tenant_context: TenantContext) -> None:
        record = MutableRecord("mutable-1", tenant_context.organization_id, tenant_context.tenant_id)
        repository.add(record)
        updated = repository.update(replace(record, metadata={"updated": True}), expected_revision=1)
        assert updated.revision == 2
        try:
            repository.update(record, expected_revision=1)
        except PersistenceConflictError:
            pass
        else:
            raise AssertionError("stale update should raise conflict")
        deactivated = repository.deactivate(tenant_context, "mutable-1")
        assert deactivated.active is False
        assert repository.get(tenant_context, "mutable-1") is None
        assert repository.get(tenant_context, "mutable-1", include_inactive=True) is not None


class AppendOnlyRepositoryComplianceSuite:
    """Compliance checks for append-only repositories."""

    def run(self, repository, tenant_context: TenantContext) -> None:
        record = AppendOnlyRecord("append-1", tenant_context.organization_id, tenant_context.tenant_id, payload={"a": 1})
        repository.append(record)
        assert repository.get(tenant_context, "append-1") is not None
        try:
            repository.update(record)
        except PersistenceImmutableStateError:
            pass
        else:
            raise AssertionError("append-only update should be rejected")


class TemporalRepositoryComplianceSuite(AppendOnlyRepositoryComplianceSuite):
    """Compliance checks for temporal repositories."""

    def run(self, repository, tenant_context: TenantContext) -> None:
        record = AppendOnlyRecord("temporal-1", tenant_context.organization_id, tenant_context.tenant_id, payload={"subject_id": "entity-1"})
        repository.append(record)
        assert repository.history_for_subject(tenant_context, "entity-1")


class TenantIsolationComplianceSuite:
    """Compliance checks for tenant isolation."""

    def run(self, repository, tenant_context: TenantContext, other_context: TenantContext) -> None:
        record = MutableRecord("tenant-1", tenant_context.organization_id, tenant_context.tenant_id)
        repository.add(record)
        assert repository.get(other_context, "tenant-1") is None
        try:
            repository.update(replace(record, organization_id=other_context.organization_id, tenant_id=other_context.tenant_id), expected_revision=1)
        except PersistenceTenantBoundaryError:
            pass
        else:
            raise AssertionError("cross-tenant update should be rejected")


class TransactionComplianceSuite:
    """Compliance checks for persistence unit-of-work behavior."""

    def run(self, unit_of_work: InMemoryPersistenceUnitOfWork, tenant_context: TenantContext) -> None:
        record = MutableRecord("tx-1", tenant_context.organization_id, tenant_context.tenant_id)
        unit_of_work.begin(tenant_context)
        unit_of_work.stage_add(unit_of_work.repositories.entities, record)
        assert unit_of_work.staged_operation_count == 1
        unit_of_work.commit()
        assert unit_of_work.state is PersistenceTransactionState.COMMITTED
        assert unit_of_work.repositories.entities.exists(tenant_context, "tx-1")
