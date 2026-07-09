"""Canonical enterprise entity contract."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from data_fabric.contracts._validation import normalize_enum, validate_score
from data_fabric.contracts.enums import EntityType
from data_fabric.contracts.identity import EntityIdentity
from data_fabric.contracts.lineage import EntityLineage
from data_fabric.contracts.ownership import EntityOwnership
from data_fabric.contracts.provenance import EntityProvenance
from data_fabric.contracts.quality import EntityQuality
from data_fabric.contracts.versioning import EntityVersion


@dataclass(slots=True)
class EnterpriseEntity:
    """Provider-neutral canonical contract for enterprise entities."""

    id: str
    canonical_id: str
    entity_type: EntityType | str
    name: str
    source_system: str
    source_identifier: str
    organization_id: str
    tenant_id: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    version: int = 1
    confidence_score: float = 1.0
    quality_score: float = 1.0
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    identity: EntityIdentity | None = None
    lineage: EntityLineage | None = None
    provenance: EntityProvenance | None = None
    entity_version: EntityVersion | None = None
    quality: EntityQuality | None = None
    ownership: EntityOwnership | None = None

    def __post_init__(self) -> None:
        self.entity_type = normalize_enum(EntityType, self.entity_type, "entity_type")
        self.confidence_score = validate_score(self.confidence_score, "confidence_score")
        self.quality_score = validate_score(self.quality_score, "quality_score")
