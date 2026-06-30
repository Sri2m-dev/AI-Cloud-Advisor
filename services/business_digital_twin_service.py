from __future__ import annotations

from uuid import UUID

from core.digital_twin.business_twin import BusinessTwin, BusinessTwinLevel
from core.entities.entity import EnterpriseEntity, EntityRelationship, EntityType
from repositories.business_digital_twin_repository import BusinessDigitalTwinRepository
from repositories.entity_repository import EntityRepository


class BusinessDigitalTwinService:
    def __init__(
        self,
        entity_repository: EntityRepository | None = None,
        twin_repository: BusinessDigitalTwinRepository | None = None,
    ):
        self.entity_repository = entity_repository or EntityRepository()
        self.twin_repository = twin_repository or BusinessDigitalTwinRepository()

    def build_business_twin(self, organization_id: UUID | str, persist: bool = True) -> BusinessTwin:
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
        twin = BusinessTwin.build(resolved_id, entities, relationships)
        return self.twin_repository.save(twin) if persist else twin

    def get_latest_business_twin(self, organization_id: UUID | str) -> BusinessTwin | None:
        return self.twin_repository.latest_for_organization(organization_id)

    def explore_entity(self, organization_id: UUID | str, entity_id: UUID | str) -> dict:
        twin = self._latest_or_build(organization_id)
        return twin.entity_context(entity_id)

    def capability_services(self, organization_id: UUID | str, capability_id: UUID | str) -> list[dict]:
        twin = self._latest_or_build(organization_id)
        return [node.to_dict() for node in twin.business_services_for_capability(capability_id)]

    def service_applications(self, organization_id: UUID | str, service_id: UUID | str) -> list[dict]:
        twin = self._latest_or_build(organization_id)
        return [node.to_dict() for node in twin.applications_for_service(service_id)]

    def service_operating_context(self, organization_id: UUID | str, service_id: UUID | str) -> dict:
        twin = self._latest_or_build(organization_id)
        context = twin.entity_context(service_id)
        context["question_answers"] = {
            "which_applications_underpin_this_service": context["applications"],
            "who_owns_them": self._owners_for_nodes(twin, service_id),
            "what_is_the_associated_spend": context["total_cost"],
            "what_risks_are_inherited": context["inherited_risks"],
            "what_technologies_are_involved": context["technologies"],
        }
        return context

    def hierarchy(self, organization_id: UUID | str) -> dict:
        twin = self._latest_or_build(organization_id)
        roots = [
            node
            for node in twin.nodes.values()
            if node.level == BusinessTwinLevel.ORGANIZATION.value or not node.parent_entity_id
        ]
        return {
            "twin_id": str(twin.id),
            "organization_id": str(twin.organization_id),
            "metadata": twin.metadata,
            "roots": [self._serialize_tree(twin, root.entity_id) for root in roots],
        }

    def _latest_or_build(self, organization_id: UUID | str) -> BusinessTwin:
        return self.get_latest_business_twin(organization_id) or self.build_business_twin(organization_id)

    def _relationship_belongs_to_org(
        self,
        relationship: EntityRelationship,
        entities: list[EnterpriseEntity],
    ) -> bool:
        entity_ids = {entity.id for entity in entities}
        return relationship.source_entity_id in entity_ids or relationship.target_entity_id in entity_ids

    def _owners_for_nodes(self, twin: BusinessTwin, entity_id: UUID | str) -> list[str]:
        owner_ids = {
            str(node.owner_id)
            for node in [twin.nodes[UUID(str(entity_id))], *twin.descendants(entity_id)]
            if node.owner_id
        }
        return sorted(owner_ids)

    def _serialize_tree(self, twin: BusinessTwin, entity_id: UUID | str) -> dict:
        node = twin.nodes[UUID(str(entity_id))]
        payload = node.to_dict()
        payload["children"] = [
            self._serialize_tree(twin, child.entity_id)
            for child in twin.children_of(entity_id)
            if child.entity_type in {
                EntityType.BUSINESS_UNIT.value,
                EntityType.DEPARTMENT.value,
                EntityType.BUSINESS_CAPABILITY.value,
                EntityType.BUSINESS_SERVICE.value,
                EntityType.APPLICATION.value,
            }
        ]
        return payload
