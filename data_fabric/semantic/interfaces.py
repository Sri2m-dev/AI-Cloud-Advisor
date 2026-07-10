"""Abstract interfaces for semantic ontology services."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Mapping

from data_fabric.contracts import EnterpriseEntity
from data_fabric.semantic.models import (
    ConceptRelationship,
    MappingResult,
    OntologyValidationResult,
    SemanticConcept,
    SemanticMapping,
    TaxonomyNode,
    TaxonomyPath,
)


class OntologyRegistry(ABC):
    @abstractmethod
    def register_concept(self, concept: SemanticConcept) -> SemanticConcept: ...

    @abstractmethod
    def get_concept(self, concept_id: str, *, organization_id: str, tenant_id: str | None) -> SemanticConcept | None: ...

    @abstractmethod
    def find_by_canonical_name(self, canonical_name: str, *, organization_id: str, tenant_id: str | None) -> SemanticConcept | None: ...

    @abstractmethod
    def find_by_synonym(self, synonym: str, *, organization_id: str, tenant_id: str | None) -> SemanticConcept | None: ...

    @abstractmethod
    def update_concept(self, concept: SemanticConcept) -> SemanticConcept: ...

    @abstractmethod
    def deactivate_concept(self, concept_id: str, *, organization_id: str, tenant_id: str | None) -> SemanticConcept: ...

    @abstractmethod
    def register_concept_relationship(self, relationship: ConceptRelationship) -> ConceptRelationship: ...

    @abstractmethod
    def list_concept_relationships(self, concept_id: str, *, organization_id: str, tenant_id: str | None) -> list[ConceptRelationship]: ...

    @abstractmethod
    def list_children(self, concept_id: str, *, organization_id: str, tenant_id: str | None) -> list[SemanticConcept]: ...

    @abstractmethod
    def list_ancestors(self, concept_id: str, *, organization_id: str, tenant_id: str | None) -> list[SemanticConcept]: ...

    @abstractmethod
    def list_descendants(self, concept_id: str, *, organization_id: str, tenant_id: str | None) -> list[SemanticConcept]: ...


class SemanticMapper(ABC):
    @abstractmethod
    def register_mapping(self, mapping: SemanticMapping) -> SemanticMapping: ...

    @abstractmethod
    def map_source_term(self, *, source_system: str, source_term: str, organization_id: str, tenant_id: str | None, source_type: str | None = None, source_identifier: str | None = None, provider: str | None = None, entity_type: str | None = None, attributes: Mapping[str, Any] | None = None) -> MappingResult: ...

    @abstractmethod
    def map_entity(self, entity: EnterpriseEntity, *, provider: str | None = None) -> MappingResult: ...

    @abstractmethod
    def list_mappings(self, *, organization_id: str, tenant_id: str | None) -> list[SemanticMapping]: ...

    @abstractmethod
    def find_mapping_candidates(self, *, source_term: str, organization_id: str, tenant_id: str | None, **kwargs: Any) -> list[Any]: ...

    @abstractmethod
    def resolve_mapping(self, result: MappingResult, *, include_inactive: bool = False) -> SemanticConcept | None: ...

    @abstractmethod
    def explain_mapping(self, result: MappingResult) -> str: ...

    @abstractmethod
    def deactivate_mapping(self, mapping_id: str, *, organization_id: str, tenant_id: str | None) -> SemanticMapping: ...


class TaxonomyService(ABC):
    @abstractmethod
    def create_taxonomy(self, taxonomy_id: str, *, organization_id: str, tenant_id: str | None) -> str: ...

    @abstractmethod
    def add_node(self, node: TaxonomyNode) -> TaxonomyNode: ...

    @abstractmethod
    def get_node(self, node_id: str, *, organization_id: str, tenant_id: str | None) -> TaxonomyNode | None: ...

    @abstractmethod
    def move_node(self, node_id: str, new_parent_node_id: str | None, *, organization_id: str, tenant_id: str | None) -> TaxonomyNode: ...

    @abstractmethod
    def remove_node(self, node_id: str, *, organization_id: str, tenant_id: str | None) -> None: ...

    @abstractmethod
    def list_roots(self, taxonomy_id: str, *, organization_id: str, tenant_id: str | None) -> list[TaxonomyNode]: ...

    @abstractmethod
    def list_children(self, node_id: str, *, organization_id: str, tenant_id: str | None) -> list[TaxonomyNode]: ...

    @abstractmethod
    def get_path(self, node_id: str, *, organization_id: str, tenant_id: str | None) -> TaxonomyPath: ...

    @abstractmethod
    def search_taxonomy(self, taxonomy_id: str, term: str, *, organization_id: str, tenant_id: str | None) -> list[TaxonomyNode]: ...

    @abstractmethod
    def detect_cycles(self, taxonomy_id: str, *, organization_id: str, tenant_id: str | None) -> list[tuple[str, str]]: ...


class OntologyValidator(ABC):
    @abstractmethod
    def validate(self, registry: OntologyRegistry, *, organization_id: str, tenant_id: str | None) -> OntologyValidationResult: ...
