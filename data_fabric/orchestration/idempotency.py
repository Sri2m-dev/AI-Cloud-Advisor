"""Tenant-isolated in-memory idempotency store."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from typing import Optional

from data_fabric.orchestration.exceptions import OrchestrationIdempotencyError
from data_fabric.orchestration.interfaces import IdempotencyStore
from data_fabric.orchestration.models import (
    CanonicalizationResult,
    IdempotencyKey,
    IdempotencyRecord,
    IdempotencyState,
)


class InMemoryIdempotencyStore(IdempotencyStore):
    """Deterministic non-persistent idempotency store."""

    def __init__(self) -> None:
        self._records: dict[tuple[str, str, str], IdempotencyRecord] = {}

    def begin(self, key: IdempotencyKey, payload_hash: str) -> IdempotencyRecord:
        store_key = self._store_key(key)
        existing = self._records.get(store_key)
        now = datetime.now(timezone.utc)
        if existing is None:
            record = IdempotencyRecord(key, payload_hash, IdempotencyState.IN_PROGRESS, now, now)
            self._records[store_key] = record
            return record
        if existing.payload_hash != payload_hash:
            raise OrchestrationIdempotencyError("idempotency key reused with different payload hash")
        if existing.state is IdempotencyState.COMPLETED:
            return existing
        if existing.state in {IdempotencyState.FAILED, IdempotencyState.EXPIRED}:
            record = replace(existing, state=IdempotencyState.IN_PROGRESS, updated_at=now, failure_reason=None)
            self._records[store_key] = record
            return record
        return existing

    def complete(self, key: IdempotencyKey, result: CanonicalizationResult) -> IdempotencyRecord:
        existing = self._require(key)
        record = replace(
            existing,
            state=IdempotencyState.COMPLETED,
            updated_at=datetime.now(timezone.utc),
            result=result,
            failure_reason=None,
        )
        self._records[self._store_key(key)] = record
        return record

    def fail(self, key: IdempotencyKey, reason: str) -> IdempotencyRecord:
        existing = self._require(key)
        record = replace(
            existing,
            state=IdempotencyState.FAILED,
            updated_at=datetime.now(timezone.utc),
            failure_reason=reason,
        )
        self._records[self._store_key(key)] = record
        return record

    def get(self, key: IdempotencyKey) -> Optional[IdempotencyRecord]:
        return self._records.get(self._store_key(key))

    @staticmethod
    def _store_key(key: IdempotencyKey) -> tuple[str, str, str]:
        return (key.tenant_context.organization_id, key.tenant_context.tenant_id, key.value)

    def _require(self, key: IdempotencyKey) -> IdempotencyRecord:
        record = self.get(key)
        if record is None:
            raise OrchestrationIdempotencyError("idempotency record has not started")
        return record
