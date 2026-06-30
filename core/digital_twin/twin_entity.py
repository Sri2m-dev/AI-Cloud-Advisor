from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from core.entities.entity import EnterpriseEntity, utc_now_iso


class TwinLayer(str, Enum):
    ORGANIZATION = "Organization"
    BUSINESS = "Business"
    APPLICATION = "Application"
    TECHNOLOGY = "Technology"
    CLOUD = "Cloud"
    SAAS = "SaaS"
    COST = "Cost"
    RISK = "Risk"
    COMPLIANCE = "Compliance"
    OBSERVABILITY = "Observability"


class TwinEntityStatus(str, Enum):
    ACTIVE = "Active"
    WARNING = "Warning"
    DEGRADED = "Degraded"
    UNKNOWN = "Unknown"


@dataclass(slots=True)
class TwinEntity:
    source_entity_id: UUID
    organization_id: UUID
    display_name: str
    entity_type: str
    id: UUID = field(default_factory=uuid4)
    layer: str = TwinLayer.TECHNOLOGY.value
    status: str = TwinEntityStatus.UNKNOWN.value
    health_score: float = 100.0
    risk_score: float = 0.0
    cost_score: float = 0.0
    owner_id: UUID | None = None
    source_systems: list[str] = field(default_factory=list)
    tags: dict[str, str] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=utc_now_iso)
    updated_at: str = field(default_factory=utc_now_iso)

    @classmethod
    def from_entity(cls, entity: EnterpriseEntity) -> "TwinEntity":
        return cls(
            source_entity_id=entity.id,
            organization_id=entity.organization_id,
            display_name=entity.display_name,
            entity_type=entity.entity_type,
            layer=layer_for_entity_type(entity.entity_type),
            owner_id=entity.owner_id,
            source_systems=sorted({reference.system for reference in entity.source_systems}),
            tags=dict(entity.tags),
            metadata=dict(entity.metadata),
            updated_at=entity.updated_at,
        )

    def refresh_from_entity(self, entity: EnterpriseEntity) -> None:
        self.display_name = entity.display_name
        self.entity_type = entity.entity_type
        self.layer = layer_for_entity_type(entity.entity_type)
        self.owner_id = entity.owner_id
        self.source_systems = sorted({reference.system for reference in entity.source_systems})
        self.tags = dict(entity.tags)
        self.metadata.update(entity.metadata)
        self.updated_at = utc_now_iso()

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        for key in ("id", "source_entity_id", "organization_id", "owner_id"):
            payload[key] = str(payload[key]) if payload.get(key) else None
        return payload

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "TwinEntity":
        data = dict(payload)
        for key in ("id", "source_entity_id", "organization_id", "owner_id"):
            data[key] = UUID(str(data[key])) if data.get(key) else None
        return cls(**data)


def layer_for_entity_type(entity_type: str) -> str:
    normalized = entity_type.lower()
    if normalized in {"organization", "businessunit", "department", "team"}:
        return TwinLayer.ORGANIZATION.value
    if normalized in {"businesscapability", "businessservice"}:
        return TwinLayer.BUSINESS.value
    if normalized == "application":
        return TwinLayer.APPLICATION.value
    if normalized in {"technology", "cloudresource", "cloudaccount", "environment", "region"}:
        return TwinLayer.CLOUD.value if "cloud" in normalized else TwinLayer.TECHNOLOGY.value
    if normalized in {"saasapplication", "vendor"}:
        return TwinLayer.SAAS.value
    if normalized == "costcenter":
        return TwinLayer.COST.value
    if normalized == "risk":
        return TwinLayer.RISK.value
    if normalized in {"control", "policy"}:
        return TwinLayer.COMPLIANCE.value
    if normalized == "incident":
        return TwinLayer.OBSERVABILITY.value
    return TwinLayer.TECHNOLOGY.value
