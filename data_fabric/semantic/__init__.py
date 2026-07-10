"""Semantic model and ontology interfaces for P3 Data Fabric."""

from data_fabric.semantic.exceptions import SemanticError, SemanticValidationError
from data_fabric.semantic.interfaces import (
    OntologyRegistry,
    OntologyValidator,
    SemanticMapper,
    TaxonomyService,
)
from data_fabric.semantic.mapping import InMemorySemanticMapper
from data_fabric.semantic.models import (
    CONCEPT_RELATIONSHIP_TYPES,
    CONCEPT_TYPES,
    ConceptIdentifier,
    ConceptRelationship,
    ConceptSynonym,
    MappingCandidate,
    MappingDecision,
    MappingResult,
    OntologyValidationIssue,
    OntologyValidationResult,
    SemanticConcept,
    SemanticMapping,
    TaxonomyNode,
    TaxonomyPath,
)
from data_fabric.semantic.ontology import InMemoryOntologyRegistry
from data_fabric.semantic.taxonomy import InMemoryTaxonomyService
from data_fabric.semantic.validation import DefaultOntologyValidator

__all__ = [
    "CONCEPT_RELATIONSHIP_TYPES",
    "CONCEPT_TYPES",
    "ConceptIdentifier",
    "ConceptRelationship",
    "ConceptSynonym",
    "DefaultOntologyValidator",
    "InMemoryOntologyRegistry",
    "InMemorySemanticMapper",
    "InMemoryTaxonomyService",
    "MappingCandidate",
    "MappingDecision",
    "MappingResult",
    "OntologyRegistry",
    "OntologyValidationIssue",
    "OntologyValidationResult",
    "OntologyValidator",
    "SemanticConcept",
    "SemanticError",
    "SemanticMapper",
    "SemanticMapping",
    "SemanticValidationError",
    "TaxonomyNode",
    "TaxonomyPath",
    "TaxonomyService",
]
