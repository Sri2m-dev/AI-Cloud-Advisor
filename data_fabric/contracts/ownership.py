"""Ownership contract for canonical enterprise entities."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class EntityOwnership:
    """Accountability metadata for canonical enterprise entities."""

    owner_id: str | None = None
    owner_name: str | None = None
    owner_email: str | None = None
    department_id: str | None = None
    department_name: str | None = None
    cost_center_id: str | None = None
    accountability: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
