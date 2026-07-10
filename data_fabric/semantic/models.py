"""Immutable semantic ontology value models."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from types import MappingProxyType
from typing import Any, Mapping

from data_fabric.semantic.exceptions import SemanticValidationError

CONCEPT_TYPES: tuple[str, ...] = (
    "compute",
    "storage",
    "database",
    "networking",
    "security",
    "observability",
    "integration",
    "analytics",
    "artificial_intelligence",
    "container_platform",
    "identity",
    "collaboration",
    "business_application",
    "infrastructure_service",
    "managed_service",
    "license",
    "vendor",
    "capability",
    "business_service",
)

CONCEPT_RELATIONSHIP_TYPES: tuple[str, ...] = (
    "is_a",
    "part_of",
    "equivalent_to",
    "related_to",
    "depends_on",
    "provided_by",
    "implemented_by",
    "supports",
    "supersedes",
    "conflicts_with",
)


class MappingDecision(str, Enum):
    MATCH = "match"
    AMBIGUOUS = "ambiguous"
    NO_MATCH = "no_match"


@dataclass(frozen=True, slots=True)
class ConceptIdentifier:
    value: str
    namespace: str = "canonical"


@dataclass(frozen=True, slots=True)
class ConceptSynonym:
    value: str
    source: str | None = None


@dataclass(frozen=True, slots=True)
class SemanticConcept:
    concept_id: str
    canonical_name: str
    display_name: str
    description: str
    concept_type: str
    parent_concept_id: str | None
    organization_id: str
    tenant_id: str | None
    synonyms: tuple[ConceptSynonym | str, ...] = field(default_factory=tuple)
    aliases: tuple[str, ...] = field(default_factory=tuple)
    attributes: Mapping[str, Any] = field(default_factory=dict)
    version: int = 1
    active: bool = True
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        if self.concept_type not in CONCEPT_TYPES:
            raise SemanticValidationError(f"Unknown concept_type: {self.concept_type}")
        if not self.concept_id:
            raise SemanticValidationError("concept_id is required")
        if not self.canonical_name:
            raise SemanticValidationError("canonical_name is required")
        normalized_synonyms = tuple(
            item if isinstance(item, ConceptSynonym) else ConceptSynonym(str(item))
            for item in self.synonyms
        )
        object.__setattr__(self, "synonyms", normalized_synonyms)
        object.__setattr__(self, "aliases", tuple(self.aliases))
        object.__setattr__(self, "attributes", MappingProxyType(dict(self.attributes)))


@dataclass(frozen=True, slots=True)
class ConceptRelationship:
    relationship_id: str
    source_concept_id: str
    target_concept_id: str
    relationship_type: str
    organization_id: str
    tenant_id: str | None
    active: bool = True
    attributes: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.relationship_type not in CONCEPT_RELATIONSHIP_TYPES:
            raise SemanticValidationError(f"Unknown concept relationship type: {self.relationship_type}")
        if self.source_concept_id == self.target_concept_id:
            raise SemanticValidationError("concept relationship cannot target itself")
        object.__setattr__(self, "attributes", MappingProxyType(dict(self.attributes)))


@dataclass(frozen=True, slots=True)
class SemanticMapping:
    mapping_id: str
    source_system: str
    source_term: str
    source_type: str | None
    source_identifier: str | None
    provider: str | None
    entity_type: str | None
    concept_id: str
    organization_id: str
    tenant_id: str | None
    confidence: float = 100.0
    active: bool = True
    attributes: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.confidence < 0.0 or self.confidence > 100.0:
            raise SemanticValidationError("mapping confidence must be between 0 and 100")
        object.__setattr__(self, "attributes", MappingProxyType(dict(self.attributes)))


@dataclass(frozen=True, slots=True)
class MappingCandidate:
    concept: SemanticConcept
    confidence: float
    reasons: tuple[str, ...]
    mapping: SemanticMapping | None = None

    def __post_init__(self) -> None:
        if self.confidence < 0.0 or self.confidence > 100.0:
            raise SemanticValidationError("candidate confidence must be between 0 and 100")
        object.__setattr__(self, "reasons", tuple(self.reasons))


@dataclass(frozen=True, slots=True)
class MappingResult:
    decision: MappingDecision
    source_term: str
    organization_id: str
    tenant_id: str | None
    candidates: tuple[MappingCandidate, ...] = field(default_factory=tuple)
    selected: MappingCandidate | None = None
    explanation: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        object.__setattr__(self, "decision", MappingDecision(self.decision))
        object.__setattr__(self, "candidates", tuple(self.candidates))
        object.__setattr__(self, "explanation", tuple(self.explanation))


@dataclass(frozen=True, slots=True)
class TaxonomyNode:
    node_id: str
    taxonomy_id: str
    concept_id: str
    parent_node_id: str | None
    organization_id: str
    tenant_id: str | None
    display_order: int = 0
    attributes: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.node_id == self.parent_node_id:
            raise SemanticValidationError("taxonomy node cannot parent itself")
        object.__setattr__(self, "attributes", MappingProxyType(dict(self.attributes)))


@dataclass(frozen=True, slots=True)
class TaxonomyPath:
    taxonomy_id: str
    node_ids: tuple[str, ...]
    concept_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class OntologyValidationIssue:
    code: str
    message: str
    severity: str = "error"
    concept_id: str | None = None


@dataclass(frozen=True, slots=True)
class OntologyValidationResult:
    valid: bool
    issues: tuple[OntologyValidationIssue, ...] = field(default_factory=tuple)


def normalize_term(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.casefold()).strip()


def concept_terms(concept: SemanticConcept) -> tuple[str, ...]:
    terms = [concept.canonical_name, concept.display_name, *concept.aliases]
    terms.extend(synonym.value for synonym in concept.synonyms)
    return tuple(term for term in terms if term)
