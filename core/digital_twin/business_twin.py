from __future__ import annotations

from collections import deque
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from core.entities.entity import EnterpriseEntity, EntityRelationship, EntityType, utc_now_iso


class BusinessTwinLevel(str, Enum):
    ORGANIZATION = "Organization"
    BUSINESS_UNIT = "Business Unit"
    DEPARTMENT = "Department"
    BUSINESS_CAPABILITY = "Business Capability"
    BUSINESS_SERVICE = "Business Service"
    APPLICATION = "Application"


LEVEL_BY_ENTITY_TYPE = {
    EntityType.ORGANIZATION.value: BusinessTwinLevel.ORGANIZATION.value,
    EntityType.BUSINESS_UNIT.value: BusinessTwinLevel.BUSINESS_UNIT.value,
    EntityType.DEPARTMENT.value: BusinessTwinLevel.DEPARTMENT.value,
    EntityType.BUSINESS_CAPABILITY.value: BusinessTwinLevel.BUSINESS_CAPABILITY.value,
    EntityType.BUSINESS_SERVICE.value: BusinessTwinLevel.BUSINESS_SERVICE.value,
    EntityType.APPLICATION.value: BusinessTwinLevel.APPLICATION.value,
}

HIERARCHY_ORDER = [
    BusinessTwinLevel.ORGANIZATION.value,
    BusinessTwinLevel.BUSINESS_UNIT.value,
    BusinessTwinLevel.DEPARTMENT.value,
    BusinessTwinLevel.BUSINESS_CAPABILITY.value,
    BusinessTwinLevel.BUSINESS_SERVICE.value,
    BusinessTwinLevel.APPLICATION.value,
]


@dataclass(slots=True)
class BusinessTwinNode:
    entity_id: UUID
    organization_id: UUID
    display_name: str
    entity_type: str
    level: str
    id: UUID = field(default_factory=uuid4)
    parent_entity_id: UUID | None = None
    owner_id: UUID | None = None
    cost: float = 0.0
    risk_score: float = 0.0
    health_score: float = 100.0
    dependency_entity_ids: list[UUID] = field(default_factory=list)
    technology_entity_ids: list[UUID] = field(default_factory=list)
    vendor_entity_ids: list[UUID] = field(default_factory=list)
    kpis: dict[str, float | int | str] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=utc_now_iso)
    updated_at: str = field(default_factory=utc_now_iso)

    @classmethod
    def from_entity(cls, entity: EnterpriseEntity, parent_entity_id: UUID | None = None) -> "BusinessTwinNode":
        return cls(
            entity_id=entity.id,
            organization_id=entity.organization_id,
            display_name=entity.display_name,
            entity_type=entity.entity_type,
            level=LEVEL_BY_ENTITY_TYPE[entity.entity_type],
            parent_entity_id=parent_entity_id,
            owner_id=entity.owner_id,
            cost=_metadata_number(entity.metadata, "cost", "monthly_cost", "annual_cost"),
            risk_score=_metadata_number(entity.metadata, "risk_score", "risk"),
            health_score=_bounded(_metadata_number(entity.metadata, "health_score", "health", default=100.0)),
            kpis=dict(entity.metadata.get("kpis", {})) if isinstance(entity.metadata.get("kpis"), dict) else {},
            metadata=dict(entity.metadata),
        )

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        for key in (
            "id",
            "entity_id",
            "organization_id",
            "parent_entity_id",
            "owner_id",
        ):
            payload[key] = str(payload[key]) if payload.get(key) else None
        payload["dependency_entity_ids"] = [str(value) for value in self.dependency_entity_ids]
        payload["technology_entity_ids"] = [str(value) for value in self.technology_entity_ids]
        payload["vendor_entity_ids"] = [str(value) for value in self.vendor_entity_ids]
        return payload

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "BusinessTwinNode":
        data = dict(payload)
        for key in ("id", "entity_id", "organization_id", "parent_entity_id", "owner_id"):
            data[key] = UUID(str(data[key])) if data.get(key) else None
        data["dependency_entity_ids"] = [UUID(str(value)) for value in data.get("dependency_entity_ids", [])]
        data["technology_entity_ids"] = [UUID(str(value)) for value in data.get("technology_entity_ids", [])]
        data["vendor_entity_ids"] = [UUID(str(value)) for value in data.get("vendor_entity_ids", [])]
        return cls(**data)


@dataclass(frozen=True, slots=True)
class BusinessTwinEdge:
    source_entity_id: UUID
    target_entity_id: UUID
    relationship_type: str
    id: UUID = field(default_factory=uuid4)
    strength: str = "Medium"
    confidence_score: float = 1.0
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_relationship(cls, relationship: EntityRelationship) -> "BusinessTwinEdge":
        return cls(
            source_entity_id=relationship.source_entity_id,
            target_entity_id=relationship.target_entity_id,
            relationship_type=relationship.relationship_type,
            strength=relationship.strength,
            confidence_score=relationship.confidence_score,
            metadata=dict(relationship.metadata),
        )

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        for key in ("id", "source_entity_id", "target_entity_id"):
            payload[key] = str(payload[key])
        return payload

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "BusinessTwinEdge":
        data = dict(payload)
        for key in ("id", "source_entity_id", "target_entity_id"):
            data[key] = UUID(str(data[key]))
        return cls(**data)


@dataclass(slots=True)
class BusinessTwin:
    organization_id: UUID
    id: UUID = field(default_factory=uuid4)
    name: str = "Business Digital Twin"
    version: str = "1.0.0"
    nodes: dict[UUID, BusinessTwinNode] = field(default_factory=dict)
    edges: list[BusinessTwinEdge] = field(default_factory=list)
    generated_at: str = field(default_factory=utc_now_iso)
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def build(
        cls,
        organization_id: UUID,
        entities: list[EnterpriseEntity],
        relationships: list[EntityRelationship],
        name: str = "Business Digital Twin",
    ) -> "BusinessTwin":
        model = cls(organization_id=organization_id, name=name)
        business_entities = [
            entity
            for entity in entities
            if entity.organization_id == organization_id and entity.entity_type in LEVEL_BY_ENTITY_TYPE
        ]
        parent_by_child = _parent_map(business_entities, relationships)
        model.nodes = {
            entity.id: BusinessTwinNode.from_entity(entity, parent_by_child.get(entity.id))
            for entity in business_entities
        }
        model.edges = [
            BusinessTwinEdge.from_relationship(relationship)
            for relationship in relationships
            if relationship.source_entity_id in model.nodes or relationship.target_entity_id in model.nodes
        ]
        model._enrich_node_context(entities, relationships)
        model._roll_up_metrics()
        model.metadata = model._summary()
        return model

    def children_of(self, entity_id: UUID | str) -> list[BusinessTwinNode]:
        resolved_id = UUID(str(entity_id))
        return sorted(
            [node for node in self.nodes.values() if node.parent_entity_id == resolved_id],
            key=lambda node: (HIERARCHY_ORDER.index(node.level), node.display_name.lower()),
        )

    def business_services_for_capability(self, capability_id: UUID | str) -> list[BusinessTwinNode]:
        return [
            node
            for node in self.descendants(capability_id)
            if node.level == BusinessTwinLevel.BUSINESS_SERVICE.value
        ]

    def applications_for_service(self, service_id: UUID | str) -> list[BusinessTwinNode]:
        return [
            node
            for node in self.descendants(service_id)
            if node.level == BusinessTwinLevel.APPLICATION.value
        ]

    def technologies_for_service(self, service_id: UUID | str) -> list[UUID]:
        technology_ids: set[UUID] = set()
        for node in self.applications_for_service(service_id):
            technology_ids.update(node.technology_entity_ids)
        return sorted(technology_ids, key=str)

    def vendors_for_service(self, service_id: UUID | str) -> list[UUID]:
        vendor_ids: set[UUID] = set()
        for node in self.applications_for_service(service_id):
            vendor_ids.update(node.vendor_entity_ids)
        return sorted(vendor_ids, key=str)

    def inherited_risks(self, entity_id: UUID | str) -> list[UUID]:
        resolved_id = UUID(str(entity_id))
        risk_ids: set[UUID] = set()
        for edge in self.edges:
            if edge.relationship_type in {"IMPACTS", "HAS_RISK"} and edge.target_entity_id == resolved_id:
                risk_ids.add(edge.source_entity_id)
        for descendant in self.descendants(resolved_id):
            for edge in self.edges:
                if edge.relationship_type in {"IMPACTS", "HAS_RISK"} and edge.target_entity_id == descendant.entity_id:
                    risk_ids.add(edge.source_entity_id)
        return sorted(risk_ids, key=str)

    def entity_context(self, entity_id: UUID | str) -> dict[str, Any]:
        resolved_id = UUID(str(entity_id))
        node = self.nodes.get(resolved_id)
        if not node:
            raise KeyError(f"Business twin node not found: {entity_id}")
        return {
            "node": node.to_dict(),
            "children": [child.to_dict() for child in self.children_of(resolved_id)],
            "applications": [item.to_dict() for item in self.applications_for_service(resolved_id)],
            "technologies": [str(item) for item in self.technologies_for_service(resolved_id)],
            "vendors": [str(item) for item in self.vendors_for_service(resolved_id)],
            "inherited_risks": [str(item) for item in self.inherited_risks(resolved_id)],
            "total_cost": self.total_cost(resolved_id),
            "health_score": self.health_score(resolved_id),
        }

    def total_cost(self, entity_id: UUID | str) -> float:
        resolved_id = UUID(str(entity_id))
        node = self.nodes.get(resolved_id)
        return round(node.cost, 2) if node else 0.0

    def health_score(self, entity_id: UUID | str) -> float:
        resolved_id = UUID(str(entity_id))
        nodes = [self.nodes[resolved_id], *self.descendants(resolved_id)] if resolved_id in self.nodes else []
        return round(sum(node.health_score for node in nodes) / len(nodes), 2) if nodes else 100.0

    def descendants(self, entity_id: UUID | str) -> list[BusinessTwinNode]:
        root_id = UUID(str(entity_id))
        descendants: list[BusinessTwinNode] = []
        queue: deque[UUID] = deque([root_id])
        while queue:
            current_id = queue.popleft()
            for child in self.children_of(current_id):
                descendants.append(child)
                queue.append(child.entity_id)
        return descendants

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": str(self.id),
            "organization_id": str(self.organization_id),
            "name": self.name,
            "version": self.version,
            "nodes": [node.to_dict() for node in self.nodes.values()],
            "edges": [edge.to_dict() for edge in self.edges],
            "generated_at": self.generated_at,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "BusinessTwin":
        model = cls(
            id=UUID(str(payload["id"])),
            organization_id=UUID(str(payload["organization_id"])),
            name=payload.get("name", "Business Digital Twin"),
            version=payload.get("version", "1.0.0"),
            generated_at=payload.get("generated_at", utc_now_iso()),
            metadata=dict(payload.get("metadata", {})),
        )
        model.nodes = {
            node.entity_id: node
            for node in [BusinessTwinNode.from_dict(item) for item in payload.get("nodes", [])]
        }
        model.edges = [BusinessTwinEdge.from_dict(item) for item in payload.get("edges", [])]
        return model

    def _enrich_node_context(
        self,
        entities: list[EnterpriseEntity],
        relationships: list[EntityRelationship],
    ) -> None:
        entity_by_id = {entity.id: entity for entity in entities}
        for node in self.nodes.values():
            adjacent = _adjacent_ids(node.entity_id, relationships)
            node.dependency_entity_ids = sorted(adjacent, key=str)
            node.technology_entity_ids = sorted(
                [
                    entity_id
                    for entity_id in adjacent
                    if (entity := entity_by_id.get(entity_id))
                    and entity.entity_type in {EntityType.TECHNOLOGY.value, EntityType.CLOUD_RESOURCE.value, EntityType.CLOUD_ACCOUNT.value}
                ],
                key=str,
            )
            vendor_ids = {
                entity_id
                for entity_id in adjacent
                if (entity := entity_by_id.get(entity_id)) and entity.entity_type == EntityType.VENDOR.value
            }
            for technology_id in node.technology_entity_ids:
                for candidate_id in _adjacent_ids(technology_id, relationships):
                    candidate = entity_by_id.get(candidate_id)
                    if candidate and candidate.entity_type == EntityType.VENDOR.value:
                        vendor_ids.add(candidate_id)
            node.vendor_entity_ids = sorted(
                vendor_ids,
                key=str,
            )

    def _roll_up_metrics(self) -> None:
        for level in reversed(HIERARCHY_ORDER):
            for node in [item for item in self.nodes.values() if item.level == level]:
                children = self.children_of(node.entity_id)
                if not children:
                    continue
                node.cost = round(node.cost + sum(child.cost for child in children), 2)
                node.risk_score = round(max([node.risk_score, *[child.risk_score for child in children]]), 2)
                node.health_score = round(sum(child.health_score for child in children) / len(children), 2)
                node.technology_entity_ids = sorted(
                    set(node.technology_entity_ids).union(*(child.technology_entity_ids for child in children)),
                    key=str,
                )
                node.vendor_entity_ids = sorted(
                    set(node.vendor_entity_ids).union(*(child.vendor_entity_ids for child in children)),
                    key=str,
                )

    def _summary(self) -> dict[str, Any]:
        counts = {level: 0 for level in HIERARCHY_ORDER}
        for node in self.nodes.values():
            counts[node.level] += 1
        return {
            "hierarchy": HIERARCHY_ORDER,
            "node_counts": counts,
            "edge_count": len(self.edges),
            "total_cost": round(sum(node.cost for node in self.nodes.values() if node.level == BusinessTwinLevel.ORGANIZATION.value), 2),
            "average_health": round(sum(node.health_score for node in self.nodes.values()) / len(self.nodes), 2) if self.nodes else 100.0,
        }


def _parent_map(
    business_entities: list[EnterpriseEntity],
    relationships: list[EntityRelationship],
) -> dict[UUID, UUID]:
    entity_by_id = {entity.id: entity for entity in business_entities}
    parent_by_child: dict[UUID, UUID] = {}
    for relationship in relationships:
        source = entity_by_id.get(relationship.source_entity_id)
        target = entity_by_id.get(relationship.target_entity_id)
        if not source or not target:
            continue
        if relationship.relationship_type in {"BELONGS_TO", "DEPENDS_ON", "RUNS_ON"}:
            parent_by_child[source.id] = target.id
        elif relationship.relationship_type in {"OWNS", "USES", "SUPPORTS"}:
            parent_by_child[target.id] = source.id
    return parent_by_child


def _adjacent_ids(entity_id: UUID, relationships: list[EntityRelationship]) -> set[UUID]:
    adjacent: set[UUID] = set()
    for relationship in relationships:
        if relationship.source_entity_id == entity_id:
            adjacent.add(relationship.target_entity_id)
        if relationship.target_entity_id == entity_id:
            adjacent.add(relationship.source_entity_id)
    return adjacent


def _metadata_number(metadata: dict[str, Any], *keys: str, default: float = 0.0) -> float:
    for key in keys:
        value = metadata.get(key)
        if value is None:
            continue
        try:
            return float(value)
        except (TypeError, ValueError):
            continue
    return default


def _bounded(value: float) -> float:
    return round(max(0.0, min(100.0, value)), 2)
