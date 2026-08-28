"""ACT-007 cross-source identity reconciliation over the existing registry."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from types import MappingProxyType
from typing import Any, Iterable, Mapping

from data_fabric.contracts import EntityType
from data_fabric.foundation import TenantContext
from universal_evidence.activation import ActivationStage, RoutingReason
from universal_evidence.normalization.fingerprints import fingerprint


class ReconciliationState(str, Enum):
    EXACT_MATCH = "EXACT_MATCH"
    CONFIRMED_MATCH = "CONFIRMED_MATCH"
    POSSIBLE_MATCH = "POSSIBLE_MATCH"
    CONFLICT = "CONFLICT"
    UNRESOLVED = "UNRESOLVED"
    BLOCKED = "BLOCKED"
    STALE = "STALE"
    REJECTED = "REJECTED"


class ReconciliationDecisionType(str, Enum):
    CONFIRM_MATCH = "CONFIRM_MATCH"
    REJECT_MATCH = "REJECT_MATCH"


@dataclass(frozen=True, slots=True)
class SourceIdentityObservation:
    """A governed source identity; it is never collapsed into a canonical ID."""

    source_system: str
    source_type: str
    source_identifier: str
    entity_type: EntityType | str
    normalized_attributes: Mapping[str, Any]
    organization_id: str
    tenant_id: str
    prospect_id: str
    analysis_id: str
    source_id: str
    file_id: str
    evidence_fingerprint: str
    mapping_decision_ids: tuple[str, ...] = ()
    normalization_references: tuple[str, ...] = ()
    materialization_reference: str | None = None
    governed_aliases: tuple[str, ...] = ()
    canonical_id: str | None = None
    stale: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "entity_type", EntityType(self.entity_type))
        object.__setattr__(
            self, "normalized_attributes", MappingProxyType(dict(self.normalized_attributes))
        )

    @property
    def scope(self) -> tuple[str, str, str, str]:
        return (self.organization_id, self.tenant_id, self.prospect_id, self.analysis_id)

    @property
    def identity_key(self) -> tuple[str, ...]:
        return (*self.scope, self.source_system, self.source_identifier, self.entity_type.value)


@dataclass(frozen=True, slots=True)
class ReconciliationProposal:
    proposal_id: str
    proposal_fingerprint: str
    scope: tuple[str, str, str, str]
    entity_type: EntityType
    source_identities: tuple[tuple[str, str, str], ...]
    candidate_canonical_id: str | None
    match_method: str | None
    match_keys: tuple[str, ...]
    supporting_observations: tuple[str, ...]
    source_systems: tuple[str, ...]
    authority_level: str
    conflicts: tuple[str, ...]
    mapping_decision_ids: tuple[str, ...]
    normalization_references: tuple[str, ...]
    materialization_references: tuple[str, ...]
    state: ReconciliationState
    reason: str | None = None


@dataclass(frozen=True, slots=True)
class ReconciliationDecision:
    decision_id: str
    decision_type: ReconciliationDecisionType
    proposal_fingerprint: str
    scope: tuple[str, str, str, str]
    candidate_canonical_id: str | None
    source_identities: tuple[tuple[str, str, str], ...]
    actor_id: str
    reason: str
    decided_at: datetime
    decision_fingerprint: str


@dataclass(frozen=True, slots=True)
class SourceIdentityBinding:
    binding_id: str
    binding_fingerprint: str
    scope: tuple[str, str, str, str]
    source_system: str
    source_identifier: str
    entity_type: EntityType
    canonical_entity_id: str
    decision_id: str | None
    authority_method: str
    evidence_references: tuple[str, ...]
    created_at: datetime


@dataclass(frozen=True, slots=True)
class ReconciliationReport:
    proposals: tuple[ReconciliationProposal, ...]
    bindings: tuple[SourceIdentityBinding, ...]
    decisions: tuple[ReconciliationDecision, ...]
    counts: Mapping[str, int]


@dataclass(frozen=True, slots=True)
class SourceAuthorityPolicy:
    """Optional field-level precedence; absent authority leaves conflicts visible."""

    field_priorities: Mapping[str, tuple[str, ...]] = field(
        default_factory=lambda: MappingProxyType({})
    )

    def winner(self, field: str, sources: Iterable[str]) -> str | None:
        priority = self.field_priorities.get(field, ())
        return next((source for source in priority if source in sources), None)


class GovernedIdentityReconciliationService:
    """Cross-source binding authority; canonical entity creation stays in ACT-006."""

    def __init__(
        self,
        registry,
        *,
        activation_resolver=None,
        authority_policy: SourceAuthorityPolicy | None = None,
        audit_sink=None,
    ) -> None:
        self.registry = registry
        self.activation_resolver = activation_resolver
        self.authority_policy = authority_policy or SourceAuthorityPolicy()
        self.audit_sink = audit_sink
        self._bindings: dict[tuple[str, ...], SourceIdentityBinding] = {}
        self._cross_references: dict[tuple[str, ...], str] = {}
        self._decisions: dict[str, ReconciliationDecision] = {}

    def reconcile(
        self,
        observations: Iterable[SourceIdentityObservation],
        *,
        context: TenantContext,
        activation=None,
        decision_overrides: Mapping[str, ReconciliationDecision] | None = None,
    ) -> ReconciliationReport:
        rows = tuple(observations)
        self._validate_scope(rows, context)
        activation = self._resolve_activation(rows, activation)
        blocked_reason = self._blocked_reason(activation)
        existing_binding_ids = {item.binding_id for item in self._bindings.values()}
        proposals = tuple(
            self._proposal(group, context, blocked_reason, decision_overrides or {})
            for group in self._groups(rows)
        )
        for proposal in proposals:
            first = next(
                row
                for row in rows
                if row.scope == proposal.scope and row.entity_type is proposal.entity_type
            )
            self._audit(f"ACT007_RECONCILIATION_{proposal.state.value}", first, proposal)
        bindings = []
        for proposal in proposals:
            if proposal.state not in {
                ReconciliationState.EXACT_MATCH,
                ReconciliationState.CONFIRMED_MATCH,
            }:
                continue
            decision = (decision_overrides or {}).get(
                proposal.proposal_fingerprint
            ) or self._decisions.get(proposal.proposal_fingerprint)
            for row in self._proposal_rows(proposal, rows):
                binding = self._bind(row, proposal, decision, blocked_reason)
                if binding is not None:
                    bindings.append(binding)
                    self._audit("ACT007_SOURCE_IDENTITY_BOUND", row, proposal)
        counts = {state.value.lower(): 0 for state in ReconciliationState}
        for proposal in proposals:
            counts[proposal.state.value.lower()] += 1
        counts["bindings_created"] = sum(
            1 for item in bindings if item.binding_id not in existing_binding_ids
        )
        counts["bindings_reused"] = len(bindings) - counts["bindings_created"]
        return ReconciliationReport(
            proposals, tuple(bindings), tuple(self._decisions.values()), MappingProxyType(counts)
        )

    def confirm_match(
        self,
        proposal: ReconciliationProposal,
        *,
        canonical_id: str,
        actor_id: str,
        reason: str,
    ) -> ReconciliationDecision:
        if not canonical_id.strip():
            raise ValueError("canonical_id is required for a confirmed match")
        entity = self.registry.get_entity(canonical_id)
        if entity.entity_type is not proposal.entity_type:
            raise ValueError("confirmed canonical entity type does not match proposal")
        if entity.organization_id != proposal.scope[0] or entity.tenant_id != proposal.scope[1]:
            raise ValueError("confirmed canonical entity crosses scope boundary")
        return self._record_decision(
            proposal, ReconciliationDecisionType.CONFIRM_MATCH, actor_id, reason, canonical_id
        )

    def reject_match(
        self, proposal: ReconciliationProposal, *, actor_id: str, reason: str
    ) -> ReconciliationDecision:
        return self._record_decision(
            proposal,
            ReconciliationDecisionType.REJECT_MATCH,
            actor_id,
            reason,
            proposal.candidate_canonical_id,
        )

    def register_cross_reference(
        self,
        left: SourceIdentityObservation,
        right: SourceIdentityObservation,
        *,
        canonical_id: str,
    ) -> str:
        if left.scope != right.scope or left.entity_type is not right.entity_type:
            raise ValueError("cross-reference scope and entity type must match")
        keys = (
            (*left.scope, left.source_system, left.source_identifier, left.entity_type.value),
            (*right.scope, right.source_system, right.source_identifier, right.entity_type.value),
        )
        if any(self._cross_references.get(key) not in (None, canonical_id) for key in keys):
            raise ValueError("source identity is already bound to another canonical entity")
        for key in keys:
            self._cross_references[key] = canonical_id
        return canonical_id

    def _proposal(self, group, context, blocked_reason, decisions):
        first = group[0]
        identities = tuple(
            sorted(
                (row.source_system, row.source_identifier, row.entity_type.value) for row in group
            )
        )
        evidence = tuple(sorted(row.evidence_fingerprint for row in group))
        keys = tuple(sorted(self._explicit_keys(group)))
        candidate, method, authority = self._candidate(group, context)
        conflicts = tuple(
            sorted(
                set(self._conflicts(group, candidate)).union(
                    self._binding_conflicts(group, candidate)
                )
            )
        )
        base = (
            first.scope,
            first.entity_type.value,
            identities,
            evidence,
            keys,
            candidate,
            method,
            conflicts,
        )
        proposal_fp = fingerprint(base)
        proposal_id = "act007-proposal-" + proposal_fp[:24]
        common = dict(
            proposal_id=proposal_id,
            proposal_fingerprint=proposal_fp,
            scope=first.scope,
            entity_type=first.entity_type,
            source_identities=identities,
            candidate_canonical_id=candidate,
            match_method=method,
            match_keys=keys,
            supporting_observations=tuple(
                f"{row.source_id}:{row.file_id}:{row.source_identifier}" for row in group
            ),
            source_systems=tuple(sorted({row.source_system for row in group})),
            authority_level=authority,
            conflicts=tuple(conflicts),
            mapping_decision_ids=tuple(
                sorted({item for row in group for item in row.mapping_decision_ids})
            ),
            normalization_references=tuple(
                sorted({item for row in group for item in row.normalization_references})
            ),
            materialization_references=tuple(
                sorted(
                    {
                        row.materialization_reference
                        for row in group
                        if row.materialization_reference
                    }
                )
            ),
        )
        if blocked_reason:
            return ReconciliationProposal(
                **common, state=ReconciliationState.BLOCKED, reason=blocked_reason
            )
        if any(row.stale for row in group):
            return ReconciliationProposal(
                **common, state=ReconciliationState.STALE, reason="source evidence is stale"
            )
        decision = decisions.get(proposal_fp) or self._decisions.get(proposal_fp)
        if decision is not None:
            if decision.proposal_fingerprint != proposal_fp:
                return ReconciliationProposal(
                    **common, state=ReconciliationState.STALE, reason="governance decision is stale"
                )
            if decision.decision_type is ReconciliationDecisionType.CONFIRM_MATCH:
                common["candidate_canonical_id"] = decision.candidate_canonical_id
                common["match_method"] = "human_confirmed"
                common["authority_level"] = "6"
                return ReconciliationProposal(
                    **common,
                    state=ReconciliationState.CONFIRMED_MATCH,
                    reason=decision.reason,
                )
            return ReconciliationProposal(
                **common,
                state=ReconciliationState.REJECTED,
                reason=decision.reason,
            )
        if conflicts:
            return ReconciliationProposal(
                **common,
                state=ReconciliationState.CONFLICT,
                reason="conflicting source descriptions require governance",
            )
        if candidate and method in {
            "canonical_identity",
            "native_identifier",
            "cross_reference",
            "composite_natural_key",
            "governed_alias",
        }:
            return ReconciliationProposal(**common, state=ReconciliationState.EXACT_MATCH)
        if len(group) > 1 and self._same_name_only(group):
            return ReconciliationProposal(
                **common,
                state=ReconciliationState.POSSIBLE_MATCH,
                reason="same name without authoritative identity",
            )
        return ReconciliationProposal(
            **common,
            state=ReconciliationState.UNRESOLVED,
            reason="no authoritative cross-source identity evidence",
        )

    def _candidate(self, group, context):
        entities = [
            entity
            for entity in self.registry.list_entities()
            if entity.entity_type is group[0].entity_type
            and entity.organization_id == context.organization_id
            and entity.tenant_id == context.tenant_id
        ]
        if group[0].prospect_id:
            entities = [
                entity
                for entity in entities
                if entity.metadata.get("act006", {}).get("prospect_id") == group[0].prospect_id
            ]
        for row in group:
            if row.canonical_id and any(
                entity.canonical_id == row.canonical_id for entity in entities
            ):
                return row.canonical_id, "canonical_identity", "1"
            cross = self._cross_references.get(
                (*row.scope, row.source_system, row.source_identifier, row.entity_type.value)
            )
            if cross and any(entity.canonical_id == cross for entity in entities):
                return cross, "cross_reference", "3"
        native = {row.source_identifier for row in group}
        for entity in entities:
            if entity.source_identifier in native and any(
                row.source_system == entity.source_system for row in group
            ):
                return entity.canonical_id, "native_identifier", "2"
        explicit = self._explicit_keys(group)
        candidates = [
            entity
            for entity in entities
            if explicit and explicit.intersection(self._entity_keys(entity))
        ]
        if len(candidates) == 1:
            return candidates[0].canonical_id, "composite_natural_key", "4"
        aliases = {self._norm(value) for row in group for value in row.governed_aliases}
        candidates = [
            entity for entity in entities if aliases and self._norm(entity.name) in aliases
        ]
        if len(candidates) == 1:
            return candidates[0].canonical_id, "governed_alias", "5"
        return None, None, "NONE"

    def _conflicts(self, group, candidate):
        if candidate is None:
            return ()
        fields: dict[str, set[tuple[str, Any]]] = {}
        for row in group:
            for key, value in row.normalized_attributes.items():
                if value not in (None, ""):
                    fields.setdefault(key, set()).add((row.source_system, value))
        conflicts = []
        for field_name, values in fields.items():
            if (
                len({value for _, value in values}) > 1
                and self.authority_policy.winner(field_name, [source for source, _ in values])
                is None
            ):
                conflicts.append(field_name)
        return tuple(sorted(conflicts))

    def _binding_conflicts(self, group, candidate):
        if candidate is None:
            return ()
        return tuple(
            "source_identity_binding"
            for row in group
            if (existing := self._bindings.get(row.identity_key)) is not None
            and existing.canonical_entity_id != candidate
        )

    def _bind(self, row, proposal, decision, blocked_reason):
        key = row.identity_key
        existing = self._bindings.get(key)
        if existing is not None:
            if existing.canonical_entity_id != proposal.candidate_canonical_id:
                return None
            return existing
        if blocked_reason or proposal.candidate_canonical_id is None:
            return None
        binding_fp = fingerprint(
            row.scope,
            row.source_system,
            row.source_identifier,
            row.entity_type.value,
            proposal.candidate_canonical_id,
            proposal.proposal_fingerprint,
        )
        binding = SourceIdentityBinding(
            "act007-binding-" + binding_fp[:24],
            binding_fp,
            row.scope,
            row.source_system,
            row.source_identifier,
            row.entity_type,
            proposal.candidate_canonical_id,
            decision.decision_id if decision else None,
            proposal.match_method or "confirmed",
            (row.evidence_fingerprint,),
            datetime.now(timezone.utc),
        )
        self._bindings[key] = binding
        return binding

    def _audit(self, event_type, observation, subject):
        if self.audit_sink is not None:
            self.audit_sink.record(
                event_type=event_type,
                actor_id="act-007",
                timestamp=datetime.now(timezone.utc),
                reason="ACT-007 governed reconciliation",
                scope_key=observation.scope,
                activation_id=None,
            )

    def _record_decision(self, proposal, decision_type, actor_id, reason, canonical_id):
        if not reason.strip():
            raise ValueError("reconciliation decision reason is required")
        decision_fp = fingerprint(
            decision_type.value, proposal.proposal_fingerprint, canonical_id, actor_id, reason
        )
        decision = ReconciliationDecision(
            "act007-decision-" + decision_fp[:24],
            decision_type,
            proposal.proposal_fingerprint,
            proposal.scope,
            canonical_id,
            proposal.source_identities,
            actor_id,
            reason,
            datetime.now(timezone.utc),
            decision_fp,
        )
        self._decisions[proposal.proposal_fingerprint] = decision
        return decision

    @staticmethod
    def _groups(rows):
        groups = {}
        for row in rows:
            groups.setdefault((row.scope, row.entity_type), []).append(row)
        return tuple(groups[key] for key in sorted(groups, key=str))

    @staticmethod
    def _proposal_rows(proposal, rows):
        return tuple(
            row
            for row in rows
            if row.scope == proposal.scope and row.entity_type is proposal.entity_type
        )

    @staticmethod
    def _explicit_keys(rows):
        keys = set()
        for row in rows:
            for name in (
                "resource_id",
                "cloud_resource_id",
                "application_id",
                "app_id",
                "ci_id",
                "contract_id",
                "license_id",
            ):
                value = row.normalized_attributes.get(name)
                if value not in (None, ""):
                    keys.add(f"{name}:{str(value).casefold()}")
        return keys

    @staticmethod
    def _entity_keys(entity):
        keys = {f"source_identifier:{entity.source_identifier.casefold()}"}
        field_by_type = {
            EntityType.CLOUD_RESOURCE: ("resource_id", "cloud_resource_id"),
            EntityType.APPLICATION: ("application_id", "app_id"),
            EntityType.BUSINESS_SERVICE: ("business_service_id", "service_id"),
            EntityType.OWNER: ("owner_id",),
            EntityType.COST_CENTER: ("cost_center_id",),
            EntityType.CONTRACT: ("contract_id",),
            EntityType.LICENSE: ("license_id",),
        }
        keys.update(
            f"{field}:{entity.source_identifier.casefold()}"
            for field in field_by_type.get(entity.entity_type, ())
        )
        keys.update(
            f"{key}:{str(value).casefold()}"
            for key, value in (entity.metadata.get("identity_keys") or {}).items()
        )
        return keys

    @staticmethod
    def _same_name_only(rows):
        names = {
            str(
                row.normalized_attributes.get("name")
                or row.normalized_attributes.get("application_name")
                or ""
            ).casefold()
            for row in rows
        }
        return (
            len(rows) > 1
            and len(names) == 1
            and "" not in names
            and not any(GovernedIdentityReconciliationService._explicit_keys([row]) for row in rows)
        )

    @staticmethod
    def _norm(value):
        return " ".join(str(value or "").casefold().split())

    @staticmethod
    def _validate_scope(rows, context):
        for row in rows:
            if row.organization_id != context.organization_id or row.tenant_id != context.tenant_id:
                raise ValueError("ACT-007 observation crosses organization or tenant boundary")

    def _resolve_activation(self, rows, activation):
        if activation is not None or self.activation_resolver is None or not rows:
            return activation
        from universal_evidence.activation import ActivationScope, ScopeLevel

        first = rows[0]
        return self.activation_resolver.resolve(
            ActivationScope(
                ScopeLevel.ANALYSIS,
                organization_id=first.organization_id,
                tenant_id=first.tenant_id,
                prospect_id=first.prospect_id,
                analysis_id=first.analysis_id,
            )
        )

    @staticmethod
    def _blocked_reason(activation):
        if activation is None:
            return None
        if activation.stage is ActivationStage.SHADOW_ONLY:
            return "ACT-C1 shadow mode blocks reconciliation binding"
        if RoutingReason.KILL_SWITCH_ACTIVE in activation.reason_codes:
            return "ACT-C1 kill switch blocks reconciliation binding"
        if activation.stage < ActivationStage.CAPABILITY_VISIBLE:
            return "ACT-C1 activation does not authorize reconciliation"
        return None
