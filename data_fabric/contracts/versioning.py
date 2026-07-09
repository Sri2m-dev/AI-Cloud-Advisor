"""Versioning contract for canonical enterprise entities."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass(slots=True)
class EntityVersion:
    """Version metadata for canonical entity state and derived intelligence."""

    version: int = 1
    effective_from: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    effective_to: datetime | None = None
    source_updated_at: datetime | None = None
    change_reason: str | None = None
    supersedes_version: int | None = None
    superseded_by_version: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
