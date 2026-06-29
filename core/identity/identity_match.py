from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from core.entities.entity import EnterpriseEntity, SourceSystemReference, utc_now_iso


class IdentityResolutionStatus(str, Enum):
    PENDING = "Pending"
    AUTO_MATCHED = "Auto Matched"
    NEEDS_REVIEW = "Needs Review"
    REJECTED = "Rejected"
    MERGED = "Merged"


@dataclass(frozen=True, slots=True)
class SourceIdentity:
    system: str
    external_id: str
    external_name: str = ""
    entity_type: str = ""
    attributes: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_reference(
        cls,
        reference: SourceSystemReference,
        entity_type: str = "",
    ) -> "SourceIdentity":
        return cls(
            system=reference.system,
            external_id=reference.external_id,
            external_name=reference.external_name,
            entity_type=entity_type,
            attributes=dict(reference.attributes),
        )


@dataclass(frozen=True, slots=True)
class IdentityMatchSignal:
    name: str
    score: int
    description: str


@dataclass(slots=True)
class IdentityMatchCandidate:
    source_entity_id: UUID
    target_entity_id: UUID
    source_display_name: str
    target_display_name: str
    entity_type: str
    confidence_score: int
    status: str
    signals: list[IdentityMatchSignal] = field(default_factory=list)
    id: UUID = field(default_factory=uuid4)
    created_at: str = field(default_factory=utc_now_iso)
    updated_at: str = field(default_factory=utc_now_iso)

    @property
    def score(self) -> int:
        return self.confidence_score

    @property
    def strength(self) -> str:
        if self.confidence_score >= 90:
            return "High"
        if self.confidence_score >= 70:
            return "Medium"
        if self.confidence_score > 0:
            return "Low"
        return "None"

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": str(self.id),
            "source_entity_id": str(self.source_entity_id),
            "target_entity_id": str(self.target_entity_id),
            "source_display_name": self.source_display_name,
            "target_display_name": self.target_display_name,
            "entity_type": self.entity_type,
            "confidence_score": self.confidence_score,
            "score": self.confidence_score,
            "strength": self.strength,
            "signals": [
                {
                    "name": signal.name,
                    "score": signal.score,
                    "description": signal.description,
                }
                for signal in self.signals
            ],
            "status": self.status,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


@dataclass(frozen=True, slots=True)
class IdentityResolutionDecision:
    candidate_id: UUID
    status: str
    source_entity_id: UUID | None = None
    target_entity_id: UUID | None = None
    decided_by: UUID | None = None
    decided_at: str = field(default_factory=utc_now_iso)
    notes: str = ""


def normalize_identity_text(value: str) -> str:
    return " ".join(str(value or "").strip().lower().replace("_", " ").replace("-", " ").split())


def source_identities_for_entity(entity: EnterpriseEntity) -> list[SourceIdentity]:
    return [
        SourceIdentity.from_reference(reference, entity.entity_type)
        for reference in entity.source_systems
    ]

