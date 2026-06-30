from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any
from uuid import UUID, uuid4

from core.digital_twin.technology.infrastructure_resource import InfrastructureResource
from core.digital_twin.technology.technology_node import TechnologyNode
from core.digital_twin.technology.technology_relationships import TechnologyRelationship
from core.entities.entity import EnterpriseEntity, EntityRelationship, EntityType, utc_now_iso


TECHNOLOGY_ENTITY_TYPES = {
    EntityType.TECHNOLOGY.value,
    EntityType.CLOUD_ACCOUNT.value,
    EntityType.CLOUD_RESOURCE.value,
    EntityType.SAAS_APPLICATION.value,
    EntityType.CONTROL.value,
    EntityType.POLICY.value,
}

INFRASTRUCTURE_ENTITY_TYPES = {
    EntityType.CLOUD_ACCOUNT.value,
    EntityType.CLOUD_RESOURCE.value,
}


@dataclass(slots=True)
class TechnologyTwin:
    organization_id: UUID
    id: UUID = field(default_factory=uuid4)
    name: str = "Technology Digital Twin"
    version: str = "1.0.0"
    nodes: dict[UUID, TechnologyNode] = field(default_factory=dict)
    relationships: list[TechnologyRelationship] = field(default_factory=list)
    generated_at: str = field(default_factory=utc_now_iso)
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def build(
        cls,
        organization_id: UUID,
        entities: list[EnterpriseEntity],
        relationships: list[EntityRelationship],
        name: str = "Technology Digital Twin",
    ) -> "TechnologyTwin":
        twin = cls(organization_id=organization_id, name=name)
        entity_by_id = {entity.id: entity for entity in entities if entity.organization_id == organization_id}
        twin.nodes = {
            entity.id: TechnologyNode.from_entity(entity)
            for entity in entity_by_id.values()
            if entity.entity_type in TECHNOLOGY_ENTITY_TYPES
        }
        twin.relationships = [
            TechnologyRelationship.from_relationship(relationship)
            for relationship in relationships
            if relationship.source_entity_id in entity_by_id and relationship.target_entity_id in entity_by_id
            and (relationship.source_entity_id in twin.nodes or relationship.target_entity_id in twin.nodes)
        ]
        twin._attach_business_context(entity_by_id, relationships)
        twin._attach_infrastructure_layer(entity_by_id, relationships)
        twin.refresh()
        return twin

    def refresh(self) -> None:
        for node in self.nodes.values():
            if node.infrastructure_layer:
                node.infrastructure_layer.refresh()
            node.refresh_state()
        self.generated_at = utc_now_iso()
        self.metadata = self._summary()

    def graph(self) -> dict[str, Any]:
        return {
            "twin_id": str(self.id),
            "nodes": [
                {
                    "id": str(node.technology_id),
                    "label": node.name,
                    "type": node.technology_type,
                    "status": node.status,
                    "health": node.state.health_score if node.state else 100.0,
                    "cost": node.monthly_cost,
                    "risk": node.risk,
                }
                for node in self.nodes.values()
            ],
            "infrastructure_nodes": [
                {
                    "id": str(resource.id),
                    "entity_id": str(resource.entity_id) if resource.entity_id else "",
                    "label": resource.name,
                    "type": resource.resource_type,
                    "provider": resource.provider,
                    "health": resource.health,
                    "cost": resource.cost,
                    "risk": resource.risk,
                    "technology_id": str(node.technology_id),
                }
                for node in self.nodes.values()
                for resource in (node.infrastructure_layer.resources.values() if node.infrastructure_layer else [])
            ],
            "edges": [
                *[relationship.to_dict() for relationship in self.relationships],
                *[
                    {
                        "id": str(mapping.id),
                        "source_entity_id": str(mapping.technology_id),
                        "target_entity_id": str(mapping.resource_id),
                        "relationship_type": mapping.relationship_type,
                        "strength": "High",
                        "confidence_score": mapping.confidence_score,
                        "source_system": mapping.source_system,
                        "metadata": mapping.metadata,
                    }
                    for node in self.nodes.values()
                    for mapping in (node.infrastructure_layer.mappings if node.infrastructure_layer else [])
                ],
            ],
            "generated_at": self.generated_at,
        }

    def technology_context(self, technology_id: UUID | str) -> dict[str, Any]:
        resolved_id = UUID(str(technology_id))
        node = self.nodes.get(resolved_id)
        if not node:
            raise KeyError(f"Technology twin node not found: {technology_id}")
        return {
            "node": node.to_dict(),
            "relationships": [
                relationship.to_dict()
                for relationship in self.relationships
                if relationship.source_entity_id == resolved_id or relationship.target_entity_id == resolved_id
            ],
            "applications": [str(value) for value in node.application_ids],
            "business_services": [str(value) for value in node.business_service_ids],
            "health": node.health.to_dict() if node.health else None,
            "state": node.state.to_dict() if node.state else None,
            "infrastructure_layer": node.infrastructure_layer.to_dict() if node.infrastructure_layer else None,
            "cost": {
                "current": node.cost,
                "monthly": node.monthly_cost,
                "annual": node.annual_cost,
                "forecast": node.metadata.get("forecast_cost", node.annual_cost),
                "optimization": node.metadata.get("optimization_opportunity", 0),
                "budget": node.metadata.get("budget", 0),
                "savings_opportunity": node.metadata.get("savings_opportunity", 0),
                "breakdown": node.metadata.get("cost_breakdown", {}),
            },
            "risk": {
                "risk_score": node.risk,
                "risk_posture": node.metadata.get("risk_posture", ""),
                "security_findings": node.metadata.get("security_findings", []),
                "compliance": node.metadata.get("compliance", ""),
                "technical_debt": node.metadata.get("technical_debt", ""),
                "dr_readiness": node.metadata.get("dr_readiness", ""),
                "patch_status": node.metadata.get("patch_status", ""),
                "criticality": node.metadata.get("criticality", ""),
                "breakdown": node.metadata.get("risk_breakdown", {}),
            },
            "operations": {
                "operational_health": node.metadata.get("operational_health", node.health.operational_score if node.health else 100.0),
                "operational_status": node.metadata.get("operational_status", ""),
                "open_alerts": node.metadata.get("open_alerts", 0),
                "incidents": node.metadata.get("incidents", 0),
                "deployments": node.metadata.get("deployments", 0),
                "changes": node.metadata.get("changes", 0),
                "maintenance": node.metadata.get("maintenance", ""),
                "breakdown": node.metadata.get("operational_breakdown", {}),
            },
            "ai": {
                "recommendations": node.metadata.get("recommendations", []),
                "predictions": node.metadata.get("predictions", []),
                "root_cause": node.metadata.get("root_cause", ""),
                "business_impact": node.metadata.get("business_impact", ""),
                "confidence": node.metadata.get("ai_confidence", 0),
            },
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": str(self.id),
            "organization_id": str(self.organization_id),
            "name": self.name,
            "version": self.version,
            "nodes": [node.to_dict() for node in self.nodes.values()],
            "relationships": [relationship.to_dict() for relationship in self.relationships],
            "generated_at": self.generated_at,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "TechnologyTwin":
        twin = cls(
            id=UUID(str(payload["id"])),
            organization_id=UUID(str(payload["organization_id"])),
            name=payload.get("name", "Technology Digital Twin"),
            version=payload.get("version", "1.0.0"),
            generated_at=payload.get("generated_at", utc_now_iso()),
            metadata=dict(payload.get("metadata", {})),
        )
        twin.nodes = {
            node.technology_id: node
            for node in [TechnologyNode.from_dict(item) for item in payload.get("nodes", [])]
        }
        twin.relationships = [TechnologyRelationship.from_dict(item) for item in payload.get("relationships", [])]
        return twin

    def _attach_business_context(
        self,
        entity_by_id: dict[UUID, EnterpriseEntity],
        relationships: list[EntityRelationship],
    ) -> None:
        app_to_services: dict[UUID, set[UUID]] = {}
        for relationship in relationships:
            source = entity_by_id.get(relationship.source_entity_id)
            target = entity_by_id.get(relationship.target_entity_id)
            if not source or not target:
                continue
            if source.entity_type == EntityType.BUSINESS_SERVICE.value and target.entity_type == EntityType.APPLICATION.value:
                app_to_services.setdefault(target.id, set()).add(source.id)
            if target.entity_type == EntityType.BUSINESS_SERVICE.value and source.entity_type == EntityType.APPLICATION.value:
                app_to_services.setdefault(source.id, set()).add(target.id)

        for relationship in relationships:
            source = entity_by_id.get(relationship.source_entity_id)
            target = entity_by_id.get(relationship.target_entity_id)
            if not source or not target:
                continue
            if source.entity_type == EntityType.APPLICATION.value and relationship.target_entity_id in self.nodes:
                node = self.nodes[relationship.target_entity_id]
                node.attach_application(source.id)
                for service_id in app_to_services.get(source.id, set()):
                    node.attach_business_service(service_id)
            if target.entity_type == EntityType.APPLICATION.value and relationship.source_entity_id in self.nodes:
                node = self.nodes[relationship.source_entity_id]
                node.attach_application(target.id)
                for service_id in app_to_services.get(target.id, set()):
                    node.attach_business_service(service_id)

    def _attach_infrastructure_layer(
        self,
        entity_by_id: dict[UUID, EnterpriseEntity],
        relationships: list[EntityRelationship],
    ) -> None:
        for relationship in relationships:
            source = entity_by_id.get(relationship.source_entity_id)
            target = entity_by_id.get(relationship.target_entity_id)
            if not source or not target:
                continue
            if relationship.source_entity_id in self.nodes and target.entity_type in INFRASTRUCTURE_ENTITY_TYPES:
                self.nodes[relationship.source_entity_id].attach_infrastructure_resource(
                    InfrastructureResource.from_entity(target),
                    relationship_type=relationship.relationship_type,
                    confidence_score=relationship.confidence_score,
                    source_system=relationship.source_system,
                )
            if relationship.target_entity_id in self.nodes and source.entity_type in INFRASTRUCTURE_ENTITY_TYPES:
                self.nodes[relationship.target_entity_id].attach_infrastructure_resource(
                    InfrastructureResource.from_entity(source),
                    relationship_type=relationship.relationship_type,
                    confidence_score=relationship.confidence_score,
                    source_system=relationship.source_system,
                )

    def _summary(self) -> dict[str, Any]:
        nodes = list(self.nodes.values())
        infrastructure_layers = [node.infrastructure_layer for node in nodes if node.infrastructure_layer]
        infrastructure_resources = [
            resource
            for layer in infrastructure_layers
            for resource in layer.resources.values()
        ]
        return {
            "node_count": len(nodes),
            "infrastructure_resource_count": len(infrastructure_resources),
            "relationship_count": len(self.relationships),
            "average_health": _average([node.state.health_score for node in nodes if node.state], default=100.0),
            "average_risk": _average([node.risk for node in nodes], default=0.0),
            "monthly_cost": round(sum(node.monthly_cost for node in nodes), 2),
            "annual_cost": round(sum(node.annual_cost for node in nodes), 2),
            "infrastructure_monthly_cost": round(sum(resource.cost for resource in infrastructure_resources), 2),
            "infrastructure_health": _average([resource.health for resource in infrastructure_resources], default=100.0),
            "applications": len({app_id for node in nodes for app_id in node.application_ids}),
            "business_services": len({service_id for node in nodes for service_id in node.business_service_ids}),
            "generated_at": self.generated_at,
        }


def _average(values: list[float], default: float) -> float:
    return round(sum(values) / len(values), 2) if values else default
