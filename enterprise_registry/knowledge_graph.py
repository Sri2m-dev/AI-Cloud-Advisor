"""Read-only enterprise knowledge projection over canonical intelligence services."""

from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter
from typing import Any, Mapping

from data_fabric.contracts import EnterpriseEntity
from enterprise_registry.relationship_intelligence import RelationshipPath


@dataclass(frozen=True, slots=True)
class KnowledgeEvidence:
    source: str
    confidence: float
    evidence: tuple[str, ...]
    lineage: str | None
    classification_status: str


@dataclass(frozen=True, slots=True)
class KnowledgeNode:
    entity: EnterpriseEntity
    classifications: tuple[Mapping[str, Any], ...]
    financial_context: Mapping[str, Any]
    relationships: tuple[Any, ...]
    evidence: KnowledgeEvidence


@dataclass(frozen=True, slots=True)
class KnowledgeAnswer:
    subject: KnowledgeNode
    paths: tuple[RelationshipPath, ...]
    entities: tuple[EnterpriseEntity, ...]
    narrative: str
    financial_impact: float
    evidence: tuple[KnowledgeEvidence, ...]


class EnterpriseKnowledgeGraphService:
    """Deterministic projection; owns neither entities nor relationships."""

    def __init__(self, registry, relationships) -> None:
        self.registry = registry
        self.relationships = relationships

    def find_entity(self, canonical_id: str) -> KnowledgeNode:
        entity = self.registry.get_entity(canonical_id)
        direct = self.relationships.get_relationships(canonical_id)
        classifications = self.registry.get_classifications(canonical_id)
        financial = self.registry.get_financial_context(canonical_id)
        evidence = tuple(
            item for relationship in direct for item in relationship.evidence if str(item).strip()
        )
        return KnowledgeNode(
            entity=entity,
            classifications=classifications,
            financial_context=financial,
            relationships=direct,
            evidence=KnowledgeEvidence(
                source=entity.source_system,
                confidence=entity.confidence_score,
                evidence=evidence,
                lineage=entity.lineage_reference,
                classification_status=entity.classification_status,
            ),
        )

    def explain_entity(self, canonical_id: str) -> KnowledgeAnswer:
        subject = self.find_entity(canonical_id)
        paths = self.relationships.traverse(canonical_id, max_hops=3)
        entities = tuple(path.entities[-1] for path in paths)
        financial = self.find_financial_impact(canonical_id)
        related_types = {}
        for entity in entities:
            label = entity.entity_type.value.replace("_", " ")
            related_types[label] = related_types.get(label, 0) + 1
        scope = ", ".join(f"{count} {label}(s)" for label, count in sorted(related_types.items()))
        subject_type = subject.entity.entity_type.value.replace("_", " ")
        narrative = (
            f"{subject.entity.display_name} is a {subject_type} from "
            f"{subject.entity.source_system}."
        )
        if scope:
            narrative += f" It is connected to {scope} through {len(paths)} governed path(s)."
        else:
            narrative += " No evidence-backed canonical relationships are currently available."
        if financial:
            narrative += f" Referenced financial impact is {financial:,.2f} USD."
        return KnowledgeAnswer(
            subject,
            paths,
            entities,
            narrative,
            financial,
            self._path_evidence(paths),
        )

    def search_graph(self, query: str, *, entity_type: str | None = None, limit: int = 100):
        return self.registry.search_entities(query, entity_type=entity_type, limit=limit)

    def find_path(self, source_canonical_id: str, target_canonical_id: str, max_hops=10):
        return next(
            (
                path
                for path in self.relationships.traverse(source_canonical_id, max_hops=max_hops)
                if path.entities[-1].canonical_id == target_canonical_id
            ),
            None,
        )

    def find_owners(self, canonical_id: str):
        return self.relationships.get_owners(canonical_id)

    def find_dependencies(self, canonical_id: str, max_hops=3):
        return self.relationships.get_dependencies(canonical_id, max_hops)

    def find_consumers(self, canonical_id: str):
        return self.relationships.get_consumers(canonical_id)

    def find_providers(self, canonical_id: str):
        return self.relationships.get_providers(canonical_id)

    def find_business_impact(self, canonical_id: str, max_hops=5):
        business_types = {
            "organization",
            "business_unit",
            "department",
            "business_capability",
            "business_service",
            "business_process",
        }
        impact = self.relationships.get_impact(canonical_id, max_hops)
        return tuple(
            entity for entity in impact.impacted if entity.entity_type.value in business_types
        )

    def find_financial_impact(self, canonical_id: str) -> float:
        contexts = [self.registry.get_financial_context(canonical_id)]
        contexts.extend(
            self.registry.get_financial_context(path.entities[-1].canonical_id)
            for path in self.relationships.traverse(canonical_id, max_hops=5)
        )
        seen = set()
        total = 0.0
        for context in contexts:
            reference = str(
                context.get("account_id")
                or context.get("allocation_id")
                or context.get("source_reference")
                or ""
            )
            signature = reference or repr(sorted(context.items()))
            if not context or signature in seen:
                continue
            seen.add(signature)
            total += self._amount(context)
        return total

    def performance_probe(self, canonical_id: str, query: str):
        start = perf_counter()
        self.registry.get_entity(canonical_id)
        entity_ms = (perf_counter() - start) * 1000
        start = perf_counter()
        self.search_graph(query)
        search_ms = (perf_counter() - start) * 1000
        start = perf_counter()
        self.relationships.traverse(canonical_id, max_hops=None)
        traversal_ms = (perf_counter() - start) * 1000
        return {"entity_ms": entity_ms, "search_ms": search_ms, "traversal_ms": traversal_ms}

    @staticmethod
    def _amount(context):
        for key in (
            "unblended_spend",
            "total_spend",
            "allocated_spend",
            "monthly_cost",
            "amount",
        ):
            if context.get(key) not in (None, ""):
                try:
                    return float(context[key])
                except (TypeError, ValueError):
                    return 0.0
        return 0.0

    @staticmethod
    def _path_evidence(paths):
        return tuple(
            KnowledgeEvidence(
                source=edge.source_system or "UNKNOWN",
                confidence=edge.confidence_score,
                evidence=edge.evidence,
                lineage=edge.lineage_reference,
                classification_status="RELATIONSHIP_EVIDENCE",
            )
            for path in paths
            for edge in path.relationships[-1:]
        )
