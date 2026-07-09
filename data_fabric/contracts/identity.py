"""Identity contract for canonical enterprise entities."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class EntityIdentity:
    """Source and canonical identity metadata for one enterprise entity."""

    id: str
    canonical_id: str
    source_system: str
    source_identifier: str
    organization_id: str
    tenant_id: str | None = None
    aliases: list[str] = field(default_factory=list)
    source_priority: int = 100
    match_confidence: float = 1.0
    metadata: dict[str, Any] = field(default_factory=dict)
