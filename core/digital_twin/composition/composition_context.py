from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID

from core.digital_twin.composition.composition_policy import CompositionPolicy


@dataclass(frozen=True, slots=True)
class CompositionContext:
    organization_id: UUID
    root_entity_id: UUID | None = None
    twin_type: str = "Technology"
    policy: CompositionPolicy = field(default_factory=CompositionPolicy)
    metadata: dict = field(default_factory=dict)
