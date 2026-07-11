"""Minimal Supabase unit-of-work boundary for Data Fabric adapter operations."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from data_fabric.foundation import TenantContext


class SupabaseUnitOfWorkState(str, Enum):
    NOT_STARTED = "not_started"
    ACTIVE = "active"
    COMMITTED = "committed"
    ROLLED_BACK = "rolled_back"


@dataclass(slots=True)
class SupabaseDataFabricUnitOfWork:
    """Minimal transaction boundary placeholder for entity operations.

    Supabase REST does not provide transparent multi-statement transactions here.
    Multi-step atomic behavior must use reviewed SQL/RPC in a later phase.
    """

    tenant_context: TenantContext | None = None
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
