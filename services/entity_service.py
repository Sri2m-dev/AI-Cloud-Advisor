from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID

from core.entities.entity import (
    EnterpriseEntity,
    EntityRelationship,
    EntityType,
    LifecycleState,
)
from repositories.entity_repository import EntityRepository
from services.ontology_service import OntologyService


@dataclass(slots=True)
class EntityQualityMetrics:
    total_entities: int
    duplicate_candidates: int
    orphan_entities: int
    missing_owners: int
    missing_relationships: int
    stale_records: int
    sync_health: float
    source_coverage: float

    def to_dict(self) -> dict[str, int | float]:
        return {
            "total_entities": self.total_entities,
            "duplicate_candidates": self.duplicate_candidates,
            "orphan_entities": self.orphan_entities,
            "missing_owners": self.missing_owners,
            "missing_relationships": self.missing_relationships,
            "stale_records": self.stale_records,
            "sync_health": self.sync_health,
            "source_coverage": self.source_coverage,
        }


class EntityService:
    def __init__(
        self,
        repository: EntityRepository | None = None,
        ontology_service: OntologyService | None = None,
    ):
        self.repository = repository or EntityRepository()
        self.ontology_service = ontology_service or OntologyService()

    def validate(self, entity: EnterpriseEntity) -> list[str]:
        errors = []
        if not entity.display_name.strip():
            errors.append("display_name is required")
        if not entity.organization_id:
            errors.append("organization_id is required")
        if entity.lifecycle_state not in {state.value for state in LifecycleState}:
            errors.append(f"unsupported lifecycle_state: {entity.lifecycle_state}")
        if entity.entity_type not in {entity_type.value for entity_type in EntityType}:
            errors.append(f"unsupported entity_type: {entity.entity_type}")
        return errors

    def save(self, entity: EnterpriseEntity) -> EnterpriseEntity:
        errors = self.validate(entity)
        if errors:
            raise ValueError("; ".join(errors))
        return self.repository.save(self.canonicalize(entity))

    def canonicalize(self, entity: EnterpriseEntity) -> EnterpriseEntity:
        entity.display_name = " ".join(entity.display_name.split())
        entity.tags = {str(key).strip().lower(): str(value).strip() for key, value in entity.tags.items()}
        entity.metadata.setdefault("canonicalized_at", datetime.now(timezone.utc).isoformat(timespec="seconds"))
        return entity

    def find_duplicate_candidates(self) -> list[tuple[EnterpriseEntity, EnterpriseEntity, str]]:
        candidates = []
        seen_by_name: dict[tuple[str, str, UUID], EnterpriseEntity] = {}
        for entity in self.repository.get_entities():
            name_key = (entity.entity_type, entity.display_name.strip().lower(), entity.organization_id)
            if name_key in seen_by_name:
                candidates.append((seen_by_name[name_key], entity, "same entity type and display name"))
            else:
                seen_by_name[name_key] = entity

            for reference in entity.source_systems:
                source_match = self.repository.find_by_source(reference.system, reference.external_id)
                if source_match and source_match.id != entity.id:
                    candidates.append((source_match, entity, f"same {reference.system} source identity"))
        return candidates

    def set_owner(self, entity_id: UUID | str, owner_id: UUID | str | None) -> EnterpriseEntity:
        entity = self._get_required(entity_id)
        entity.owner_id = UUID(str(owner_id)) if owner_id else None
        return self.repository.update(entity)

    def transition_lifecycle(self, entity_id: UUID | str, lifecycle_state: str) -> EnterpriseEntity:
        if lifecycle_state not in {state.value for state in LifecycleState}:
            raise ValueError(f"Unsupported lifecycle state: {lifecycle_state}")
        entity = self._get_required(entity_id)
        entity.lifecycle_state = lifecycle_state
        return self.repository.update(entity)

    def enrich_metadata(self, entity_id: UUID | str, metadata: dict) -> EnterpriseEntity:
        entity = self._get_required(entity_id)
        entity.metadata.update(metadata)
        return self.repository.update(entity)

    def add_relationship(
        self,
        source_entity_id: UUID | str,
        relationship_type: str,
        target_entity_id: UUID | str,
        confidence: float = 1.0,
        source_system: str = "manual",
        created_by: UUID | str | None = None,
        verification_method: str = "unverified",
        status: str | None = None,
        strength: str | None = None,
        metadata: dict | None = None,
    ) -> EntityRelationship:
        source_entity = self._get_required(source_entity_id)
        target_entity = self._get_required(target_entity_id)
        validation = self.ontology_service.require_valid_relationship(
            relationship_type,
            source_entity.entity_type,
            target_entity.entity_type,
        )
        self.ontology_service.require_cardinality_allows(
            relationship_type,
            source_entity.entity_type,
            target_entity.entity_type,
            existing_targets_for_source=self._count_relationship_targets(source_entity.id, relationship_type),
            existing_sources_for_target=self._count_relationship_sources(target_entity.id, relationship_type),
            same_relationship_exists=self._relationship_exists(source_entity.id, relationship_type, target_entity.id),
        )
        semantics = self.ontology_service.relationship_semantics(
            relationship_type,
            source_entity.entity_type,
            target_entity.entity_type,
        )
        return self.repository.add_relationship(
            EntityRelationship(
                source_entity_id=UUID(str(source_entity_id)),
                relationship_type=relationship_type,
                target_entity_id=UUID(str(target_entity_id)),
                confidence_score=confidence,
                source_system=source_system,
                created_by=UUID(str(created_by)) if created_by else None,
                last_verified=datetime.now(timezone.utc).isoformat(timespec="seconds") if verification_method != "unverified" else None,
                verification_method=verification_method,
                status=status or ("Active" if verification_method != "unverified" else "Pending"),
                strength=strength or (validation.default_strength or semantics.get("default_strength") or "Medium"),
                direction=validation.direction or semantics.get("direction") or "Forward",
                ontology_version=validation.ontology_version or semantics.get("ontology_version") or "1.2.1",
                metadata={
                    **(metadata or {}),
                    "relationship_group": semantics.get("relationship_group"),
                    "cardinality": validation.cardinality or semantics.get("cardinality"),
                },
            )
        )

    def source_system_summary(self) -> dict[str, int]:
        counts: Counter[str] = Counter()
        for entity in self.repository.get_entities():
            for reference in entity.source_systems:
                counts[reference.system] += 1
        return dict(sorted(counts.items()))

    def entity_type_summary(self) -> dict[str, int]:
        counts = Counter(entity.entity_type for entity in self.repository.get_entities())
        return dict(sorted(counts.items()))

    def quality_metrics(self, stale_after_days: int = 30) -> EntityQualityMetrics:
        entities = self.repository.get_entities()
        relationships = self.repository.get_relationships()
        related_ids = {
            relationship.source_entity_id for relationship in relationships
        } | {
            relationship.target_entity_id for relationship in relationships
        }

        duplicate_count = len(self.find_duplicate_candidates())
        missing_owners = sum(1 for entity in entities if not entity.owner_id)
        missing_relationships = sum(1 for entity in entities if entity.id not in related_ids)
        orphan_entities = sum(
            1
            for entity in entities
            if entity.entity_type not in {EntityType.ORGANIZATION.value, EntityType.USER.value}
            and entity.id not in related_ids
        )
        stale_records = sum(1 for entity in entities if self._age_days(entity.updated_at) > stale_after_days)
        with_sources = sum(1 for entity in entities if entity.source_systems)
        total = len(entities)
        source_coverage = round((with_sources / total) * 100, 2) if total else 100.0
        quality_penalty = duplicate_count + missing_owners + orphan_entities + stale_records
        sync_health = round(max(0, 100 - (quality_penalty / max(total, 1)) * 10), 2)

        return EntityQualityMetrics(
            total_entities=total,
            duplicate_candidates=duplicate_count,
            orphan_entities=orphan_entities,
            missing_owners=missing_owners,
            missing_relationships=missing_relationships,
            stale_records=stale_records,
            sync_health=sync_health,
            source_coverage=source_coverage,
        )

    def recent_changes(self, limit: int = 10) -> list[EnterpriseEntity]:
        return sorted(
            self.repository.get_entities(),
            key=lambda entity: entity.updated_at,
            reverse=True,
        )[:limit]

    def _get_required(self, entity_id: UUID | str) -> EnterpriseEntity:
        entity = self.repository.get_entity(entity_id)
        if not entity:
            raise KeyError(f"Entity not found: {entity_id}")
        return entity

    def _relationship_exists(
        self,
        source_entity_id: UUID | str,
        relationship_type: str,
        target_entity_id: UUID | str,
    ) -> bool:
        source_id = UUID(str(source_entity_id))
        target_id = UUID(str(target_entity_id))
        return any(
            relationship.source_entity_id == source_id
            and relationship.relationship_type == relationship_type
            and relationship.target_entity_id == target_id
            for relationship in self.repository.get_relationships()
        )

    def _count_relationship_targets(self, source_entity_id: UUID | str, relationship_type: str) -> int:
        source_id = UUID(str(source_entity_id))
        return len(
            {
                relationship.target_entity_id
                for relationship in self.repository.get_relationships()
                if relationship.source_entity_id == source_id
                and relationship.relationship_type == relationship_type
            }
        )

    def _count_relationship_sources(self, target_entity_id: UUID | str, relationship_type: str) -> int:
        target_id = UUID(str(target_entity_id))
        return len(
            {
                relationship.source_entity_id
                for relationship in self.repository.get_relationships()
                if relationship.target_entity_id == target_id
                and relationship.relationship_type == relationship_type
            }
        )

    @staticmethod
    def _age_days(timestamp: str) -> int:
        try:
            parsed = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        except ValueError:
            return 999
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - parsed).days


def group_relationships_by_entity(
    relationships: list[EntityRelationship],
) -> dict[UUID, list[EntityRelationship]]:
    grouped: dict[UUID, list[EntityRelationship]] = defaultdict(list)
    for relationship in relationships:
        grouped[relationship.source_entity_id].append(relationship)
        grouped[relationship.target_entity_id].append(relationship)
    return grouped
