"""Production view models over certified ACT-006 and ACT-007 authority."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Iterable

from data_fabric.contracts import EntityType
from universal_evidence.persistence import LifecycleScope
from universal_evidence.pilot.reconciliation import (
    ReconciliationState,
)

ENTITY_LABELS = {
    EntityType.APPLICATION: "Applications",
    EntityType.BUSINESS_SERVICE: "Business Services",
    EntityType.TECHNOLOGY: "Technologies",
    EntityType.CLOUD_RESOURCE: "Cloud Resources",
    EntityType.OWNER: "Owners",
    EntityType.COST_CENTER: "Cost Centers",
    EntityType.SAAS_PRODUCT: "SaaS Products",
    EntityType.CONTRACT: "Contracts",
    EntityType.LICENSE: "Licenses",
}

ENTITY_SINGULAR_LABELS = {
    EntityType.APPLICATION: "Application",
    EntityType.BUSINESS_SERVICE: "Business Service",
    EntityType.TECHNOLOGY: "Technology",
    EntityType.CLOUD_RESOURCE: "Cloud Resource",
    EntityType.OWNER: "Owner",
    EntityType.COST_CENTER: "Cost Center",
    EntityType.SAAS_PRODUCT: "SaaS Product",
    EntityType.CONTRACT: "Contract",
    EntityType.LICENSE: "License",
}

RELATIONSHIP_LABELS = {
    "owned_by": "owned by",
    "funded_by": "assigned to",
    "supports": "supports",
    "depends_on": "depends on",
    "runs_on": "runs on",
    "associated_with": "related to",
    "provided_by": "provided by",
    "supplied_by": "supplied by",
}

RECONCILIATION_LABELS = {
    ReconciliationState.EXACT_MATCH: "Matched",
    ReconciliationState.CONFIRMED_MATCH: "Matched",
    ReconciliationState.POSSIBLE_MATCH: "Needs Review",
    ReconciliationState.CONFLICT: "Conflict",
    ReconciliationState.UNRESOLVED: "Unresolved",
    ReconciliationState.REJECTED: "Rejected",
    ReconciliationState.STALE: "Needs Review",
    ReconciliationState.BLOCKED: "Unresolved",
}

@dataclass(frozen=True, slots=True)
class RelationshipView:
    relationship: str
    target_name: str
    target_canonical_id: str


@dataclass(frozen=True, slots=True)
class EnterpriseEntityView:
    canonical_id: str
    name: str
    entity_type: str
    entity_type_label: str
    source_count: int
    sources: tuple[str, ...]
    governance_state: str
    relationships: tuple[RelationshipView, ...]


@dataclass(frozen=True, slots=True)
class EnterpriseContextView:
    counts: tuple[tuple[str, int], ...]
    entities: tuple[EnterpriseEntityView, ...]
    empty_message: str = (
        "No governed enterprise entities are available from this evidence yet."
    )


@dataclass(frozen=True, slots=True)
class ReconciliationViewItem:
    canonical_id: str | None
    canonical_name: str
    entity_type: str
    status: str
    sources: tuple[str, ...]
    match_basis: str
    conflicts: tuple[tuple[str, tuple[tuple[str, str], ...]], ...] = ()
    proposal_fingerprint: str | None = None
    valid_targets: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True, slots=True)
class ReconciliationView:
    items: tuple[ReconciliationViewItem, ...]
    source_count: int
    empty_message: str


def build_enterprise_context(
    entities: Iterable[Any],
    relationships: Iterable[Any] = (),
    bindings: Iterable[Any] = (),
    *,
    prospect_id: str | None = None,
    analysis_id: str | None = None,
) -> EnterpriseContextView:
    """Project canonical entities without interpreting source values."""
    scoped = tuple(
        entity
        for entity in entities
        if entity.entity_type in ENTITY_LABELS
        and _entity_in_scope(entity, prospect_id=prospect_id, analysis_id=analysis_id)
    )
    by_id = {entity.id: entity for entity in scoped}
    binding_sources: dict[str, set[str]] = {}
    for binding in bindings:
        binding_sources.setdefault(binding.canonical_entity_id, set()).add(
            _source_label(binding.source_system)
        )
    edges: dict[str, list[RelationshipView]] = {}
    for relationship in relationships:
        source = by_id.get(relationship.source_entity_id)
        target = by_id.get(relationship.target_entity_id)
        if source is None or target is None:
            continue
        label = RELATIONSHIP_LABELS.get(
            relationship.relationship_type.value,
            relationship.relationship_type.value.replace("_", " "),
        )
        edges.setdefault(source.canonical_id, []).append(
            RelationshipView(label, target.display_name, target.canonical_id)
        )
    views = []
    for entity in sorted(scoped, key=lambda item: (item.entity_type.value, item.display_name)):
        sources = set(binding_sources.get(entity.canonical_id, ()))
        if entity.source_system:
            sources.add(_source_label(entity.source_system))
        views.append(
            EnterpriseEntityView(
                entity.canonical_id,
                entity.display_name,
                entity.entity_type.value,
                ENTITY_SINGULAR_LABELS[entity.entity_type],
                len(sources),
                tuple(sorted(sources)),
                "Governed",
                tuple(
                    sorted(
                        edges.get(entity.canonical_id, ()),
                        key=lambda item: item.relationship,
                    )
                ),
            )
        )
    counts = tuple(
        (label, sum(entity.entity_type is entity_type for entity in scoped))
        for entity_type, label in ENTITY_LABELS.items()
        if any(entity.entity_type is entity_type for entity in scoped)
    )
    return EnterpriseContextView(counts, tuple(views))


def build_reconciliation_view(
    *,
    proposals: Iterable[Any] = (),
    bindings: Iterable[Any] = (),
    entities: Iterable[Any] = (),
    observations: Iterable[Any] = (),
) -> ReconciliationView:
    """Translate ACT-007 state while preserving its authority and ambiguity."""
    proposals = tuple(proposals)
    bindings = tuple(bindings)
    entities_by_id = {entity.canonical_id: entity for entity in entities}
    observation_rows = tuple(observations)
    all_sources = {
        _source_label(source)
        for source in (
            *(binding.source_system for binding in bindings),
            *(source for proposal in proposals for source in proposal.source_systems),
        )
    }
    items = []
    for proposal in proposals:
        canonical = entities_by_id.get(proposal.candidate_canonical_id)
        sources = tuple(sorted({_source_label(item) for item in proposal.source_systems}))
        items.append(
            ReconciliationViewItem(
                proposal.candidate_canonical_id,
                canonical.display_name
                if canonical is not None
                else _proposal_name(proposal, observation_rows),
                ENTITY_SINGULAR_LABELS.get(proposal.entity_type, proposal.entity_type.value),
                RECONCILIATION_LABELS[proposal.state],
                sources,
                _match_basis(proposal),
                _conflict_values(proposal, observation_rows),
                proposal.proposal_fingerprint,
                tuple(
                    sorted(
                        (
                            entity.canonical_id,
                            entity.display_name,
                        )
                        for entity in entities_by_id.values()
                        if entity.entity_type is proposal.entity_type
                    )
                ),
            )
        )
    proposed_ids = {item.canonical_id for item in items}
    for canonical_id in sorted({item.canonical_entity_id for item in bindings} - proposed_ids):
        canonical = entities_by_id.get(canonical_id)
        related = tuple(item for item in bindings if item.canonical_entity_id == canonical_id)
        items.append(
            ReconciliationViewItem(
                canonical_id,
                canonical.display_name if canonical is not None else canonical_id,
                ENTITY_SINGULAR_LABELS.get(canonical.entity_type, canonical.entity_type.value)
                if canonical is not None
                else "Enterprise Object",
                "Matched",
                tuple(sorted({_source_label(item.source_system) for item in related})),
                "Governed source identities resolve to the same canonical object.",
                valid_targets=(),
            )
        )
    empty = (
        "Reconciliation becomes available when multiple governed evidence sources describe "
        "the same enterprise environment."
        if len(all_sources) < 2
        else "No governed cross-source reconciliation is available yet."
    )
    return ReconciliationView(tuple(items), len(all_sources), empty)


def confirm_reconciliation(
    service, proposal, *, canonical_id: str, authorization, reason: str
):
    return service.confirm_match(
        proposal,
        canonical_id=canonical_id,
        authorization=authorization,
        reason=reason,
    )


def reject_reconciliation(service, proposal, *, authorization, reason: str):
    return service.reject_match(
        proposal, authorization=authorization, reason=reason
    )


def persist_production_views(lifecycle, scope: LifecycleScope, context, reconciliation):
    """Persist presentation-neutral snapshots for restart reconstruction."""
    lifecycle.put(
        "production_workflow_view",
        scope.analysis_id,
        scope,
        payload={"context": asdict(context), "reconciliation": asdict(reconciliation)},
        reason="ACT-010B production workflow snapshot",
    )


def load_production_views(lifecycle, scope: LifecycleScope):
    record = lifecycle.get("production_workflow_view", scope.analysis_id, scope)
    payload = record.payload
    return _context_from_payload(payload["context"]), _reconciliation_from_payload(
        payload["reconciliation"]
    )


def _entity_in_scope(entity, *, prospect_id, analysis_id):
    act006 = entity.metadata.get("act006", {})
    if prospect_id is not None and act006.get("prospect_id") != prospect_id:
        return False
    if analysis_id is not None and act006.get("analysis_id") != analysis_id:
        return False
    return True


def _match_basis(proposal):
    labels = {
        "native_identifier": "The sources share a governed native identifier.",
        "canonical_identity": "The sources reference the same canonical object.",
        "cross_reference": "A governed cross-reference connects these source identities.",
        "composite_natural_key": "Governed identity fields resolve to the same object.",
        "governed_alias": "A governed alias resolves these records to the same object.",
        "human_confirmed": "An authorized reviewer confirmed this match.",
    }
    if proposal.state is ReconciliationState.POSSIBLE_MATCH:
        return "Similar names are present, but no authoritative identity has been confirmed."
    if proposal.state is ReconciliationState.CONFLICT:
        return "Conflicting governed evidence requires review."
    return labels.get(
        proposal.match_method,
        proposal.reason or "No authoritative cross-source identity is currently available.",
    )


def _conflict_values(proposal, observations):
    result = []
    relevant = tuple(
        row
        for row in observations
        if row.scope == proposal.scope and row.entity_type is proposal.entity_type
    )
    for field in proposal.conflicts:
        values = tuple(
            sorted(
                {
                    (_source_label(row.source_system), str(row.normalized_attributes[field]))
                    for row in relevant
                    if row.normalized_attributes.get(field) not in (None, "")
                }
            )
        )
        result.append((field.replace("_", " ").title(), values))
    return tuple(result)


def _proposal_name(proposal, observations):
    names = {
        str(row.normalized_attributes.get("name") or "").strip()
        for row in observations
        if row.scope == proposal.scope and row.entity_type is proposal.entity_type
    }
    names.discard("")
    if len(names) == 1:
        return names.pop()
    return "Unresolved object"


def _source_label(value):
    normalized = str(value or "Unknown source").replace("_", " ").strip()
    acronyms = {"aws": "AWS", "cmdb": "CMDB", "gcp": "GCP", "saas": "SaaS"}
    return acronyms.get(normalized.casefold(), normalized.title())


def _context_from_payload(payload):
    entities = tuple(
        EnterpriseEntityView(
            **{
                **item,
                "sources": tuple(item["sources"]),
                "relationships": tuple(RelationshipView(**row) for row in item["relationships"]),
            }
        )
        for item in payload["entities"]
    )
    return EnterpriseContextView(tuple(tuple(item) for item in payload["counts"]), entities)


def _reconciliation_from_payload(payload):
    items = tuple(
        ReconciliationViewItem(
            **{
                **item,
                "sources": tuple(item["sources"]),
                "conflicts": tuple(
                    (field, tuple(tuple(value) for value in values))
                    for field, values in item["conflicts"]
                ),
                "valid_targets": tuple(tuple(value) for value in item["valid_targets"]),
            }
        )
        for item in payload["items"]
    )
    return ReconciliationView(items, payload["source_count"], payload["empty_message"])
