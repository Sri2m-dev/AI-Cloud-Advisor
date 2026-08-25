"""PUE-003 confirmation lifecycle over PUE-002 discovery results only."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone

from universal_evidence.contracts import ConfirmationState
from universal_evidence.governance.audit import InMemoryAuditSink
from universal_evidence.governance.fingerprints import fingerprint
from universal_evidence.governance.models import (
    ActorType,
    AuditEvent,
    ConfirmationActor,
    ConfirmationRequest,
    ConfirmationRequirement,
    DecisionScope,
    DriftResult,
    EffectiveSemanticMapping,
    GovernanceDecisionProvenance,
    MappingDecision,
    MappingDecisionHistory,
    MappingDecisionState,
)
from universal_evidence.governance.policy import GovernancePolicy
from universal_evidence.governance.repository import InMemoryMappingDecisionRepository
from universal_evidence.semantic.concepts import DEFAULT_CONCEPT_REGISTRY
from universal_evidence.semantic.models import ColumnDiscoveryResult, FileDiscoveryResult
from universal_evidence.semantic.registry import ConceptRegistry


class ConfirmationService:
    def __init__(
        self,
        *,
        repository: InMemoryMappingDecisionRepository | None = None,
        audit: InMemoryAuditSink | None = None,
        policy: GovernancePolicy | None = None,
        registry: ConceptRegistry = DEFAULT_CONCEPT_REGISTRY,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.repository = repository or InMemoryMappingDecisionRepository()
        self.audit = audit or InMemoryAuditSink()
        self.policy = policy or GovernancePolicy()
        self.registry = registry
        self.clock = clock or (lambda: datetime.now(timezone.utc))

    @staticmethod
    def _column(
        discovery: FileDiscoveryResult, column_reference: str
    ) -> ColumnDiscoveryResult:
        try:
            return next(
                item
                for item in discovery.columns
                if item.source_column_reference == column_reference
            )
        except StopIteration as exc:
            raise ValueError("column does not belong to discovery result") from exc

    @staticmethod
    def _scope(column: ColumnDiscoveryResult) -> DecisionScope:
        provenance = column.provenance
        return DecisionScope(
            provenance.analysis_id,
            provenance.prospect_id,
            provenance.organization_id,
            provenance.tenant_id,
            provenance.source_id,
            provenance.file_id,
            provenance.sheet_id,
            provenance.column_id,
        )

    def evaluate_confirmation_requirement(
        self, column: ColumnDiscoveryResult
    ) -> ConfirmationRequirement:
        required = self.policy.requires_confirmation(column)
        reasons = column.confirmation_reasons
        if required and not reasons:
            reasons = ("governance policy requires explicit confirmation",)
        return ConfirmationRequirement(
            ConfirmationState.REQUIRED if required else ConfirmationState.NOT_REQUIRED,
            reasons,
            self.policy.version,
        )

    def request_confirmation(
        self,
        discovery: FileDiscoveryResult,
        column_reference: str,
        semantic_concept_id: str,
    ) -> ConfirmationRequest:
        column = self._column(discovery, column_reference)
        scope = self._scope(column)
        if self.repository.effective(scope) is not None:
            raise ValueError("an effective mapping cannot transition back to pending")
        candidate = self._candidate(column, semantic_concept_id)
        requirement = self.evaluate_confirmation_requirement(column)
        if requirement.state is not ConfirmationState.REQUIRED:
            raise ValueError("candidate does not require a confirmation request")
        actor = ConfirmationActor(
            "pue-confirmation-service",
            "pue-confirmation-service",
            "system",
            ActorType.SYSTEM,
        )
        request_fingerprint = fingerprint(
            scope.key,
            column.discovery_id,
            semantic_concept_id,
            discovery.semantic_fingerprint,
            self.policy.version,
        )
        request = ConfirmationRequest(
            "request-" + request_fingerprint[:24],
            request_fingerprint,
            column.discovery_id,
            scope,
            semantic_concept_id,
            ConfirmationState.PENDING,
            actor,
            self.clock(),
            column.classifier_version,
            column.ontology_version,
            self.policy.version,
        )
        saved = self.repository.save_request(request)
        if saved is request:
            self._audit("CONFIRMATION_REQUESTED", None, saved, actor, None, None)
        _ = candidate
        return saved

    def auto_accept(
        self, discovery: FileDiscoveryResult, column_reference: str
    ) -> MappingDecision:
        column = self._column(discovery, column_reference)
        if not self.policy.permits_auto_accept(column):
            raise ValueError("governance policy does not permit automatic acceptance")
        actor = ConfirmationActor(
            "pue-governance-policy",
            "pue-governance-policy",
            "policy_engine",
            ActorType.POLICY_ENGINE,
        )
        return self._decide(
            discovery,
            column,
            column.candidates[0].semantic_concept_id,
            MappingDecisionState.AUTO_ACCEPTED,
            ConfirmationState.NOT_REQUIRED,
            actor,
            None,
        )

    def confirm_mapping(
        self,
        discovery: FileDiscoveryResult,
        column_reference: str,
        semantic_concept_id: str,
        *,
        actor: ConfirmationActor,
        reason: str | None = None,
    ) -> MappingDecision:
        self.policy.authorize("confirm", actor.actor_role)
        self._require_human(actor)
        column = self._column(discovery, column_reference)
        self._require_pending(discovery, column, semantic_concept_id)
        return self._decide(
            discovery,
            column,
            semantic_concept_id,
            MappingDecisionState.CONFIRMED,
            ConfirmationState.CONFIRMED,
            actor,
            reason,
        )

    def reject_mapping(
        self,
        discovery: FileDiscoveryResult,
        column_reference: str,
        semantic_concept_id: str,
        *,
        actor: ConfirmationActor,
        reason: str | None,
    ) -> MappingDecision:
        self.policy.authorize("reject", actor.actor_role)
        self._require_human(actor)
        if self.policy.reject_reason_required and not str(reason or "").strip():
            raise ValueError("rejection reason is required by policy")
        column = self._column(discovery, column_reference)
        self._require_pending(discovery, column, semantic_concept_id)
        return self._decide(
            discovery,
            column,
            semantic_concept_id,
            MappingDecisionState.REJECTED,
            ConfirmationState.REJECTED,
            actor,
            reason,
        )

    def override_mapping(
        self,
        discovery: FileDiscoveryResult,
        column_reference: str,
        selected_concept_id: str,
        *,
        actor: ConfirmationActor,
        reason: str | None,
    ) -> MappingDecision:
        self.policy.authorize("override", actor.actor_role)
        self._require_human(actor)
        if self.policy.override_reason_required and not str(reason or "").strip():
            raise ValueError("override reason is required by policy")
        self._require_concept(selected_concept_id)
        column = self._column(discovery, column_reference)
        return self._decide(
            discovery,
            column,
            selected_concept_id,
            MappingDecisionState.OVERRIDDEN,
            ConfirmationState.OVERRIDDEN,
            actor,
            reason,
        )

    def expire_mapping(
        self,
        discovery: FileDiscoveryResult,
        column_reference: str,
        *,
        actor: ConfirmationActor,
    ) -> MappingDecision:
        column = self._column(discovery, column_reference)
        effective = self.repository.effective(self._scope(column))
        if effective is None:
            raise ValueError("no effective mapping exists to expire")
        return self._decide(
            discovery,
            column,
            effective.semantic_concept_id,
            MappingDecisionState.EXPIRED,
            ConfirmationState.REJECTED,
            actor,
            "analysis retention expired",
        )

    def get_decision_history(
        self, column: ColumnDiscoveryResult, *, actor: ConfirmationActor
    ) -> MappingDecisionHistory:
        self.policy.authorize("view", actor.actor_role)
        return self.repository.history(self._scope(column))

    def get_effective_mapping(
        self,
        column: ColumnDiscoveryResult,
        *,
        actor: ConfirmationActor,
    ) -> EffectiveSemanticMapping | None:
        self.policy.authorize("view", actor.actor_role)
        decision = self.repository.effective(self._scope(column))
        if decision is None:
            return None
        confidence = next(
            (
                item.confidence.score
                for item in column.candidates
                if item.semantic_concept_id == decision.semantic_concept_id
            ),
            None,
        )
        return EffectiveSemanticMapping(
            decision.scope,
            decision.semantic_concept_id,
            decision.decision_state,
            decision.decision_id,
            confidence,
            decision.actor,
            decision.provenance,
        )

    def detect_drift(
        self, decision: MappingDecision, discovery: FileDiscoveryResult
    ) -> DriftResult:
        return DriftResult(
            decision.provenance.semantic_fingerprint
            != discovery.semantic_fingerprint,
            decision.provenance.classifier_version != discovery.classifier_version,
            decision.provenance.ontology_version != discovery.ontology_version,
            decision.provenance.discovery_policy_version != discovery.policy_version
            or decision.provenance.governance_policy_version != self.policy.version,
        )

    def _decide(
        self,
        discovery: FileDiscoveryResult,
        column: ColumnDiscoveryResult,
        concept_id: str,
        state: MappingDecisionState,
        confirmation: ConfirmationState,
        actor: ConfirmationActor,
        reason: str | None,
    ) -> MappingDecision:
        self._require_concept(concept_id)
        scope = self._scope(column)
        previous = self.repository.effective(scope)
        history = self.repository.history(scope).decisions
        if history:
            last = history[-1]
            repeated = (
                last.decision_state is state
                and last.semantic_concept_id == concept_id
                and last.actor == actor
                and last.reason == reason
            )
            if state in {
                MappingDecisionState.AUTO_ACCEPTED,
                MappingDecisionState.CONFIRMED,
                MappingDecisionState.REJECTED,
            } and not repeated:
                raise ValueError(
                    "a completed mapping requires an explicit override or expiry"
                )
        decision_timestamp = self.clock()
        provenance = GovernanceDecisionProvenance(
            column.discovery_id,
            discovery.semantic_fingerprint,
            column.provenance.structural_profile_fingerprint,
            column.classifier_version,
            column.ontology_version,
            column.policy_version,
            self.policy.version,
        )
        ranking = tuple(
            (item.semantic_concept_id, item.confidence.score)
            for item in column.candidates
        )
        decision_fingerprint = fingerprint(
            scope.key,
            concept_id,
            state,
            actor.actor_id,
            actor.actor_type,
            discovery.semantic_fingerprint,
            column.classifier_version,
            column.ontology_version,
            self.policy.version,
            reason,
        )
        decision = MappingDecision(
            "decision-" + decision_fingerprint[:24],
            decision_fingerprint,
            scope,
            concept_id,
            state,
            confirmation,
            actor,
            decision_timestamp,
            reason,
            ranking,
            provenance,
            previous.decision_id if previous else None,
            decision_timestamp
            if state
            in {
                MappingDecisionState.AUTO_ACCEPTED,
                MappingDecisionState.CONFIRMED,
                MappingDecisionState.OVERRIDDEN,
            }
            else None,
        )
        if previous is not None and state is MappingDecisionState.OVERRIDDEN:
            superseded_fingerprint = fingerprint(
                previous.decision_id,
                decision.decision_id,
                MappingDecisionState.SUPERSEDED,
            )
            superseded = MappingDecision(
                "decision-" + superseded_fingerprint[:24],
                superseded_fingerprint,
                scope,
                previous.semantic_concept_id,
                MappingDecisionState.SUPERSEDED,
                previous.confirmation_state,
                actor,
                decision_timestamp,
                reason,
                previous.original_candidate_ranking,
                previous.provenance,
                previous.decision_id,
                previous.effective_from,
                decision_timestamp,
            )
            saved_superseded = self.repository.append(superseded)
            if saved_superseded is superseded:
                self._audit(
                    "MAPPING_SUPERSEDED",
                    superseded,
                    None,
                    actor,
                    previous,
                    reason,
                )
        saved = self.repository.append(decision)
        if saved is decision:
            event = {
                MappingDecisionState.AUTO_ACCEPTED: "MAPPING_AUTO_ACCEPTED",
                MappingDecisionState.CONFIRMED: "MAPPING_CONFIRMED",
                MappingDecisionState.REJECTED: "MAPPING_REJECTED",
                MappingDecisionState.OVERRIDDEN: "MAPPING_OVERRIDDEN",
                MappingDecisionState.EXPIRED: "MAPPING_EXPIRED",
            }[state]
            self._audit(event, saved, None, actor, previous, reason)
        return saved

    def _require_pending(
        self,
        discovery: FileDiscoveryResult,
        column: ColumnDiscoveryResult,
        concept_id: str,
    ) -> None:
        request_fingerprint = fingerprint(
            self._scope(column).key,
            column.discovery_id,
            concept_id,
            discovery.semantic_fingerprint,
            self.policy.version,
        )
        request = self.repository.find_request(request_fingerprint)
        if request is None or request.confirmation_state is not ConfirmationState.PENDING:
            raise ValueError("a pending confirmation request is required")

    def _candidate(self, column: ColumnDiscoveryResult, concept_id: str):
        try:
            return next(
                item
                for item in column.candidates
                if item.semantic_concept_id == concept_id
            )
        except StopIteration as exc:
            raise ValueError("semantic candidate does not belong to column") from exc

    def _require_concept(self, concept_id: str) -> None:
        if not any(
            item.concept.concept_id == concept_id for item in self.registry.concepts
        ):
            raise ValueError("selected semantic concept is not ontology-approved")

    @staticmethod
    def _require_human(actor: ConfirmationActor) -> None:
        if actor.actor_type is not ActorType.HUMAN:
            raise PermissionError("human mapping actions require a human actor")

    def _audit(
        self,
        event_type: str,
        decision: MappingDecision | None,
        request: ConfirmationRequest | None,
        actor: ConfirmationActor,
        previous: MappingDecision | None,
        reason: str | None,
    ) -> None:
        subject = decision or request
        assert subject is not None
        self.audit.emit(
            AuditEvent(
                event_type,
                decision.decision_id if decision else None,
                request.request_id if request else None,
                subject.scope,
                subject.semantic_concept_id,
                actor,
                decision.decision_timestamp
                if decision
                else request.created_at,
                previous.decision_id if previous else None,
                reason,
                subject.provenance.classifier_version
                if decision
                else request.classifier_version,
                subject.provenance.ontology_version
                if decision
                else request.ontology_version,
                self.policy.version,
            )
        )
