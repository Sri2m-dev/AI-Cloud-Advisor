"""Ontology validation service."""

from __future__ import annotations

from data_fabric.semantic.interfaces import OntologyRegistry, OntologyValidator
from data_fabric.semantic.models import OntologyValidationIssue, OntologyValidationResult, normalize_term


class DefaultOntologyValidator(OntologyValidator):
    """Provider-agnostic validation over an in-memory ontology registry."""

    def validate(self, registry: OntologyRegistry, *, organization_id: str, tenant_id: str | None) -> OntologyValidationResult:
        issues: list[OntologyValidationIssue] = []
        concepts = getattr(registry, "list_concepts")(organization_id=organization_id, tenant_id=tenant_id)
        names: dict[str, str] = {}
        terms: dict[str, str] = {}
        for concept in concepts:
            if not concept.concept_id:
                issues.append(OntologyValidationIssue("concept_id_required", "concept_id is required"))
            if not concept.canonical_name:
                issues.append(OntologyValidationIssue("canonical_name_required", "canonical_name is required", concept_id=concept.concept_id))
            normalized_name = normalize_term(concept.canonical_name)
            if normalized_name in names:
                issues.append(OntologyValidationIssue("duplicate_canonical_name", "canonical name collision", concept_id=concept.concept_id))
            names[normalized_name] = concept.concept_id
            if concept.parent_concept_id:
                if registry.get_concept(concept.parent_concept_id, organization_id=organization_id, tenant_id=tenant_id) is None:
                    issues.append(OntologyValidationIssue("missing_parent", "parent concept must exist", concept_id=concept.concept_id))
                if concept.parent_concept_id == concept.concept_id:
                    issues.append(OntologyValidationIssue("self_parent", "self-parent concepts are rejected", concept_id=concept.concept_id))
            for term in [concept.canonical_name, concept.display_name, *concept.aliases, *[syn.value for syn in concept.synonyms]]:
                normalized = normalize_term(term)
                if normalized in terms and terms[normalized] != concept.concept_id:
                    issues.append(OntologyValidationIssue("synonym_collision", "synonym collision detected", concept_id=concept.concept_id))
                terms[normalized] = concept.concept_id
            try:
                registry.list_ancestors(concept.concept_id, organization_id=organization_id, tenant_id=tenant_id)
            except Exception:
                issues.append(OntologyValidationIssue("hierarchy_cycle", "hierarchy cycle detected", concept_id=concept.concept_id))
        return OntologyValidationResult(valid=not issues, issues=tuple(issues))
