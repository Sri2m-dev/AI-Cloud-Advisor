"""Canonical persistence batching support."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence

from connector_normalization import CanonicalEnterpriseRecord
from connector_persistence.metadata import PersistenceMetadata, PersistenceResult
from connector_persistence.repository import CanonicalRepository


@dataclass(frozen=True)
class BatchConfig:
    chunk_size: int = 500
    retry_attempts: int = 0
    rollback_on_failure: bool = False


class BatchManager:
    """Chunks and publishes canonical records through a repository."""

    def __init__(self, config: BatchConfig | None = None) -> None:
        self.config = config or BatchConfig()

    def chunks(self, records: Sequence[CanonicalEnterpriseRecord]) -> Iterable[list[CanonicalEnterpriseRecord]]:
        size = max(1, self.config.chunk_size)
        for index in range(0, len(records), size):
            yield list(records[index:index + size])

    def save_batch(
        self,
        repository: CanonicalRepository,
        records: Sequence[CanonicalEnterpriseRecord],
        metadata: PersistenceMetadata | None = None,
    ) -> PersistenceResult:
        attempted = len(records)
        succeeded = 0
        errors: list[str] = []
        warnings: list[str] = []

        for chunk in self.chunks(records):
            result = repository.save_batch(chunk, metadata=metadata)
            succeeded += result.succeeded
            errors.extend(result.errors)
            warnings.extend(result.warnings)
            if result.failed and self.config.rollback_on_failure:
                for record in records[:succeeded]:
                    repository.delete(record.record_id)
                return PersistenceResult(
                    attempted=attempted,
                    succeeded=0,
                    failed=attempted,
                    errors=tuple(errors or ["Batch rollback completed after failure."]),
                    warnings=tuple(warnings),
                    batch_id=metadata.batch_id if metadata else None,
                )

        failed = attempted - succeeded
        return PersistenceResult(
            attempted=attempted,
            succeeded=succeeded,
            failed=failed,
            errors=tuple(errors),
            warnings=tuple(warnings),
            batch_id=metadata.batch_id if metadata else None,
        )
