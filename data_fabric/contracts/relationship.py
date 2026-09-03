"""Canonical enterprise relationship contract."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from data_fabric.contracts._validation import normalize_enum, validate_score
from data_fabric.contracts.enums import RelationshipDecisionState, RelationshipType
from data_fabric.contracts.lineage import EntityLineage
from data_fabric.contracts.provenance import EntityProvenance
from data_fabric.contracts.quality import EntityQuality


@dataclass(slots=True)
class EnterpriseRelationship:
    """Provider-neutral contract for relationships between canonical entities."""

    id: str
    relationship_type: RelationshipType | str
    source_entity_id: str
    target_entity_id: str
    organization_id: str
    tenant_id: str | None = None
    source_system: str | None = None
    source_identifier: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    version: int = 1
    confidence_score: float = 1.0
    quality_score: float = 1.0
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    lineage: EntityLineage | None = None
    provenance: EntityProvenance | None = None
    quality: EntityQuality | None = None
    evidence: tuple[str, ...] = ()
    discovery_timestamp: datetime | None = None
    last_validation: datetime | None = None
    lineage_reference: str | None = None
    provenance_reference: str | None = None
    decision_state: RelationshipDecisionState | str = RelationshipDecisionState.CONFIRMED
    effective_from: datetime | None = None
    effective_to: datetime | None = None
    actor: str | None = None
    actor_role: str | None = None
    decision_reason: str | None = None
    superseded_by: str | None = None

    def __post_init__(self) -> None:
        self.relationship_type = normalize_enum(
            RelationshipType,
            self.relationship_type,
            "relationship_type",
        )
        self.decision_state = normalize_enum(
            RelationshipDecisionState,
            self.decision_state,
            "decision_state",
        )
        self.confidence_score = validate_score(self.confidence_score, "confidence_score")
        self.quality_score = validate_score(self.quality_score, "quality_score")
        self.evidence = tuple(str(value).strip() for value in self.evidence if str(value).strip())
        if self.effective_from is not None and self.effective_to is not None:
            if self.effective_to <= self.effective_from:
                raise ValueError("effective_to must be after effective_from")
