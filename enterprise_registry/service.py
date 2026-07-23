"""Business Service Registry orchestration over released P3 interfaces."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from typing import Any, Mapping

from data_fabric.contracts import (
    EnterpriseEntity,
    EnterpriseRelationship,
    EntityOwnership,
    EntityType,
    EntityVersion,
    RelationshipType,
)
from data_fabric.foundation import TenantContext
from data_fabric.lineage import (
    LineageEvent,
    LineageTracker,
    ProvenanceRecord,
    ProvenanceTracker,
)
from data_fabric.quality import DataQualityEvaluator, QualityAssessment
from data_fabric.registry.interfaces import RelationshipRegistry
from data_fabric.semantic.interfaces import OntologyRegistry
from data_fabric.versioning import EntitySnapshot, VersionStore
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
    EntityType.BUSINESS_CAPABILITY: frozenset(
        {RelationshipType.ASSOCIATED_WITH}
    ),
}


class BusinessServiceRegistry:
    """Tenant-bound application service for the WP-006 registry."""

    def __init__(
        self,
        context: TenantContext,
        repository: BusinessServiceRepository,
        *,
        ontology: OntologyRegistry | None = None,
        relationships: RelationshipRegistry | None = None,
        versions: VersionStore | None = None,
        lineage: LineageTracker | None = None,
        provenance: ProvenanceTracker | None = None,
        quality: DataQualityEvaluator | None = None,
    ) -> None:
        self.context = context
        self.repository = repository
        self.ontology = ontology
        self.relationships = relationships
        self.versions = versions
        self.lineage = lineage
        self.provenance = provenance
        self.quality = quality

    def register(self, service: BusinessService) -> BusinessService:
        self.context.assert_record_matches(service, "business_service")
        self._validate_ontology(service)
        registered = self.repository.register(self.context, service)
        self._record_entity_integrations(registered, operation="register")
        return registered

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
        self._validate_ontology(updated)
        stored = self.repository.update(
            self.context,
            updated,
            expected_version=expected_version,
        )
        self._record_entity_integrations(stored, operation="metadata_update")
        return stored

    def assign_owner(
        self,
        canonical_id: str,
        *,
        owner_id: str,
        expected_version: int,
        owner_name: str | None = None,
        owner_email: str | None = None,
        department_id: str | None = None,
        department_name: str | None = None,
        cost_center_id: str | None = None,
        accountability: str | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> BusinessService:
        """Assign canonical ownership and preserve the change as a new version."""

        if not str(owner_id).strip():
            raise BusinessServiceValidationError("owner_id is required")
        current = self.get_by_canonical_id(canonical_id, include_inactive=True)
        ownership = EntityOwnership(
            owner_id=str(owner_id).strip(),
            owner_name=owner_name,
            owner_email=owner_email,
            department_id=department_id,
            department_name=department_name,
            cost_center_id=cost_center_id,
            accountability=accountability,
            metadata=dict(metadata or {}),
        )
        updated = replace(
            current,
            entity=replace(
                self._updated_entity(
                    current,
                    expected_version,
                    metadata_updates={"owner_id": ownership.owner_id},
                ),
                ownership=ownership,
            ),
        )
        stored = self.repository.update(
            self.context,
            updated,
            expected_version=expected_version,
        )
        self._record_entity_integrations(stored, operation="ownership_update")
        return stored

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
        stored = self.repository.update(
            self.context,
            updated,
            expected_version=expected_version,
        )
        self._record_entity_integrations(stored, operation="lifecycle_update")
        return stored

    def activate(self, canonical_id: str, *, expected_version: int) -> BusinessService:
        return self.transition_lifecycle(
            canonical_id,
            BusinessServiceLifecycle.ACTIVE,
            expected_version=expected_version,
        )

    def deactivate(self, canonical_id: str, *, expected_version: int) -> BusinessService:
        return self.transition_lifecycle(
            canonical_id,
            BusinessServiceLifecycle.SUSPENDED,
            expected_version=expected_version,
        )

    def archive(self, canonical_id: str, *, expected_version: int) -> BusinessService:
        return self.transition_lifecycle(
            canonical_id,
            BusinessServiceLifecycle.ARCHIVED,
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
        self._validate_relationship_ontology(
            service,
            relationship,
            target=target,
        )
        stored = self.relationships.register_relationship(relationship)
        if self.versions is not None:
            self.versions.create_relationship_snapshot(stored)
        if self.lineage is not None:
            self.lineage.record_relationship_event(
                LineageEvent(
                    id=f"{stored.id}:lineage:v{stored.version}",
                    event_type="relationship",
                    source_system=stored.source_system or service.source_system,
                    source_identifier=stored.source_identifier or stored.id,
                    organization_id=self.context.organization_id,
                    tenant_id=self.context.tenant_id,
                    entity_id=service.canonical_id,
                    relationship_id=stored.id,
                )
            )
        if self.provenance is not None:
            self.provenance.record_provenance(
                ProvenanceRecord(
                    id=f"{stored.id}:provenance:v{stored.version}",
                    source_system=stored.source_system or service.source_system,
                    source_identifier=stored.source_identifier or stored.id,
                    organization_id=self.context.organization_id,
                    tenant_id=self.context.tenant_id,
                    relationship_id=stored.id,
                    collection_method="business_service_registry",
                )
            )
        return stored

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

    def list_versions(self, canonical_id: str) -> list[EntitySnapshot]:
        self.get_by_canonical_id(canonical_id, include_inactive=True)
        if self.versions is None:
            return []
        return self.versions.list_entity_versions(
            canonical_id,
            organization_id=self.context.organization_id,
            tenant_id=self.context.tenant_id,
        )

    def assess_quality(
        self,
        canonical_id: str,
        **evidence: Any,
    ) -> QualityAssessment:
        if self.quality is None:
            raise BusinessServiceValidationError("quality evaluator is not configured")
        service = self.get_by_canonical_id(canonical_id, include_inactive=True)
        return self.quality.evaluate_entity(service.entity, **evidence)

    def _validate_ontology(self, service: BusinessService) -> None:
        domain = str(service.business_domain).strip()
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
        allowed_types = concept.attributes.get("service_types")
        if allowed_types is not None and service.service_type.value not in {
            str(value) for value in allowed_types
        }:
            raise BusinessServiceValidationError(
                "service_type is not compatible with the business_domain ontology"
            )
        allowed_criticalities = concept.attributes.get("criticalities")
        if allowed_criticalities is not None and service.criticality.value not in {
            str(value) for value in allowed_criticalities
        }:
            raise BusinessServiceValidationError(
                "criticality is not compatible with the business_domain ontology"
            )

    def _record_entity_integrations(
        self,
        service: BusinessService,
        *,
        operation: str,
    ) -> None:
        if self.versions is not None:
            self.versions.create_entity_snapshot(
                service.entity,
                lineage_ref=f"{service.canonical_id}:lineage:v{service.version}",
                provenance_ref=f"{service.canonical_id}:provenance:v{service.version}",
            )
        if self.lineage is not None:
            self.lineage.record_canonicalization_event(
                LineageEvent(
                    id=f"{service.canonical_id}:lineage:v{service.version}",
                    event_type="canonicalization",
                    source_system=service.source_system,
                    source_identifier=service.source_id,
                    organization_id=self.context.organization_id,
                    tenant_id=self.context.tenant_id,
                    entity_id=service.canonical_id,
                    transformation_name=operation,
                    transformation_version=str(service.version),
                )
            )
        if self.provenance is not None:
            self.provenance.record_provenance(
                ProvenanceRecord(
                    id=f"{service.canonical_id}:provenance:v{service.version}",
                    source_system=service.source_system,
                    source_identifier=service.source_id,
                    organization_id=self.context.organization_id,
                    tenant_id=self.context.tenant_id,
                    entity_id=service.canonical_id,
                    collection_method="business_service_registry",
                    normalization_rule=operation,
                )
            )

    def _validate_relationship_ontology(
        self,
        service: BusinessService,
        relationship: EnterpriseRelationship,
        *,
        target: EnterpriseEntity,
    ) -> None:
        if self.ontology is None:
            return
        concept = self.ontology.get_concept(
            service.business_domain,
            organization_id=self.context.organization_id,
            tenant_id=self.context.tenant_id,
        ) or self.ontology.find_by_canonical_name(
            service.business_domain,
            organization_id=self.context.organization_id,
            tenant_id=self.context.tenant_id,
        )
        if concept is None:
            raise BusinessServiceRelationshipError(
                "business service ontology concept is not available"
            )
        semantics = concept.attributes.get("relationship_types")
        if semantics is None:
            return
        allowed = semantics.get(target.entity_type.value, ())
        if relationship.relationship_type.value not in {
            str(value) for value in allowed
        }:
            raise BusinessServiceRelationshipError(
                "relationship is not compatible with the business_domain ontology"
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
