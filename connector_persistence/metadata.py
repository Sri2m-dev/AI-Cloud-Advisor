"""Canonical persistence metadata contracts."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Mapping
from uuid import uuid4


@dataclass(frozen=True)
class PersistenceMetadata:
    """Lineage metadata attached to canonical record persistence operations."""

    connector_id: str | None = None
    provider: str | None = None
    sync_time: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    batch_id: str = field(default_factory=lambda: str(uuid4()))
    correlation_id: str | None = None
    source_system: str | None = None
    version: str = "1.0"
    schema_version: str = "canonical.v1"
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class PersistenceResult:
    """Result for persistence operations."""

    attempted: int
    succeeded: int
    failed: int = 0
    skipped: int = 0
    errors: tuple[str, ...] = field(default_factory=tuple)
    warnings: tuple[str, ...] = field(default_factory=tuple)
    batch_id: str | None = None

    @property
    def partial_success(self) -> bool:
        return self.succeeded > 0 and self.failed > 0

    @property
    def ok(self) -> bool:
        return self.failed == 0
