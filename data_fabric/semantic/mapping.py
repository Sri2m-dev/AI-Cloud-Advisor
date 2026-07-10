"""In-memory semantic mapping implementation."""

from __future__ import annotations

from dataclasses import replace
from typing import Any, Mapping

from data_fabric.contracts import EnterpriseEntity
from data_fabric.semantic.exceptions import SemanticValidationError
from data_fabric.semantic.interfaces import SemanticMapper
from data_fabric.semantic.models import (
    MappingCandidate,
    MappingDecision,
    MappingResult,
    SemanticMapping,
    concept_terms,
    normalize_term,
)
from data_fabric.semantic.ontology import InMemoryOntologyRegistry


class InMemorySemanticMapper(SemanticMapper):
    """Tenant-isolated in-memory source-term to concept mapper."""

    def __init__(self, registry: InMemoryOntologyRegistry) -> None:
        self._registry = registry
        self._mappings: dict[tuple[str, str | None], dict[str, SemanticMapping]] = {}

    def register_mapping(self, mapping: SemanticMapping) -> SemanticMapping:
        concept = self._registry.get_concept(mapping.concept_id, organization_id=mapping.organization_id, tenant_id=mapping.tenant_id)
        if concept is None:
            raise SemanticValidationError("mapping target concept must exist")
        key = (mapping.organization_id, mapping.tenant_id)
        self._mappings.setdefault(key, {})[mapping.mapping_id] = mapping
        return mapping

    def map_source_term(
        self,
        *,
        source_system: str,
        source_term: str,
        organization_id: str,
        tenant_id: str | None,
        source_type: str | None = None,
        source_identifier: str | None = None,
        provider: str | None = None,
        entity_type: str | None = None,
        attributes: Mapping[str, Any] | None = None,
    ) -> MappingResult:
        candidates = self.find_mapping_candidates(
            source_term=source_term,
            organization_id=organization_id,
            tenant_id=tenant_id,
            source_system=source_system,
            source_type=source_type,
            source_identifier=source_identifier,
            provider=provider,
            entity_type=entity_type,
            attributes=attributes or {},
        )
        active_candidates = [candidate for candidate in candidates if candidate.concept.active]
        if not active_candidates:
            return MappingResult(MappingDecision.NO_MATCH, source_term, organization_id, tenant_id, (), None, ("no active candidates",))
        top_score = active_candidates[0].confidence
        top = [candidate for candidate in active_candidates if candidate.confidence == top_score]
        if len(top) > 1:
            return MappingResult(MappingDecision.AMBIGUOUS, source_term, organization_id, tenant_id, tuple(active_candidates), None, tuple(f"ambiguous candidate {item.concept.concept_id}: {', '.join(item.reasons)}" for item in top))
        selected = top[0]
        return MappingResult(MappingDecision.MATCH, source_term, organization_id, tenant_id, tuple(active_candidates), selected, (f"selected {selected.concept.concept_id}: {', '.join(selected.reasons)}",))

    def map_entity(self, entity: EnterpriseEntity, *, provider: str | None = None) -> MappingResult:
        return self.map_source_term(
            source_system=entity.source_system,
            source_term=entity.name,
            source_identifier=entity.source_identifier,
            provider=provider,
            entity_type=entity.entity_type.value,
            attributes=entity.metadata,
            organization_id=entity.organization_id,
            tenant_id=entity.tenant_id,
        )

    def list_mappings(self, *, organization_id: str, tenant_id: str | None) -> list[SemanticMapping]:
        return sorted(self._mappings.get((organization_id, tenant_id), {}).values(), key=lambda item: item.mapping_id)

    def find_mapping_candidates(self, *, source_term: str, organization_id: str, tenant_id: str | None, **kwargs: Any) -> list[MappingCandidate]:
        normalized = normalize_term(source_term)
        candidates: dict[str, MappingCandidate] = {}
        for mapping in self.list_mappings(organization_id=organization_id, tenant_id=tenant_id):
            if not mapping.active:
                continue
            if _mapping_matches(mapping, source_term=source_term, normalized=normalized, kwargs=kwargs):
                concept = self._registry.get_concept(mapping.concept_id, organization_id=organization_id, tenant_id=tenant_id)
                if concept:
                    _add_candidate(candidates, MappingCandidate(concept, mapping.confidence, ("explicit_mapping",), mapping))
        for concept in self._registry.list_concepts(organization_id=organization_id, tenant_id=tenant_id):
            exact_terms = concept_terms(concept)
            normalized_terms = {normalize_term(term) for term in exact_terms}
            if source_term in exact_terms:
                _add_candidate(candidates, MappingCandidate(concept, 95.0, ("exact_canonical_or_alias",)))
            elif normalized in normalized_terms:
                reason = "exact_synonym_or_alias" if any(normalize_term(term) == normalized for term in list(concept.aliases) + [syn.value for syn in concept.synonyms]) else "normalized_term"
                _add_candidate(candidates, MappingCandidate(concept, 90.0, (reason,)))
            elif _attribute_assisted_match(concept, kwargs.get("attributes") or {}):
                _add_candidate(candidates, MappingCandidate(concept, 75.0, ("attribute_assisted",)))
        return sorted(candidates.values(), key=lambda item: (-item.confidence, item.concept.canonical_name, item.concept.concept_id))

    def resolve_mapping(self, result: MappingResult, *, include_inactive: bool = False):
        if result.selected is None:
            return None
        if not include_inactive and not result.selected.concept.active:
            return None
        return result.selected.concept

    def explain_mapping(self, result: MappingResult) -> str:
        lines = [f"decision={result.decision.value}", f"source_term={result.source_term}"]
        for candidate in result.candidates:
            lines.append(f"candidate={candidate.concept.concept_id} confidence={candidate.confidence:.1f} reasons={','.join(candidate.reasons)}")
        lines.extend(result.explanation)
        return "\n".join(lines)

    def deactivate_mapping(self, mapping_id: str, *, organization_id: str, tenant_id: str | None) -> SemanticMapping:
        mappings = self._mappings.get((organization_id, tenant_id), {})
        if mapping_id not in mappings:
            raise SemanticValidationError(f"mapping not found: {mapping_id}")
        updated = replace(mappings[mapping_id], active=False)
        mappings[mapping_id] = updated
        return updated


def register_demo_mappings(mapper: InMemorySemanticMapper, *, organization_id: str, tenant_id: str | None) -> None:
    examples = [
        ("aws-ec2", "aws", "EC2", "virtual-machine"),
        ("azure-vm", "azure", "Virtual Machines", "virtual-machine"),
        ("gcp-compute", "gcp", "Compute Engine", "virtual-machine"),
        ("aws-s3", "aws", "S3", "object-storage"),
        ("azure-blob", "azure", "Blob Storage", "object-storage"),
        ("gcp-storage", "gcp", "Cloud Storage", "object-storage"),
        ("aws-rds", "aws", "RDS", "managed-relational-database"),
        ("azure-sql", "azure", "SQL Database", "managed-relational-database"),
        ("gcp-sql", "gcp", "Cloud SQL", "managed-relational-database"),
        ("aws-eks", "aws", "EKS", "managed-kubernetes"),
        ("azure-aks", "azure", "Kubernetes Service", "managed-kubernetes"),
        ("gcp-gke", "gcp", "Kubernetes Engine", "managed-kubernetes"),
        ("aws-cloudwatch", "aws", "CloudWatch", "cloud-monitoring"),
        ("azure-monitor", "azure", "Monitor", "cloud-monitoring"),
        ("gcp-monitoring", "gcp", "Cloud Monitoring", "cloud-monitoring"),
    ]
    for mapping_id, provider, source_term, concept_id in examples:
        mapper.register_mapping(SemanticMapping(mapping_id, provider, source_term, None, None, provider, None, concept_id, organization_id, tenant_id, 100.0))


def _mapping_matches(mapping: SemanticMapping, *, source_term: str, normalized: str, kwargs: dict[str, Any]) -> bool:
    if normalize_term(mapping.source_term) != normalized:
        return False
    for field in ("source_system", "source_type", "source_identifier", "provider", "entity_type"):
        expected = getattr(mapping, field)
        actual = kwargs.get(field)
        if expected is not None and actual is not None and normalize_term(str(expected)) != normalize_term(str(actual)):
            return False
    return True


def _attribute_assisted_match(concept, attributes: Mapping[str, Any]) -> bool:
    keywords = concept.attributes.get("keywords", ())
    values = " ".join(str(value) for value in attributes.values()).casefold()
    return any(str(keyword).casefold() in values for keyword in keywords)


def _add_candidate(candidates: dict[str, MappingCandidate], candidate: MappingCandidate) -> None:
    existing = candidates.get(candidate.concept.concept_id)
    if existing is None or candidate.confidence > existing.confidence:
        candidates[candidate.concept.concept_id] = candidate
