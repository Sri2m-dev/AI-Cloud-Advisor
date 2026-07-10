from __future__ import annotations

from data_fabric.foundation import TenantContext
from data_fabric.persistence import (
    AppendOnlyRepositoryComplianceSuite,
    InMemoryEntityRepository,
    InMemoryLineageRepository,
    InMemoryPersistenceUnitOfWork,
    InMemoryTemporalHistoryRepository,
    MutableRepositoryComplianceSuite,
    RepositoryComplianceSuite,
    TenantIsolationComplianceSuite,
    TemporalRepositoryComplianceSuite,
    TransactionComplianceSuite,
)


def tenant() -> TenantContext:
    return TenantContext("org-1", "tenant-a")


def other_tenant() -> TenantContext:
    return TenantContext("org-1", "tenant-b")


def test_repository_compliance_suite_passes_for_in_memory_adapter():
    RepositoryComplianceSuite().run(InMemoryEntityRepository(), tenant())


def test_mutable_repository_compliance_suite_passes_for_in_memory_adapter():
    MutableRepositoryComplianceSuite().run(InMemoryEntityRepository(), tenant())


def test_append_only_repository_compliance_suite_passes_for_in_memory_adapter():
    AppendOnlyRepositoryComplianceSuite().run(InMemoryLineageRepository(), tenant())


def test_temporal_repository_compliance_suite_passes_for_in_memory_adapter():
    TemporalRepositoryComplianceSuite().run(InMemoryTemporalHistoryRepository(), tenant())


def test_tenant_isolation_compliance_suite_passes_for_in_memory_adapter():
    TenantIsolationComplianceSuite().run(InMemoryEntityRepository(), tenant(), other_tenant())


def test_transaction_compliance_suite_passes_for_in_memory_adapter():
    TransactionComplianceSuite().run(InMemoryPersistenceUnitOfWork(), tenant())
