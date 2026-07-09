"""Provenance contracts for canonical enterprise entities."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass(slots=True)
class EntityProvenance:
    """Explain authority, derivation, and trust for a canonical fact."""

    source_system: str
    source_identifier: str
    collection_method: str
    connector_version: str | None = None
    normalization_rule: str | None = None
    identity_resolution_rule: str | None = None
    reviewed_by: str | None = None
    reviewed_at: datetime | None = None
    captured_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = field(default_factory=dict)
