"""Minimal Supabase unit-of-work boundary for Data Fabric adapter operations."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from data_fabric.adapters.supabase.atomic_write import SupabaseAtomicWriteExecutor
from data_fabric.foundation import TenantContext


class SupabaseUnitOfWorkState(str, Enum):
    NOT_STARTED = "not_started"
    ACTIVE = "active"
    COMMITTED = "committed"
    ROLLED_BACK = "rolled_back"


@dataclass(slots=True)
class SupabaseDataFabricUnitOfWork:
    """Minimal state marker for isolated Supabase repository operations.

    Supabase REST does not provide transparent multi-statement transactions here.
    Individual repository operations remain available for isolated, tenant-scoped
    work. The only supported multi-record canonical write transaction path is
    the reviewed ``SupabaseAtomicWriteExecutor`` RPC boundary; this class does
    not advertise a general-purpose Python-side or distributed transaction.
    """

    tenant_context: TenantContext | None = None
    atomic_executor: SupabaseAtomicWriteExecutor | None = None
    state: SupabaseUnitOfWorkState = SupabaseUnitOfWorkState.NOT_STARTED
    failure_reason: str | None = None

    def begin(self, tenant_context: TenantContext) -> None:
        if self.state is SupabaseUnitOfWorkState.ACTIVE and tenant_context != self.tenant_context:
            raise ValueError("tenant cannot change inside an active unit of work")
        self.tenant_context = tenant_context
        self.state = SupabaseUnitOfWorkState.ACTIVE
        self.failure_reason = None

    def commit(self) -> None:
        self.state = SupabaseUnitOfWorkState.COMMITTED

    def rollback(self, reason: str) -> None:
        self.failure_reason = reason
        self.state = SupabaseUnitOfWorkState.ROLLED_BACK
