from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any
from uuid import UUID, uuid4

from core.digital_twin.technology.infrastructure_mapping import InfrastructureMapping
from core.digital_twin.technology.infrastructure_resource import InfrastructureResource
from core.entities.entity import utc_now_iso


@dataclass(slots=True)
class InfrastructureLayer:
    technology_id: UUID
    id: UUID = field(default_factory=uuid4)
    resources: dict[UUID, InfrastructureResource] = field(default_factory=dict)
    mappings: list[InfrastructureMapping] = field(default_factory=list)
    health_score: float = 100.0
    cost: float = 0.0
    risk_score: float = 0.0
    generated_at: str = field(default_factory=utc_now_iso)
    metadata: dict[str, Any] = field(default_factory=dict)

    def attach_resource(
        self,
        resource: InfrastructureResource,
        relationship_type: str = "RUNS_ON",
        confidence_score: float = 1.0,
        source_system: str = "technology_twin",
    ) -> InfrastructureMapping:
        self.resources[resource.id] = resource
        mapping = InfrastructureMapping(
            technology_id=self.technology_id,
            resource_id=resource.id,
            relationship_type=relationship_type,
            confidence_score=confidence_score,
            source_system=source_system,
            metadata={
                "provider": resource.provider,
                "resource_type": resource.resource_type,
                "resource_entity_id": str(resource.entity_id) if resource.entity_id else "",
            },
        )
        self.mappings = [
            existing
            for existing in self.mappings
            if not (existing.technology_id == mapping.technology_id and existing.resource_id == mapping.resource_id)
        ]
        self.mappings.append(mapping)
        self.refresh()
        return mapping

    def refresh(self) -> None:
        resources = list(self.resources.values())
        self.cost = round(sum(resource.cost for resource in resources), 2)
        self.health_score = round(sum(resource.health for resource in resources) / len(resources), 2) if resources else 100.0
        self.risk_score = round(max((resource.risk for resource in resources), default=0.0), 2)
        self.generated_at = utc_now_iso()
        self.metadata = {
            "resource_count": len(resources),
            "providers": sorted({resource.provider for resource in resources if resource.provider}),
            "resource_types": sorted({resource.resource_type for resource in resources}),
            "monthly_cost": self.cost,
            "average_health": self.health_score,
            "max_risk": self.risk_score,
        }

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["id"] = str(self.id)
        payload["technology_id"] = str(self.technology_id)
        payload["resources"] = [resource.to_dict() for resource in self.resources.values()]
        payload["mappings"] = [mapping.to_dict() for mapping in self.mappings]
        return payload

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "InfrastructureLayer":
        data = dict(payload)
        data["id"] = UUID(str(data["id"])) if data.get("id") else uuid4()
        data["technology_id"] = UUID(str(data["technology_id"]))
        resources = [InfrastructureResource.from_dict(item) for item in data.pop("resources", [])]
        data["resources"] = {resource.id: resource for resource in resources}
        data["mappings"] = [InfrastructureMapping.from_dict(item) for item in data.get("mappings", [])]
        return cls(**data)
