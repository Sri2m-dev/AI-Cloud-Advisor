from __future__ import annotations

from uuid import UUID

from core.digital_twin.technology import InfrastructureLayer, InfrastructureResource, TechnologyTwin
from core.digital_twin.technology.technology_twin import TECHNOLOGY_ENTITY_TYPES
from core.entities.entity import EnterpriseEntity, EntityRelationship
from repositories.entity_repository import EntityRepository
from repositories.technology_twin_repository import TechnologyTwinRepository


class TechnologyTwinService:
    def __init__(
        self,
        entity_repository: EntityRepository | None = None,
        twin_repository: TechnologyTwinRepository | None = None,
    ):
        self.entity_repository = entity_repository or EntityRepository()
        self.twin_repository = twin_repository or TechnologyTwinRepository()

    def build_technology_twin(self, organization_id: UUID | str, persist: bool = True) -> TechnologyTwin:
        resolved_id = UUID(str(organization_id))
        entities = [
            entity
            for entity in self.entity_repository.get_entities()
            if entity.organization_id == resolved_id
        ]
        relationships = [
            relationship
            for relationship in self.entity_repository.get_relationships()
            if self._relationship_belongs_to_org(relationship, entities)
        ]
        twin = TechnologyTwin.build(resolved_id, entities, relationships)
        return self.twin_repository.save(twin) if persist else twin

    def refresh_technology_twin(self, organization_id: UUID | str) -> TechnologyTwin:
        return self.build_technology_twin(organization_id, persist=True)

    def get_latest_technology_twin(self, organization_id: UUID | str) -> TechnologyTwin | None:
        return self.twin_repository.latest_for_organization(organization_id)

    def technology_context(self, organization_id: UUID | str, technology_id: UUID | str) -> dict:
        twin = self.get_latest_technology_twin(organization_id) or self.build_technology_twin(organization_id)
        return twin.technology_context(technology_id)

    def technology_portfolio(self, organization_id: UUID | str) -> list[dict]:
        twin = self.get_latest_technology_twin(organization_id) or self.build_technology_twin(organization_id)
        return [
            {
                "technology_id": str(node.technology_id),
                "name": node.name,
                "technology_type": node.technology_type,
                "vendor": node.vendor,
                "cloud_provider": node.cloud_provider,
                "environment": node.environment,
                "region": node.region,
                "status": node.status,
                "health": node.state.health_score if node.state else 100.0,
                "risk": node.risk,
                "monthly_cost": node.monthly_cost,
                "applications": len(node.application_ids),
                "business_services": len(node.business_service_ids),
            }
            for node in sorted(twin.nodes.values(), key=lambda item: (item.technology_type, item.name.lower()))
        ]

    def graph(self, organization_id: UUID | str) -> dict:
        twin = self.get_latest_technology_twin(organization_id) or self.build_technology_twin(organization_id)
        return twin.graph()

    def attach_infrastructure_resource(
        self,
        organization_id: UUID | str,
        technology_id: UUID | str,
        resource: InfrastructureResource,
        relationship_type: str = "RUNS_ON",
    ) -> TechnologyTwin:
        twin = self.get_latest_technology_twin(organization_id) or self.build_technology_twin(organization_id)
        node = twin.nodes.get(UUID(str(technology_id)))
        if not node:
            raise KeyError(f"Technology twin node not found: {technology_id}")
        node.attach_infrastructure_resource(resource, relationship_type=relationship_type)
        twin.refresh()
        return self.twin_repository.save(twin)

    def get_infrastructure_layer(
        self,
        organization_id: UUID | str,
        technology_id: UUID | str,
    ) -> InfrastructureLayer:
        twin = self.get_latest_technology_twin(organization_id) or self.build_technology_twin(organization_id)
        node = twin.nodes.get(UUID(str(technology_id)))
        if not node:
            raise KeyError(f"Technology twin node not found: {technology_id}")
        if node.infrastructure_layer is None:
            node.infrastructure_layer = InfrastructureLayer(node.technology_id)
        return node.infrastructure_layer

    def map_resource_to_technology(
        self,
        organization_id: UUID | str,
        technology_id: UUID | str,
        resource_entity_id: UUID | str,
        relationship_type: str = "RUNS_ON",
    ) -> TechnologyTwin:
        entity = self.entity_repository.get_entity(resource_entity_id)
        if not entity:
            raise KeyError(f"Infrastructure resource entity not found: {resource_entity_id}")
        return self.attach_infrastructure_resource(
            organization_id,
            technology_id,
            InfrastructureResource.from_entity(entity),
            relationship_type=relationship_type,
        )

    def calculate_infrastructure_health(self, organization_id: UUID | str, technology_id: UUID | str) -> float:
        layer = self.get_infrastructure_layer(organization_id, technology_id)
        layer.refresh()
        return layer.health_score

    def calculate_infrastructure_cost(self, organization_id: UUID | str, technology_id: UUID | str) -> float:
        layer = self.get_infrastructure_layer(organization_id, technology_id)
        layer.refresh()
        return layer.cost

    def _relationship_belongs_to_org(
        self,
        relationship: EntityRelationship,
        entities: list[EnterpriseEntity],
    ) -> bool:
        entity_ids = {entity.id for entity in entities}
        return relationship.source_entity_id in entity_ids or relationship.target_entity_id in entity_ids

    def technology_entities(self, organization_id: UUID | str) -> list[EnterpriseEntity]:
        resolved_id = UUID(str(organization_id))
        return [
            entity
            for entity in self.entity_repository.get_entities()
            if entity.organization_id == resolved_id and entity.entity_type in TECHNOLOGY_ENTITY_TYPES
        ]
