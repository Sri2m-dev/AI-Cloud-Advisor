"""Business Service Registry orchestration over released P3 interfaces."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from typing import Any, Mapping

from data_fabric.contracts import (
    EnterpriseEntity,
    EnterpriseRelationship,
    EntityType,
    EntityVersion,
    RelationshipType,
)
from data_fabric.foundation import TenantContext
from data_fabric.registry.interfaces import RelationshipRegistry
from data_fabric.semantic.interfaces import OntologyRegistry
from enterprise_registry.exceptions import (
    BusinessServiceRelationshipError,
    BusinessServiceValidationError,
)
from enterprise_registry.models import (
    LIFECYCLE_TRANSITIONS,
    BusinessCriticality,
    BusinessService,
    BusinessServiceLifecycle,
    BusinessServiceType,
)
from enterprise_registry.repository import BusinessServiceRepository

ALLOWED_RELATIONSHIPS: Mapping[
    EntityType,
    frozenset[RelationshipType],
] = {
    EntityType.APPLICATION: frozenset(
        {
            RelationshipType.DEPENDS_ON,
            RelationshipType.ASSOCIATED_WITH,
        }
    ),
    EntityType.TECHNOLOGY: frozenset(
        {
            RelationshipType.DEPENDS_ON,
            RelationshipType.RUNS_ON,
            RelationshipType.ASSOCIATED_WITH,
        }
    ),
    EntityType.OWNER: frozenset({RelationshipType.OWNED_BY}),
    EntityType.DEPARTMENT: frozenset({RelationshipType.ASSOCIATED_WITH}),
    EntityType.COST_CENTER: frozenset(
        {
            RelationshipType.FUNDS,
            RelationshipType.ASSOCIATED_WITH,
        }
    ),
}


class BusinessServiceRegistry:
    """Tenant-bound application service for WP-006 Phase 1."""

    def __init__(
        self,
        context: TenantContext,
        repository: BusinessServiceRepository,
        *,
        ontology: OntologyRegistry | None = None,
        relationships: RelationshipRegistry | None = None,
    ) -> None:
        self.context = context
        self.repository = repository
        self.ontology = ontology
        self.relationships = relationships

    def register(self, service: BusinessService) -> BusinessService:
        self.context.assert_record_matches(service, "business_service")
        self._validate_domain(service.business_domain)
        return self.repository.register(self.context, service)

    def get_by_canonical_id(
        self,
        canonical_id: str,
        *,
        include_inactive: bool = False,
    ) -> BusinessService:
        return self.repository.get_by_canonical_id(
            self.context,
            canonical_id,
            include_inactive=include_inactive,
        )

    def get_by_business_service_id(
        self,
        business_service_id: str,
        *,
        include_inactive: bool = False,
    ) -> BusinessService:
        return self.repository.get_by_business_service_id(
            self.context,
            business_service_id,
            include_inactive=include_inactive,
        )

    def resolve_alias(
        self,
        alias: str,
        *,
        include_inactive: bool = False,
    ) -> BusinessService:
        return self.repository.resolve_alias(
            self.context,
            alias,
            include_inactive=include_inactive,
        )

    def list_services(
        self,
        *,
        business_domain: str | None = None,
        include_inactive: bool = False,
    ) -> list[BusinessService]:
        return self.repository.list_services(
            self.context,
            business_domain=business_domain,
            include_inactive=include_inactive,
        )

    def update_metadata(
        self,
        canonical_id: str,
        *,
        expected_version: int,
        name: str | None = None,
        description: str | None = None,
        business_domain: str | None = None,
        service_type: BusinessServiceType | str | None = None,
        criticality: BusinessCriticality | str | None = None,
        attributes: Mapping[str, Any] | None = None,
    ) -> BusinessService:
        current = self.get_by_canonical_id(canonical_id, include_inactive=True)
        resolved_domain = (
            str(business_domain).strip()
            if business_domain is not None
            else current.business_domain
        )
        self._validate_domain(resolved_domain)
        resolved_type = (
            BusinessServiceType(service_type)
            if service_type is not None
            else current.service_type
        )
        resolved_criticality = (
            BusinessCriticality(criticality)
            if criticality is not None
            else current.criticality
        )
        updated_entity = self._updated_entity(
            current,
            expected_version,
            name=current.name if name is None else str(name).strip(),
            metadata_updates={
                "business_domain": resolved_domain,
                "criticality": resolved_criticality.value,
                "service_type": resolved_type.value,
            },
        )
        updated = replace(
            current,
            entity=updated_entity,
            description=current.description
            if description is None
            else str(description).strip(),
            business_domain=resolved_domain,
            service_type=resolved_type,
            criticality=resolved_criticality,
            attributes=current.attributes if attributes is None else attributes,
        )
        return self.repository.update(
            self.context,
            updated,
            expected_version=expected_version,
        )

    def transition_lifecycle(
        self,
        canonical_id: str,
        target: BusinessServiceLifecycle | str,
        *,
        expected_version: int,
    ) -> BusinessService:
        current = self.get_by_canonical_id(canonical_id, include_inactive=True)
        target_state = BusinessServiceLifecycle(target)
        if target_state not in LIFECYCLE_TRANSITIONS[current.lifecycle_state]:
            raise BusinessServiceValidationError(
                f"unsupported lifecycle transition: {current.lifecycle_state} -> {target_state}"
            )
        updated_entity = self._updated_entity(
            current,
            expected_version,
            metadata_updates={
                "active": target_state
                not in {
                    BusinessServiceLifecycle.RETIRED,
                    BusinessServiceLifecycle.ARCHIVED,
                },
                "lifecycle_state": target_state.value,
            },
        )
        updated = replace(
            current,
            entity=updated_entity,
            lifecycle_state=target_state,
        )
        return self.repository.update(
            self.context,
            updated,
            expected_version=expected_version,
        )

    def register_relationship(
        self,
        relationship: EnterpriseRelationship,
        *,
        target: EnterpriseEntity,
    ) -> EnterpriseRelationship:
        if self.relationships is None:
            raise BusinessServiceRelationshipError(
                "relationship registry is not configured"
            )
        self.context.assert_record_matches(relationship, "relationship")
        self.context.assert_record_matches(target, "relationship target")
        service = self.get_by_canonical_id(relationship.source_entity_id)
        if relationship.source_entity_id != service.canonical_id:
            raise BusinessServiceRelationshipError(
                "relationship source must be a registered business service"
            )
        if relationship.target_entity_id not in {target.id, target.canonical_id}:
            raise BusinessServiceRelationshipError(
                "relationship target identity is inconsistent"
            )
        allowed = ALLOWED_RELATIONSHIPS.get(target.entity_type, frozenset())
        if relationship.relationship_type not in allowed:
            raise BusinessServiceRelationshipError(
                "relationship type is not supported for the target entity type"
            )
        return self.relationships.register_relationship(relationship)

    def list_relationships(
        self,
        canonical_id: str,
        *,
        include_inactive: bool = False,
    ) -> list[EnterpriseRelationship]:
        if self.relationships is None:
            return []
        self.get_by_canonical_id(canonical_id, include_inactive=include_inactive)
        relationships = self.relationships.search_relationships(
            source_entity_id=canonical_id,
            organization_id=self.context.organization_id,
            include_inactive=include_inactive,
        )
        return [
            relationship
            for relationship in relationships
            if relationship.tenant_id == self.context.tenant_id
        ]

    def _validate_domain(self, business_domain: str) -> None:
        domain = str(business_domain).strip()
        if not domain:
            raise BusinessServiceValidationError("business_domain is required")
        if self.ontology is None:
            return
        concept = self.ontology.get_concept(
            domain,
            organization_id=self.context.organization_id,
            tenant_id=self.context.tenant_id,
        ) or self.ontology.find_by_canonical_name(
            domain,
            organization_id=self.context.organization_id,
            tenant_id=self.context.tenant_id,
        )
        if concept is None or not concept.active:
            raise BusinessServiceValidationError(
                "business_domain is not compatible with the active tenant ontology"
            )
        if concept.concept_type not in {"capability", "business_service"}:
            raise BusinessServiceValidationError(
                "business_domain ontology concept must be a capability or business_service"
            )

    @staticmethod
    def _updated_entity(
        current: BusinessService,
        expected_version: int,
        *,
        name: str | None = None,
        metadata_updates: Mapping[str, Any] | None = None,
    ) -> EnterpriseEntity:
        if current.version != expected_version:
            raise BusinessServiceValidationError(
                f"expected version {expected_version}, found {current.version}"
            )
        timestamp = datetime.now(timezone.utc)
        metadata = dict(current.entity.metadata)
        metadata.update(metadata_updates or {})
        return replace(
            current.entity,
            name=current.name if name is None else name,
            updated_at=timestamp,
            version=expected_version + 1,
            metadata=metadata,
            entity_version=EntityVersion(
                version=expected_version + 1,
                effective_from=timestamp,
                supersedes_version=expected_version,
            ),
        )
