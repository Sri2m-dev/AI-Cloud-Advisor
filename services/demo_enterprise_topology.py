"""Golden Demo projection into existing canonical enterprise contracts.

This module owns no graph, registry, persistence layer, or AI framework.
It converts certified Golden Demo twin-path evidence into the existing
EnterpriseEntity and EnterpriseRelationship contracts.
"""

from __future__ import annotations

from hashlib import sha256

from data_fabric.contracts import (
    EnterpriseEntity,
    EnterpriseRelationship,
    EntityType,
    RelationshipType,
)
from services.demo_tenant_service import (
    demo_mode_enabled,
    is_demo_tenant,
    load_demo_tenant,
)


SOURCE_SYSTEM = "golden_demo"

_LAYER_ENTITY_TYPES = {
    "Business Service": EntityType.BUSINESS_SERVICE,
    "Application": EntityType.APPLICATION,
    "Technology": EntityType.TECHNOLOGY,
    "Cloud": EntityType.VENDOR,
    "Decision": EntityType.RECOMMENDATION,
    "Cost": EntityType.EVIDENCE,
    "Risk": EntityType.RISK,
}

_DEPENDENCY_TARGET_LAYERS = frozenset(
    {"Application", "Technology", "Cloud"}
)


def _stable_id(prefix: str, *parts: str) -> str:
    payload = "|".join(str(part).strip().casefold() for part in parts)
    digest = sha256(payload.encode("utf-8")).hexdigest()[:20]
    return f"demo:{prefix}:{digest}"


def _pointer(journey_index: int, node_index: int | None = None) -> str:
    base = f"data/demo/nexora_global_retail.json#/journeys/{journey_index}"
    if node_index is None:
        return base
    return f"{base}/twin_path/{node_index}"


def demo_enterprise_topology(context):
    """Return canonical demo entities and relationships for demo scope only."""

    if not demo_mode_enabled() or not is_demo_tenant(context.organization_id):
        return (), ()

    payload = load_demo_tenant(context.organization_id)
    journeys = tuple(payload.get("journeys") or ())

    entity_specs = {}

    for journey_index, journey in enumerate(journeys):
        path = tuple(journey.get("twin_path") or ())

        for node_index, node in enumerate(path):
            layer = str(node.get("layer") or "").strip()
            name = str(node.get("entity") or "").strip()
            entity_type = _LAYER_ENTITY_TYPES.get(layer)

            if not name or entity_type is None:
                continue

            key = (entity_type.value, name.casefold())

            spec = entity_specs.setdefault(
                key,
                {
                    "entity_type": entity_type,
                    "name": name,
                    "references": [],
                    "journeys": [],
                },
            )

            spec["references"].append(
                _pointer(journey_index, node_index)
            )

            spec["journeys"].append(
                {
                    "decision_id": journey.get("decision_id"),
                    "title": journey.get("title"),
                    "change": journey.get("change"),
                    "impact": journey.get("impact"),
                    "recommendation": journey.get("recommendation"),
                    "evidence": journey.get("evidence"),
                    "next_step": journey.get("next_step"),
                }
            )

    entities = []
    by_key = {}

    for key in sorted(entity_specs):
        spec = entity_specs[key]
        entity_type = spec["entity_type"]
        name = spec["name"]

        canonical_id = _stable_id(
            "entity",
            entity_type.value,
            name,
        )

        references = tuple(
            dict.fromkeys(spec["references"])
        )

        entity = EnterpriseEntity(
            id=canonical_id,
            canonical_id=canonical_id,
            entity_type=entity_type,
            name=name,
            canonical_name=name,
            display_name=name,
            source_system=SOURCE_SYSTEM,
            source_identifier=references[0],
            organization_id=context.organization_id,
            tenant_id=context.tenant_id,
            confidence_score=1.0,
            quality_score=1.0,
            classification_status="CLASSIFIED",
            provenance_reference=references[0],
            lineage_reference=references[0],
            tags=["synthetic_demo", "golden_demo"],
            metadata={
                "classification": payload.get("classification"),
                "demo_source": payload.get("source"),
                "as_of": payload.get("as_of"),
                "evidence_references": references,
                "journeys": tuple(spec["journeys"]),
            },
        )

        entities.append(entity)
        by_key[key] = entity

    relationships = []

    for journey_index, journey in enumerate(journeys):
        path = tuple(journey.get("twin_path") or ())

        for node_index in range(len(path) - 1):
            source_node = path[node_index]
            target_node = path[node_index + 1]

            source_layer = str(
                source_node.get("layer") or ""
            ).strip()

            target_layer = str(
                target_node.get("layer") or ""
            ).strip()

            source_name = str(
                source_node.get("entity") or ""
            ).strip()

            target_name = str(
                target_node.get("entity") or ""
            ).strip()

            source_type = _LAYER_ENTITY_TYPES.get(source_layer)
            target_type = _LAYER_ENTITY_TYPES.get(target_layer)

            if (
                not source_name
                or not target_name
                or source_type is None
                or target_type is None
            ):
                continue

            source = by_key.get(
                (source_type.value, source_name.casefold())
            )

            target = by_key.get(
                (target_type.value, target_name.casefold())
            )

            if source is None or target is None:
                continue

            relationship_type = (
                RelationshipType.DEPENDS_ON
                if target_layer in _DEPENDENCY_TARGET_LAYERS
                else RelationshipType.ASSOCIATED_WITH
            )

            evidence = (
                _pointer(journey_index, node_index),
                _pointer(journey_index, node_index + 1),
            )

            relationship = EnterpriseRelationship(
                id=_stable_id(
                    "relationship",
                    source.canonical_id,
                    relationship_type.value,
                    target.canonical_id,
                    str(
                        journey.get("decision_id")
                        or journey_index
                    ),
                ),
                relationship_type=relationship_type,
                source_entity_id=source.id,
                target_entity_id=target.id,
                organization_id=context.organization_id,
                tenant_id=context.tenant_id,
                source_system=SOURCE_SYSTEM,
                source_identifier=(
                    "data/demo/nexora_global_retail.json"
                    f"#/journeys/{journey_index}/twin_path"
                ),
                confidence_score=1.0,
                quality_score=1.0,
                evidence=evidence,
                provenance_reference=_pointer(journey_index),
                lineage_reference=_pointer(journey_index),
                decision_state="confirmed",
                decision_reason=(
                    "Certified Golden Demo twin_path evidence"
                ),
                metadata={
                    "classification": payload.get("classification"),
                    "decision_id": journey.get("decision_id"),
                    "journey_title": journey.get("title"),
                    "evidence_statement": journey.get("evidence"),
                },
            )

            relationships.append(relationship)

    return tuple(entities), tuple(relationships)
