"""In-memory ontology registry implementation."""

from __future__ import annotations

from dataclasses import replace
from typing import Any

from data_fabric.semantic.exceptions import SemanticValidationError
from data_fabric.semantic.interfaces import OntologyRegistry
from data_fabric.semantic.models import (
    ConceptRelationship,
    SemanticConcept,
    concept_terms,
    normalize_term,
)

PartitionKey = tuple[str, str | None]


class InMemoryOntologyRegistry(OntologyRegistry):
    """Tenant-isolated in-memory ontology registry."""

    def __init__(self) -> None:
        self._concepts: dict[PartitionKey, dict[str, SemanticConcept]] = {}
        self._relationships: dict[PartitionKey, dict[str, ConceptRelationship]] = {}

    def register_concept(self, concept: SemanticConcept) -> SemanticConcept:
        key = _partition(concept.organization_id, concept.tenant_id)
        self._validate_concept(concept)
        concepts = self._concepts.setdefault(key, {})
        if concept.concept_id in concepts:
            raise SemanticValidationError(f"concept_id already exists: {concept.concept_id}")
        self._ensure_name_available(concept, concepts)
        self._ensure_terms_available(concept, concepts)
        concepts[concept.concept_id] = concept
        return concept

    def get_concept(self, concept_id: str, *, organization_id: str, tenant_id: str | None) -> SemanticConcept | None:
        return self._concepts.get(_partition(organization_id, tenant_id), {}).get(concept_id)

    def find_by_canonical_name(self, canonical_name: str, *, organization_id: str, tenant_id: str | None) -> SemanticConcept | None:
        wanted = normalize_term(canonical_name)
        for concept in self._concepts.get(_partition(organization_id, tenant_id), {}).values():
            if normalize_term(concept.canonical_name) == wanted:
                return concept
        return None

    def find_by_synonym(self, synonym: str, *, organization_id: str, tenant_id: str | None) -> SemanticConcept | None:
        wanted = normalize_term(synonym)
        for concept in self._concepts.get(_partition(organization_id, tenant_id), {}).values():
            synonym_terms = [item.value for item in concept.synonyms] + list(concept.aliases)
            if any(normalize_term(term) == wanted for term in synonym_terms):
                return concept
        return None

    def update_concept(self, concept: SemanticConcept) -> SemanticConcept:
        key = _partition(concept.organization_id, concept.tenant_id)
        concepts = self._concepts.setdefault(key, {})
        if concept.concept_id not in concepts:
            raise SemanticValidationError(f"concept not found: {concept.concept_id}")
        self._validate_concept(concept)
        others = {cid: item for cid, item in concepts.items() if cid != concept.concept_id}
        self._ensure_name_available(concept, others)
        self._ensure_terms_available(concept, others)
        concepts[concept.concept_id] = concept
        return concept

    def deactivate_concept(self, concept_id: str, *, organization_id: str, tenant_id: str | None) -> SemanticConcept:
        concept = self.get_concept(concept_id, organization_id=organization_id, tenant_id=tenant_id)
        if concept is None:
            raise SemanticValidationError(f"concept not found: {concept_id}")
        updated = replace(concept, active=False)
        self.update_concept(updated)
        return updated

    def register_concept_relationship(self, relationship: ConceptRelationship) -> ConceptRelationship:
        key = _partition(relationship.organization_id, relationship.tenant_id)
        concepts = self._concepts.get(key, {})
        if relationship.source_concept_id not in concepts or relationship.target_concept_id not in concepts:
            raise SemanticValidationError("relationship endpoints must exist")
        if self._contradicts_existing(relationship):
            raise SemanticValidationError("equivalent_to conflicts with conflicts_with")
        relationships = self._relationships.setdefault(key, {})
        relationships[relationship.relationship_id] = relationship
        return relationship

    def list_concept_relationships(self, concept_id: str, *, organization_id: str, tenant_id: str | None) -> list[ConceptRelationship]:
        relationships = self._relationships.get(_partition(organization_id, tenant_id), {}).values()
        return sorted([item for item in relationships if item.source_concept_id == concept_id or item.target_concept_id == concept_id], key=lambda item: item.relationship_id)

    def list_children(self, concept_id: str, *, organization_id: str, tenant_id: str | None) -> list[SemanticConcept]:
        concepts = self._concepts.get(_partition(organization_id, tenant_id), {})
        return sorted([item for item in concepts.values() if item.parent_concept_id == concept_id], key=lambda item: item.concept_id)

    def list_ancestors(self, concept_id: str, *, organization_id: str, tenant_id: str | None) -> list[SemanticConcept]:
        concepts = self._concepts.get(_partition(organization_id, tenant_id), {})
        ancestors: list[SemanticConcept] = []
        seen: set[str] = set()
        current = concepts.get(concept_id)
        while current and current.parent_concept_id:
            if current.parent_concept_id in seen:
                raise SemanticValidationError("hierarchy cycle detected")
            seen.add(current.parent_concept_id)
            parent = concepts.get(current.parent_concept_id)
            if parent is None:
                break
            ancestors.append(parent)
            current = parent
        return ancestors

    def list_descendants(self, concept_id: str, *, organization_id: str, tenant_id: str | None) -> list[SemanticConcept]:
        descendants: list[SemanticConcept] = []
        stack = self.list_children(concept_id, organization_id=organization_id, tenant_id=tenant_id)
        seen: set[str] = set()
        while stack:
            child = stack.pop(0)
            if child.concept_id in seen:
                raise SemanticValidationError("hierarchy cycle detected")
            seen.add(child.concept_id)
            descendants.append(child)
            stack.extend(self.list_children(child.concept_id, organization_id=organization_id, tenant_id=tenant_id))
        return sorted(descendants, key=lambda item: item.concept_id)

    def list_concepts(self, *, organization_id: str, tenant_id: str | None) -> list[SemanticConcept]:
        return sorted(self._concepts.get(_partition(organization_id, tenant_id), {}).values(), key=lambda item: item.concept_id)

    def effective_attributes(self, concept_id: str, *, organization_id: str, tenant_id: str | None) -> tuple[dict[str, Any], tuple[str, ...]]:
        concept = self.get_concept(concept_id, organization_id=organization_id, tenant_id=tenant_id)
        if concept is None:
            raise SemanticValidationError(f"concept not found: {concept_id}")
        chain = list(reversed(self.list_ancestors(concept_id, organization_id=organization_id, tenant_id=tenant_id))) + [concept]
        attributes: dict[str, Any] = {}
        explanation: list[str] = []
        for item in chain:
            for key, value in item.attributes.items():
                attributes[key] = value
                explanation.append(f"{key} from {item.concept_id}")
        return attributes, tuple(explanation)

    def _validate_concept(self, concept: SemanticConcept) -> None:
        if concept.parent_concept_id == concept.concept_id:
            raise SemanticValidationError("self-parent concepts are rejected")
        key = _partition(concept.organization_id, concept.tenant_id)
        if concept.parent_concept_id and concept.parent_concept_id not in self._concepts.get(key, {}):
            raise SemanticValidationError("parent concept must exist")
        if concept.parent_concept_id and self._would_create_cycle(concept):
            raise SemanticValidationError("hierarchy cycle detected")

    @staticmethod
    def _ensure_name_available(concept: SemanticConcept, concepts: dict[str, SemanticConcept]) -> None:
        wanted = normalize_term(concept.canonical_name)
        if any(normalize_term(item.canonical_name) == wanted for item in concepts.values()):
            raise SemanticValidationError("canonical names must be unique within tenant")

    @staticmethod
    def _ensure_terms_available(concept: SemanticConcept, concepts: dict[str, SemanticConcept]) -> None:
        existing: dict[str, str] = {}
        for item in concepts.values():
            for synonym in item.synonyms:
                existing[normalize_term(synonym.value)] = item.concept_id
        for synonym in concept.synonyms:
            normalized = normalize_term(synonym.value)
            if normalized in existing:
                raise SemanticValidationError(f"synonym collision detected with {existing[normalized]}")

    def _would_create_cycle(self, concept: SemanticConcept) -> bool:
        key = _partition(concept.organization_id, concept.tenant_id)
        concepts = dict(self._concepts.get(key, {}))
        concepts[concept.concept_id] = concept
        seen: set[str] = set()
        current = concept
        while current.parent_concept_id:
            if current.parent_concept_id in seen or current.parent_concept_id == concept.concept_id:
                return True
            seen.add(current.parent_concept_id)
            parent = concepts.get(current.parent_concept_id)
            if parent is None:
                return False
            current = parent
        return False

    def _contradicts_existing(self, relationship: ConceptRelationship) -> bool:
        if relationship.relationship_type not in {"equivalent_to", "conflicts_with"}:
            return False
        opposite = "conflicts_with" if relationship.relationship_type == "equivalent_to" else "equivalent_to"
        endpoints = {relationship.source_concept_id, relationship.target_concept_id}
        for existing in self._relationships.get(_partition(relationship.organization_id, relationship.tenant_id), {}).values():
            if existing.relationship_type == opposite and {existing.source_concept_id, existing.target_concept_id} == endpoints:
                return True
        return False


def _partition(organization_id: str, tenant_id: str | None) -> PartitionKey:
    return (organization_id, tenant_id)

