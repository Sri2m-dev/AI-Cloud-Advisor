from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping
from uuid import NAMESPACE_URL, UUID, uuid5

from data_fabric.adapters.supabase.atomic_write import (
    AtomicEntityWriteRequest,
    AtomicRelationshipWriteRequest,
    SupabaseAtomicWriteExecutor,
)
from data_fabric.contracts import EnterpriseRelationship
from data_fabric.foundation import DefaultDeterministicSerializer, TenantContext
from data_fabric.persistence.mappers import (
    EntityPersistenceMapper,
    RelationshipPersistenceMapper,
)
from data_fabric.source_facts.models import FactType, LifecycleState, SourceFact
from enterprise_registry.canonical import enterprise_entity_from_source


@dataclass(frozen=True, slots=True)
class EntityProjectionRule:
    rule_id: str
    version: str
    source_system: str
    fact_type: FactType
    predicate: str
    entity_type: str
    source_identifier_field: str
    canonical_name_field: str
    metadata_fields: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        required = (
            self.rule_id,
            self.version,
            self.source_system,
            self.predicate,
            self.source_identifier_field,
            self.canonical_name_field,
        )
        if not all(str(value or "").strip() for value in required):
            raise ValueError("projection rule fields are required")
        object.__setattr__(self, "fact_type", FactType(self.fact_type))
        object.__setattr__(self, "metadata_fields", tuple(self.metadata_fields))


@dataclass(frozen=True, slots=True)
class RelationshipProjectionRule:
    rule_id: str
    version: str
    source_system: str
    fact_type: FactType
    predicate: str
    relationship_type: str

    def __post_init__(self) -> None:
        required = (
            self.rule_id,
            self.version,
            self.source_system,
            self.predicate,
            self.relationship_type,
        )
        if not all(str(value or "").strip() for value in required):
            raise ValueError("relationship projection rule fields are required")
        object.__setattr__(self, "fact_type", FactType(self.fact_type))


@dataclass(frozen=True, slots=True)
class EntityProjectionCandidate:
    source_fact: SourceFact
    rule_id: str


@dataclass(frozen=True, slots=True)
class RelationshipProjectionCandidate:
    source_fact: SourceFact
    rule_id: str
    relationship: EnterpriseRelationship


class GovernedCanonicalProjectionService:
    """Project only facts explicitly paired with a registered canonical rule."""

    def __init__(
        self,
        context: TenantContext,
        executor: SupabaseAtomicWriteExecutor,
        *,
        entity_rules: Mapping[str, EntityProjectionRule] | None = None,
        relationship_rules: Mapping[str, RelationshipProjectionRule] | None = None,
        entity_mapper: EntityPersistenceMapper | None = None,
        relationship_mapper: RelationshipPersistenceMapper | None = None,
    ) -> None:
        if not isinstance(context, TenantContext):
            raise TypeError("an explicit TenantContext is required")
        if executor is None:
            raise ValueError("an atomic canonical write executor is required")
        self.context = context
        self.executor = executor
        self.entity_rules = dict(entity_rules or {})
        self.relationship_rules = dict(relationship_rules or {})
        if any(key != rule.rule_id for key, rule in self.entity_rules.items()):
            raise ValueError("entity projection rule keys must match rule IDs")
        if any(key != rule.rule_id for key, rule in self.relationship_rules.items()):
            raise ValueError("relationship projection rule keys must match rule IDs")
        self.entity_mapper = entity_mapper or EntityPersistenceMapper()
        self.relationship_mapper = relationship_mapper or RelationshipPersistenceMapper()
        self.serializer = DefaultDeterministicSerializer()

    def project_entities(
        self, candidates: tuple[EntityProjectionCandidate, ...]
    ) -> tuple[object, ...]:
        results = []
        for candidate in candidates:
            fact = candidate.source_fact
            rule = self.entity_rules.get(candidate.rule_id)
            if rule is None:
                raise ValueError("SourceFact has no registered entity projection rule")
            self._validate_fact(fact, rule.source_system, rule.fact_type, rule.predicate)
            value = fact.value
            if not isinstance(value, dict):
                raise ValueError("projected SourceFact value must be a mapping")
            source_identifier = str(value.get(rule.source_identifier_field) or "").strip()
            canonical_name = str(value.get(rule.canonical_name_field) or "").strip()
            if not source_identifier or source_identifier != fact.subject_reference:
                raise ValueError("SourceFact source identity is missing or inconsistent")
            if not canonical_name:
                raise ValueError("SourceFact canonical name is required")
            metadata = {
                field: value[field]
                for field in rule.metadata_fields
                if field in value
            }
            entity = enterprise_entity_from_source(
                context=self.context,
                entity_type=rule.entity_type,
                source_system=fact.source_system,
                source_entity_id=source_identifier,
                canonical_name=canonical_name,
                display_name=canonical_name,
                valid_from=fact.observed_at,
                lineage_reference=fact.ingestion_run_id,
                provenance_reference=fact.source_fact_id,
                search_attributes=metadata,
            )
            entity.id = str(
                uuid5(
                    NAMESPACE_URL,
                    f"entity-record:{self.context.organization_id}:"
                    f"{self.context.tenant_id}:{entity.canonical_id}",
                )
            )
            if entity.identity is not None:
                entity.identity.id = entity.id
            entity.metadata.update(metadata)
            if entity.lineage is not None:
                entity.lineage.observed_at = fact.observed_at
                entity.lineage.metadata.update(
                    {
                        "source_fact_id": fact.source_fact_id,
                        "evidence_reference": fact.evidence_reference,
                        "ingestion_run_id": fact.ingestion_run_id,
                    }
                )
            if entity.provenance is not None:
                entity.provenance.captured_at = fact.observed_at
                entity.provenance.metadata.update(
                    {
                        "source_fact_id": fact.source_fact_id,
                        "evidence_reference": fact.evidence_reference,
                        "fact_version": fact.fact_version,
                        "projection_rule": rule.rule_id,
                        "projection_rule_version": rule.version,
                    }
                )
            record = self.entity_mapper.domain_to_record(entity, self.context)
            request = AtomicEntityWriteRequest(
                tenant_context=self.context,
                operation="create",
                entity_record=record,
                idempotency_key=self._idempotency_key(rule.rule_id, fact.source_fact_id),
                payload_hash=self.serializer.content_hash(entity),
                correlation_id=fact.ingestion_run_id,
                metadata={"projection_rule": rule.rule_id, "projection_rule_version": rule.version},
            )
            results.append(self.executor.execute_entity_write(request))
        return tuple(results)

    def project_relationships(
        self, candidates: tuple[RelationshipProjectionCandidate, ...]
    ) -> tuple[object, ...]:
        results = []
        for candidate in candidates:
            fact = candidate.source_fact
            rule = self.relationship_rules.get(candidate.rule_id)
            if rule is None:
                raise ValueError("SourceFact has no registered relationship projection rule")
            self._validate_fact(fact, rule.source_system, rule.fact_type, rule.predicate)
            relationship = candidate.relationship
            self.context.assert_record_matches(relationship, "relationship")
            if relationship.relationship_type.value != rule.relationship_type:
                raise ValueError("relationship does not match its registered projection rule")
            if not fact.object_reference:
                raise ValueError("relationship evidence requires an explicit object reference")
            try:
                UUID(relationship.source_entity_id)
                UUID(relationship.target_entity_id)
            except ValueError as exc:
                raise ValueError(
                    "relationship endpoints must be canonical entity record UUIDs"
                ) from exc
            if relationship.source_identifier != fact.source_record_id:
                raise ValueError("relationship source identifier does not match its SourceFact")
            relationship.id = str(
                uuid5(
                    NAMESPACE_URL,
                    f"relationship:{self.context.organization_id}:"
                    f"{self.context.tenant_id}:{rule.rule_id}:"
                    f"{relationship.source_entity_id}:{relationship.relationship_type.value}:"
                    f"{relationship.target_entity_id}",
                )
            )
            relationship.created_at = fact.observed_at
            relationship.updated_at = fact.observed_at
            relationship.evidence = tuple(
                dict.fromkeys(
                    (*relationship.evidence, fact.source_fact_id, fact.evidence_reference)
                )
            )
            relationship.provenance_reference = fact.source_fact_id
            relationship.lineage_reference = fact.ingestion_run_id
            record = self.relationship_mapper.domain_to_record(relationship, self.context)
            request = AtomicRelationshipWriteRequest(
                tenant_context=self.context,
                operation="create",
                relationship_record=record,
                idempotency_key=self._idempotency_key(rule.rule_id, fact.source_fact_id),
                payload_hash=self.serializer.content_hash(relationship),
                correlation_id=fact.ingestion_run_id,
                metadata={"projection_rule": rule.rule_id, "projection_rule_version": rule.version},
            )
            results.append(self.executor.execute_relationship_write(request))
        return tuple(results)

    def _validate_fact(self, fact, source_system, fact_type, predicate) -> None:
        if not isinstance(fact, SourceFact):
            raise TypeError("canonical projection requires a persisted SourceFact")
        if (fact.organization_id, fact.tenant_id) != (
            self.context.organization_id,
            self.context.tenant_id,
        ):
            raise PermissionError("SourceFact crosses the canonical projection tenant boundary")
        if fact.lifecycle is not LifecycleState.ACTIVE:
            raise ValueError("inactive SourceFacts cannot be projected")
        if fact.source_system != source_system or fact.fact_type is not fact_type:
            raise ValueError("SourceFact does not match its registered projection rule")
        if fact.predicate != predicate:
            raise ValueError("SourceFact predicate does not match its registered projection rule")

    @staticmethod
    def _idempotency_key(rule_id: str, source_fact_id: str) -> str:
        import hashlib

        digest = hashlib.sha256(f"{rule_id}:{source_fact_id}".encode("utf-8")).hexdigest()
        return f"projection:{digest}"


def configured_supabase_atomic_executor():
    """Build the existing atomic writer only when a canonical write is requested."""
    import os

    from data_fabric.adapters.supabase import (
        DataFabricDatabaseConfig,
        SupabaseAtomicWriteExecutor,
        SupabaseDataFabricClient,
    )

    url = os.getenv("SUPABASE_URL", "").strip()
    service_key = (
        os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        or os.getenv("SUPABASE_SERVICE_KEY")
        or ""
    ).strip()
    if not url or not service_key:
        raise RuntimeError(
            "The server-side Data Fabric persistence credential is not configured."
        )
    config = DataFabricDatabaseConfig(url, service_key, enable_health_check=False)
    return SupabaseAtomicWriteExecutor(SupabaseDataFabricClient(config))
