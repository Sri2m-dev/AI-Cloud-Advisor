"""Lineage contracts for canonical enterprise entities."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass(slots=True)
class EntityLineage:
    """Trace how a record moved from source data to canonical entity."""

    connector: str
    raw_record_id: str
    normalized_record_id: str | None = None
    canonical_entity_id: str | None = None
    transformation_name: str | None = None
    transformation_version: str | None = None
    observed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = field(default_factory=dict)
