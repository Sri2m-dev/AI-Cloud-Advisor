from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import UUID, uuid4


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class LifecycleState(str, Enum):
    ACTIVE = "Active"
    PLANNED = "Planned"
    DEPRECATED = "Deprecated"
    RETIRED = "Retired"


class EntityType(str, Enum):
    ORGANIZATION = "Organization"
    BUSINESS_UNIT = "BusinessUnit"
    DEPARTMENT = "Department"
    TEAM = "Team"
    BUSINESS_CAPABILITY = "BusinessCapability"
    BUSINESS_SERVICE = "BusinessService"
    APPLICATION = "Application"
    TECHNOLOGY = "Technology"
    CLOUD_ACCOUNT = "CloudAccount"
    CLOUD_RESOURCE = "CloudResource"
    SAAS_APPLICATION = "SaaSApplication"
    VENDOR = "Vendor"
    COST_CENTER = "CostCenter"
    ENVIRONMENT = "Environment"
    PROJECT = "Project"
    REGION = "Region"
    USER = "User"
    ROLE = "Role"
    POLICY = "Policy"
    RISK = "Risk"
    CONTROL = "Control"
    INCIDENT = "Incident"
    RECOMMENDATION = "Recommendation"
    APPROVAL = "Approval"


class RelationshipType(str, Enum):
    OWNS = "OWNS"
    BELONGS_TO = "BELONGS_TO"
    USES = "USES"
    RUNS_ON = "RUNS_ON"
    DEPLOYED_IN = "DEPLOYED_IN"
    HOSTED_IN = "HOSTED_IN"
    MONITORED_BY = "MONITORED_BY"
    SUPPLIES = "SUPPLIES"
    GENERATES = "GENERATES"
    MITIGATED_BY = "MITIGATED_BY"
    DEPENDS_ON = "DEPENDS_ON"
    SUPPORTS = "SUPPORTS"
    GOVERNED_BY = "GOVERNED_BY"
    IMPLEMENTS = "IMPLEMENTS"
    AFFECTS = "AFFECTS"
    APPROVES = "APPROVES"


@dataclass(slots=True)
class SourceSystemReference:
    system: str
    external_id: str
    external_name: str = ""
    url: str = ""
    first_seen_at: str = field(default_factory=utc_now_iso)
    last_seen_at: str = field(default_factory=utc_now_iso)
    attributes: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class EntityRelationship:
    source_entity_id: UUID
    relationship_type: str
    target_entity_id: UUID
    confidence: float = 1.0
    source_system: str = "manual"
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=utc_now_iso)
    updated_at: str = field(default_factory=utc_now_iso)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["source_entity_id"] = str(self.source_entity_id)
        payload["target_entity_id"] = str(self.target_entity_id)
        return payload

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "EntityRelationship":
        data = dict(payload)
        data["source_entity_id"] = UUID(str(data["source_entity_id"]))
        data["target_entity_id"] = UUID(str(data["target_entity_id"]))
        return cls(**data)


@dataclass(slots=True)
class EnterpriseEntity:
    display_name: str
    organization_id: UUID
    entity_type: str
    description: str = ""
    id: UUID = field(default_factory=uuid4)
    owner_id: UUID | None = None
    lifecycle_state: str = LifecycleState.ACTIVE.value
    source_systems: list[SourceSystemReference] = field(default_factory=list)
    tags: dict[str, str] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=utc_now_iso)
    updated_at: str = field(default_factory=utc_now_iso)
    created_by: UUID | None = None
    updated_by: UUID | None = None

    def touch(self, updated_by: UUID | None = None) -> None:
        self.updated_at = utc_now_iso()
        if updated_by:
            self.updated_by = updated_by

    def add_source_reference(
        self,
        system: str,
        external_id: str,
        external_name: str = "",
        url: str = "",
        attributes: dict[str, Any] | None = None,
    ) -> None:
        for reference in self.source_systems:
            if reference.system == system and reference.external_id == external_id:
                reference.external_name = external_name or reference.external_name
                reference.url = url or reference.url
                reference.last_seen_at = utc_now_iso()
                reference.attributes.update(attributes or {})
                self.touch()
                return

        self.source_systems.append(
            SourceSystemReference(
                system=system,
                external_id=external_id,
                external_name=external_name,
                url=url,
                attributes=attributes or {},
            )
        )
        self.touch()

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["id"] = str(self.id)
        payload["organization_id"] = str(self.organization_id)
        payload["owner_id"] = str(self.owner_id) if self.owner_id else None
        payload["created_by"] = str(self.created_by) if self.created_by else None
        payload["updated_by"] = str(self.updated_by) if self.updated_by else None
        return payload

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "EnterpriseEntity":
        data = dict(payload)
        data["id"] = UUID(str(data["id"]))
        data["organization_id"] = UUID(str(data["organization_id"]))
        data["owner_id"] = UUID(str(data["owner_id"])) if data.get("owner_id") else None
        data["created_by"] = UUID(str(data["created_by"])) if data.get("created_by") else None
        data["updated_by"] = UUID(str(data["updated_by"])) if data.get("updated_by") else None
        data["source_systems"] = [
            SourceSystemReference(**reference)
            for reference in data.get("source_systems", [])
        ]
        return cls(**data)

