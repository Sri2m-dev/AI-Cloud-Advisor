"""Tenant-scoped canonical Enterprise Registry facade over released P3 contracts."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, fields
from enum import Enum
from typing import Any, Protocol

from classification_engine.repository import ClassificationRepository
from data_fabric.contracts import EnterpriseEntity, EnterpriseRelationship, EntityType
from data_fabric.foundation import TenantContext
from data_fabric.identity import IdentityResolver, MatchCandidate, MatchResult
from data_fabric.lineage import LineageTracker, ProvenanceTracker
from data_fabric.registry import EntityNotFoundError, EntityRegistry, RelationshipRegistry
from data_fabric.versioning import VersionStore

READ_ROLES = frozenset(
    {"super_admin", "client_admin", "executive", "cio", "finance", "operations", "auditor"}
)
MUTATION_ROLES = frozenset({"super_admin", "client_admin", "operations"})
CLASSIFICATION_FIELDS = (
    "account_name",
    "business_unit",
    "department",
    "cost_center",
    "environment",
    "application",
    "business_service",
    "owner",
    "technical_owner",
    "finance_owner",
    "criticality",
)


def _classification_mapping(result) -> dict[str, Any]:
    if not hasattr(result, "__dataclass_fields__"):
        return dict(result)
    values = {}
    for item in fields(result):
        value = getattr(result, item.name)
        if isinstance(value, Enum):
            value = value.value
        elif isinstance(value, Mapping):
            value = dict(value)
        elif isinstance(value, tuple):
            value = list(value)
        values[item.name] = value
    return values


class FinancialContextProvider(Protocol):
    def get_financial_context(
        self, context: TenantContext, entity: EnterpriseEntity
    ) -> Mapping[str, Any]: ...


class EmptyFinancialContextProvider:
    def get_financial_context(self, context, entity):
        context.assert_record_matches(entity, "financial entity")
        return {}


@dataclass(frozen=True, slots=True)
class EnterpriseEntityDetail:
    entity: EnterpriseEntity
    relationships: tuple[EnterpriseRelationship, ...]
    classifications: tuple[Mapping[str, Any], ...]
    financial_context: Mapping[str, Any]
    lineage: Any
    provenance: Any
    versions: tuple[Any, ...]


class EnterpriseRegistryService:
    """Read and govern canonical identities without owning domain persistence."""

    def __init__(
        self,
        context: TenantContext,
        *,
        role: str,
        entities: EntityRegistry,
        identities: IdentityResolver,
        relationships: RelationshipRegistry,
        classifications: ClassificationRepository | None = None,
        financial: FinancialContextProvider | None = None,
        lineage: LineageTracker | None = None,
        provenance: ProvenanceTracker | None = None,
        versions: VersionStore | None = None,
        source_mode: str = "in_memory",
    ) -> None:
        if role not in READ_ROLES:
            raise PermissionError("enterprise registry read denied")
        self.context = context
        self.role = role
        self.entities = entities
        self.identities = identities
        self.relationships = relationships
        self.classifications = classifications
        self.financial = financial or EmptyFinancialContextProvider()
        self.lineage = lineage
        self.provenance = provenance
        self.versions = versions
        self.source_mode = str(source_mode).strip().lower()

    def register_entity(self, entity: EnterpriseEntity) -> EnterpriseEntity:
        if self.role not in MUTATION_ROLES:
            raise PermissionError("enterprise registry identity mutation denied")
        self.context.assert_record_matches(entity, "entity")
        registered = self.entities.register_entity(entity)
        self.identities.register_entity(registered)
        if self.versions is not None:
            self.versions.create_entity_snapshot(
                registered,
                lineage_ref=registered.lineage_reference,
                provenance_ref=registered.provenance_reference,
            )
        return registered

    def register_entities(self, entities: Iterable[EnterpriseEntity]):
        return tuple(self.register_entity(entity) for entity in entities)

    def reconcile_identity(self, candidate: MatchCandidate) -> MatchResult:
        self.context.assert_record_matches(candidate, "identity candidate")
        result = self.identities.detect_duplicates(candidate)
        for entity in result.matched_entities:
            self.context.assert_record_matches(entity, "identity match")
        if result.matched_entity is not None:
            self.context.assert_record_matches(result.matched_entity, "identity match")
        return result

    def get_entity(self, canonical_id: str) -> EnterpriseEntity:
        entity = self.entities.find_entity_by_canonical_id(canonical_id)
        if entity is None:
            raise EntityNotFoundError(f"Entity not found: {canonical_id}")
        self.context.assert_record_matches(entity, "entity")
        return entity

    def list_entities(self, *, entity_type: EntityType | str | None = None):
        resolved = EntityType(entity_type).value if entity_type is not None else None
        rows = self.entities.search_entities(
            entity_type=resolved,
            organization_id=self.context.organization_id,
        )
        return tuple(
            sorted(
                (row for row in rows if row.tenant_id == self.context.tenant_id),
                key=lambda row: row.canonical_id,
            )
        )

    def search_entities(self, query: str = "", *, entity_type=None, limit: int = 100):
        wanted = str(query or "").strip().casefold()
        matches = []
        for entity in self.list_entities(entity_type=entity_type):
            identity_aliases = entity.identity.aliases if entity.identity else []
            search_values = [
                entity.canonical_id,
                entity.canonical_name,
                entity.display_name,
                entity.source_identifier,
                entity.source_system,
                *identity_aliases,
                *(entity.metadata.get("search") or {}).values(),
            ]
            if not wanted or any(wanted in str(value or "").casefold() for value in search_values):
                matches.append(entity)
        return tuple(matches[: max(0, int(limit))])

    def get_relationships(self, canonical_id: str):
        entity = self.get_entity(canonical_id)
        rows = self.relationships.search_relationships(
            organization_id=self.context.organization_id,
            include_inactive=False,
        )
        return tuple(
            row
            for row in rows
            if row.tenant_id == self.context.tenant_id
            and entity.id in (row.source_entity_id, row.target_entity_id)
        )

    def get_classifications(self, canonical_id: str):
        entity = self.get_entity(canonical_id)
        if self.classifications is None:
            return ()
        results = []
        domain_id = entity.source_identifier
        for field_name in CLASSIFICATION_FIELDS:
            result = self.classifications.current(
                self.context, entity.entity_type.value, domain_id, field_name
            )
            if result is None and entity.entity_type is EntityType.CLOUD_ACCOUNT:
                result = self.classifications.current(
                    self.context, "cloud_account", domain_id, field_name
                )
            if result is not None:
                results.append(_classification_mapping(result))
        return tuple(results)

    def get_financial_context(self, canonical_id: str):
        entity = self.get_entity(canonical_id)
        return dict(self.financial.get_financial_context(self.context, entity))

    def get_lineage(self, canonical_id: str):
        entity = self.get_entity(canonical_id)
        if self.lineage is not None:
            return self.lineage.trace_lineage_by_entity_id(entity.id)
        return entity.lineage

    def get_provenance(self, canonical_id: str):
        entity = self.get_entity(canonical_id)
        if self.provenance is not None:
            return self.provenance.trace_provenance_by_source(
                entity.source_system, entity.source_identifier
            )
        return entity.provenance

    def get_versions(self, canonical_id: str):
        entity = self.get_entity(canonical_id)
        if self.versions is None:
            return (entity.entity_version,) if entity.entity_version else ()
        return tuple(
            self.versions.list_entity_versions(
                entity.id,
                organization_id=self.context.organization_id,
                tenant_id=self.context.tenant_id,
            )
        )

    def get_detail(self, canonical_id: str) -> EnterpriseEntityDetail:
        return EnterpriseEntityDetail(
            entity=self.get_entity(canonical_id),
            relationships=self.get_relationships(canonical_id),
            classifications=self.get_classifications(canonical_id),
            financial_context=self.get_financial_context(canonical_id),
            lineage=self.get_lineage(canonical_id),
            provenance=self.get_provenance(canonical_id),
            versions=self.get_versions(canonical_id),
        )
