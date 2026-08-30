"""ACT-003 adapter reusing certified semantic discovery and mapping governance."""

from __future__ import annotations

from universal_evidence.activation import (
    ActivationScope,
    ActivationStage,
    RoutingReason,
    ScopeLevel,
)
from universal_evidence.governance import MappingDecisionState
from universal_evidence.pilot.semantic_view_models import (
    SemanticCandidateViewModel,
    SemanticDecisionViewModel,
    SemanticGovernanceViewModel,
    SemanticMappingStatus,
    SemanticMappingViewModel,
)
from universal_evidence.semantic import discover_semantics


class PilotSemanticGovernanceService:
    def __init__(
        self,
        *,
        activation_resolver,
        confirmation_service,
        telemetry,
        audit_sink=None,
        clock=None,
        operations=None,
        operation_context=None,
    ) -> None:
        self.activation_resolver = activation_resolver
        self.confirmation_service = confirmation_service
        self.telemetry = telemetry
        self.audit_sink = audit_sink
        self.clock = clock
        self.operations = operations
        self.operation_context = operation_context
        self._discovery_cache = {}

    def discovery(self, admission):
        cached = self._discovery_cache.get(admission.fingerprint)
        if cached is None:
            cached = discover_semantics(admission.profile)
            self._discovery_cache[admission.fingerprint] = cached
        return cached

    def experience(self, admission, *, actor):
        activation = self.activation_resolver.resolve(
            ActivationScope(
                ScopeLevel.ANALYSIS,
                organization_id=admission.scope.organization_id,
                tenant_id=admission.scope.tenant_id,
                prospect_id=admission.scope.prospect_id,
                analysis_id=admission.scope.analysis_id,
            )
        )
        if (
            RoutingReason.KILL_SWITCH_ACTIVE in activation.reason_codes
            or activation.stage is ActivationStage.SHADOW_ONLY
        ):
            return None
        discovery = self.discovery(admission)
        mappings = tuple(self._mapping(discovery, column, actor) for column in discovery.columns)
        self.telemetry.increment(
            "semantic_candidates_shown",
            admission.scope.key,
            sum(len(item.candidates) for item in mappings),
        )
        self.telemetry.increment(
            "confirmation_required_count",
            admission.scope.key,
            sum(item.status is SemanticMappingStatus.CONFIRMATION_REQUIRED for item in mappings),
        )
        self.telemetry.increment(
            "ambiguous_mapping_count",
            admission.scope.key,
            sum(item.ambiguous for item in mappings),
        )
        self.telemetry.increment(
            "stale_mapping_count",
            admission.scope.key,
            sum(item.stale for item in mappings),
        )
        if self.audit_sink is not None and self.clock is not None:
            self.audit_sink.record(
                event_type="PUE_MAPPING_CANDIDATES_VIEWED",
                actor_id=actor.actor_id,
                timestamp=self.clock(),
                reason="ACT-003 semantic governance surface viewed",
                scope_key=admission.scope.key,
                activation_id=(
                    activation.config.activation_id if activation.config else None
                ),
            )
        return SemanticGovernanceViewModel(
            admission.scope.analysis_id,
            discovery.semantic_fingerprint,
            mappings,
            sum(len(item.candidates) for item in mappings),
            sum(item.status is SemanticMappingStatus.CONFIRMATION_REQUIRED for item in mappings),
            sum(item.ambiguous for item in mappings),
            sum(item.effective_concept_id is not None and not item.stale for item in mappings),
        )

    def confirm(self, admission, column_reference, concept_id, *, actor):
        discovery = self.discovery(admission)
        column = next(
            item
            for item in discovery.columns
            if item.source_column_reference == column_reference
        )
        effective = self.confirmation_service.get_effective_mapping(column, actor=actor)
        if (
            effective is not None
            and effective.semantic_concept_id == concept_id
            and effective.decision_state is MappingDecisionState.CONFIRMED
            and effective.actor == actor
        ):
            return next(
                item
                for item in self.confirmation_service.get_decision_history(
                    column, actor=actor
                ).decisions
                if item.decision_id == effective.decision_id
            )
        self._operation("MAPPING_CONFIRMED", admission, actor, column_reference)
        self.confirmation_service.request_confirmation(
            discovery, column_reference, concept_id
        )
        decision = self.confirmation_service.confirm_mapping(
            discovery, column_reference, concept_id, actor=actor
        )
        self.telemetry.increment("mapping_confirmed_count", admission.scope.key)
        return decision

    def reject(self, admission, column_reference, concept_id, *, actor, reason):
        self._operation(
            "MAPPING_REJECTED", admission, actor, column_reference, attributes={"reason": reason}
        )
        discovery = self.discovery(admission)
        self.confirmation_service.request_confirmation(
            discovery, column_reference, concept_id
        )
        decision = self.confirmation_service.reject_mapping(
            discovery,
            column_reference,
            concept_id,
            actor=actor,
            reason=reason,
        )
        self.telemetry.increment("mapping_rejected_count", admission.scope.key)
        return decision

    def override(self, admission, column_reference, concept_id, *, actor, reason):
        self._operation(
            "MAPPING_OVERRIDDEN", admission, actor, column_reference, attributes={"reason": reason}
        )
        decision = self.confirmation_service.override_mapping(
            self.discovery(admission),
            column_reference,
            concept_id,
            actor=actor,
            reason=reason,
        )
        self.telemetry.increment("mapping_overridden_count", admission.scope.key)
        return decision

    def _operation(self, event_type, admission, actor, mapping_reference, *, attributes=None):
        from universal_evidence.operations import (
            GovernedEventType,
            observe,
            workflow_context,
        )

        observe(
            self.operations,
            GovernedEventType(event_type),
            workflow_context(self.operation_context, admission.scope, actor=actor),
            references={
                "evidence": admission.evidence_fingerprint,
                "governance": str(mapping_reference),
            },
            attributes={"phase": "AUTHORIZED", **(attributes or {})},
        )

    def _mapping(self, discovery, column, actor):
        history = self.confirmation_service.get_decision_history(column, actor=actor)
        effective = self.confirmation_service.get_effective_mapping(column, actor=actor)
        stale = False
        if effective is not None:
            decision = next(
                item for item in history.decisions if item.decision_id == effective.decision_id
            )
            stale = self.confirmation_service.detect_drift(
                decision, discovery
            ).requires_reevaluation
        status = self._status(column, history.decisions, effective, stale)
        definitions = {
            item.concept.concept_id: item
            for item in self.confirmation_service.registry.concepts
        }
        candidates = tuple(
            SemanticCandidateViewModel(
                item.semantic_concept_id,
                _display_name(item.semantic_concept_id),
                round(item.confidence.score * 100),
                item.confidence.band.value.title(),
                item.explanation,
                item.risk.value,
            )
            for item in column.candidates
        )
        ambiguous = any("ambiguity gap" in reason for reason in column.confirmation_reasons)
        actions = (
            ["confirm", "reject"]
            if status is SemanticMappingStatus.CONFIRMATION_REQUIRED
            and not history.decisions
            else []
        )
        if actor.actor_role in self.confirmation_service.policy.override_roles:
            actions.append("override")
        effective_id = effective.semantic_concept_id if effective and not stale else None
        return SemanticMappingViewModel(
            column.source_column_reference,
            column.original_header,
            status,
            candidates,
            effective_id,
            _display_name(effective_id) if effective_id else None,
            _status_reason(column, history.decisions, stale),
            ambiguous,
            stale,
            tuple(actions),
            tuple(
                (concept_id, _display_name(concept_id))
                for concept_id in sorted(definitions)
            ),
            tuple(
                SemanticDecisionViewModel(
                    item.decision_id,
                    item.decision_state.value,
                    item.semantic_concept_id,
                    item.actor.actor_id,
                    item.actor.actor_role,
                    item.reason,
                    item.decision_timestamp.isoformat(),
                )
                for item in history.decisions
            ),
        )

    @staticmethod
    def _status(column, decisions, effective, stale):
        if stale:
            return SemanticMappingStatus.BLOCKED
        if effective is not None:
            return (
                SemanticMappingStatus.OVERRIDDEN
                if effective.decision_state is MappingDecisionState.OVERRIDDEN
                else SemanticMappingStatus.CONFIRMED
            )
        if decisions:
            last = decisions[-1].decision_state
            if last is MappingDecisionState.REJECTED:
                return SemanticMappingStatus.REJECTED
            if last is MappingDecisionState.EXPIRED:
                return SemanticMappingStatus.EXPIRED
        if not column.candidates:
            return SemanticMappingStatus.OBSERVED
        if column.confirmation_state.value == "REQUIRED":
            return SemanticMappingStatus.CONFIRMATION_REQUIRED
        return SemanticMappingStatus.CANDIDATE


def _display_name(concept_id):
    if not concept_id:
        return None
    return concept_id.replace(".", " ").replace("_", " ").title()


def _status_reason(column, decisions, stale):
    if stale:
        return "The effective decision is stale under current discovery or governance versions."
    if decisions:
        last = decisions[-1]
        if last.decision_state is MappingDecisionState.REJECTED:
            return last.reason or "The candidate was rejected."
        if last.decision_state is MappingDecisionState.EXPIRED:
            return "The governed mapping expired."
    if column.confirmation_reasons:
        return "; ".join(column.confirmation_reasons)
    if column.candidates:
        return "A semantic candidate was observed; confidence is not authority."
    return "The source column was observed but no semantic candidate met policy thresholds."
