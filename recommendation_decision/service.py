"""Tenant-safe Recommendation lifecycle, Decision authority, and reconstruction."""

from __future__ import annotations

from dataclasses import asdict, replace
from datetime import datetime, timezone
from typing import Any

from data_fabric.foundation import DefaultDeterministicSerializer, TenantContext
from evidence_registry import (
    CaseRole,
    EvidencePackageStatus,
    InMemoryEvidenceRegistry,
)

from recommendation_decision.models import (
    Actor,
    ActorType,
    Alternative,
    Decision,
    DecisionDisposition,
    LifecycleEvent,
    Recommendation,
    RecommendationState,
)

_SERIALIZER = DefaultDeterministicSerializer()


class RecommendationDecisionError(ValueError):
    """Recommendation, evidence, authority, or lifecycle failure."""


class DecisionAuthorityRegistry:
    """Minimal adapter boundary over existing governed authorization capability."""

    def __init__(self) -> None:
        self._grants: set[tuple[str, str, str]] = set()

    def grant(self, context: TenantContext, actor_id: str) -> None:
        self._grants.add((context.organization_id, context.tenant_id, actor_id))

    def is_authorized(self, context: TenantContext, actor: Actor) -> bool:
        return (
            context.organization_id,
            context.tenant_id,
            actor.actor_id,
        ) in self._grants


class RecommendationDecisionService:
    """Persistence-neutral governed orchestration; it has no execution behavior."""

    def __init__(
        self,
        evidence_registry: InMemoryEvidenceRegistry,
        authority: DecisionAuthorityRegistry,
    ) -> None:
        self._evidence = evidence_registry
        self._authority = authority
        self._recommendations: dict[tuple[str, str, str, int], Recommendation] = {}
        self._current: dict[tuple[str, str, str], int] = {}
        self._decisions: dict[tuple[str, str, str], Decision] = {}
        self._events: list[LifecycleEvent] = []

    def create_recommendation(
        self,
        context: TenantContext,
        *,
        recommendation_id: str,
        finding: str,
        proposed_action: str,
        expected_outcome: str,
        alternatives: tuple[Alternative, ...],
        evidence_package_id: str,
        proposer: Actor,
        created_at: datetime | None = None,
        assumptions: tuple[str, ...] = (),
        risks: tuple[str, ...] = (),
        confidence: float | None = None,
        metadata: dict[str, Any] | None = None,
        supersedes_recommendation_id: str | None = None,
    ) -> Recommendation:
        package = self._approved_package(context, evidence_package_id)
        current_key = self._current_key(context, recommendation_id)
        if current_key in self._current:
            raise RecommendationDecisionError("recommendation id already exists")
        now = created_at or datetime.now(timezone.utc)
        lineage, provenance = self._evidence_refs(context, package)
        recommendation = Recommendation(
            recommendation_id=recommendation_id,
            organization_id=context.organization_id,
            tenant_id=context.tenant_id,
            version=1,
            finding=finding,
            proposed_action=proposed_action,
            expected_outcome=expected_outcome,
            alternatives=alternatives,
            evidence_package_id=package.package_id,
            evidence_package_hash=package.package_hash,
            proposer=proposer,
            state=RecommendationState.DRAFT,
            created_at=now,
            assumptions=assumptions,
            risks=risks,
            confidence=confidence,
            lineage_refs=lineage,
            provenance_refs=provenance,
            supersedes_recommendation_id=supersedes_recommendation_id,
            metadata=metadata or {},
        )
        self._store(recommendation)
        self._events.append(
            LifecycleEvent(
                recommendation_id,
                1,
                None,
                RecommendationState.DRAFT,
                proposer,
                now,
                "recommendation created",
            )
        )
        return recommendation

    def transition(
        self,
        context: TenantContext,
        recommendation_id: str,
        to_state: RecommendationState,
        *,
        actor: Actor,
        reason: str,
        occurred_at: datetime | None = None,
    ) -> Recommendation:
        current = self.get_recommendation(context, recommendation_id)
        target = RecommendationState(to_state)
        allowed = {
            RecommendationState.DRAFT: {
                RecommendationState.PROPOSED,
                RecommendationState.WITHDRAWN,
            },
            RecommendationState.PROPOSED: {
                RecommendationState.UNDER_REVIEW,
                RecommendationState.WITHDRAWN,
            },
            RecommendationState.UNDER_REVIEW: {
                RecommendationState.WITHDRAWN,
            },
            RecommendationState.APPROVED: {RecommendationState.SUPERSEDED},
            RecommendationState.REJECTED: {RecommendationState.SUPERSEDED},
            RecommendationState.REVISION_REQUIRED: {
                RecommendationState.SUPERSEDED
            },
        }
        if target not in allowed.get(current.state, set()):
            raise RecommendationDecisionError(
                f"invalid lifecycle transition: {current.state.value} -> {target.value}"
            )
        updated = replace(current, state=target)
        self._replace_current(updated)
        self._events.append(
            LifecycleEvent(
                current.recommendation_id,
                current.version,
                current.state,
                target,
                actor,
                occurred_at or datetime.now(timezone.utc),
                reason,
            )
        )
        return updated

    def decide(
        self,
        context: TenantContext,
        recommendation_id: str,
        *,
        disposition: DecisionDisposition,
        approver: Actor,
        rationale: str,
        decision_id: str,
        created_at: datetime | None = None,
    ) -> Decision:
        recommendation = self.get_recommendation(context, recommendation_id)
        if recommendation.state is not RecommendationState.UNDER_REVIEW:
            raise RecommendationDecisionError("recommendation is not under review")
        if approver.actor_type is ActorType.AI:
            raise RecommendationDecisionError("AI cannot approve or decide")
        if approver.actor_id == recommendation.proposer.actor_id:
            raise RecommendationDecisionError("proposer cannot approve own recommendation")
        if not self._authority.is_authorized(context, approver):
            raise RecommendationDecisionError("actor lacks explicit decision authority")
        package = self._approved_package(
            context, recommendation.evidence_package_id
        )
        evidence_result = self._evidence_result(context, package)
        requested = DecisionDisposition(disposition)
        if requested is DecisionDisposition.APPROVE and evidence_result != "AVAILABLE":
            raise RecommendationDecisionError(
                f"approval blocked by evidence state: {evidence_result}"
            )
        decision_key = (context.organization_id, context.tenant_id, decision_id)
        if decision_key in self._decisions:
            raise RecommendationDecisionError("decision id already exists")
        decision = Decision(
            decision_id=decision_id,
            organization_id=context.organization_id,
            tenant_id=context.tenant_id,
            recommendation_id=recommendation.recommendation_id,
            recommendation_version=recommendation.version,
            disposition=requested,
            approver=approver,
            authority_result="AUTHORIZED",
            evidence_result=evidence_result,
            rationale=rationale,
            created_at=created_at or datetime.now(timezone.utc),
        )
        self._decisions[decision_key] = decision
        target = {
            DecisionDisposition.APPROVE: RecommendationState.APPROVED,
            DecisionDisposition.REJECT: RecommendationState.REJECTED,
            DecisionDisposition.REQUEST_REVISION: RecommendationState.REVISION_REQUIRED,
        }[requested]
        self._decision_transition(context, recommendation, target, approver, decision.created_at)
        return decision

    def correct_recommendation(
        self,
        context: TenantContext,
        recommendation_id: str,
        *,
        actor: Actor,
        finding: str | None = None,
        proposed_action: str | None = None,
        alternatives: tuple[Alternative, ...] | None = None,
        evidence_package_id: str | None = None,
        created_at: datetime | None = None,
    ) -> Recommendation:
        original = self.get_recommendation(context, recommendation_id)
        if original.state not in {
            RecommendationState.REVISION_REQUIRED,
            RecommendationState.REJECTED,
            RecommendationState.APPROVED,
        }:
            raise RecommendationDecisionError(
                "correction requires a governed terminal decision state"
            )
        package = self._approved_package(
            context, evidence_package_id or original.evidence_package_id
        )
        corrected = replace(
            original,
            version=original.version + 1,
            finding=finding or original.finding,
            proposed_action=proposed_action or original.proposed_action,
            alternatives=alternatives or original.alternatives,
            evidence_package_id=package.package_id,
            evidence_package_hash=package.package_hash,
            state=RecommendationState.DRAFT,
            created_at=created_at or datetime.now(timezone.utc),
            supersedes_recommendation_id=(
                f"{original.recommendation_id}:v{original.version}"
            ),
        )
        self._store(corrected)
        self._events.append(
            LifecycleEvent(
                recommendation_id,
                corrected.version,
                original.state,
                RecommendationState.DRAFT,
                actor,
                corrected.created_at,
                "corrected recommendation version",
            )
        )
        return corrected

    def get_recommendation(
        self,
        context: TenantContext,
        recommendation_id: str,
        version: int | None = None,
    ) -> Recommendation:
        selected = version or self._current.get(
            self._current_key(context, recommendation_id)
        )
        if selected is None:
            raise RecommendationDecisionError("recommendation not found in tenant scope")
        try:
            return self._recommendations[
                (
                    context.organization_id,
                    context.tenant_id,
                    recommendation_id,
                    selected,
                )
            ]
        except KeyError as exc:
            raise RecommendationDecisionError(
                "recommendation not found in tenant scope"
            ) from exc

    def reconstruct(
        self,
        context: TenantContext,
        decision_id: str,
    ) -> dict[str, Any]:
        try:
            decision = self._decisions[
                (context.organization_id, context.tenant_id, decision_id)
            ]
        except KeyError as exc:
            raise RecommendationDecisionError(
                "decision not found in tenant scope"
            ) from exc
        recommendation = self.get_recommendation(
            context,
            decision.recommendation_id,
            decision.recommendation_version,
        )
        package = self._evidence.get_package(
            context, recommendation.evidence_package_id
        )
        evidence = []
        for use in package.evidence:
            item = self._evidence.get_evidence(context, use.evidence_id)
            evidence.append(
                {
                    "evidence_id": item.evidence_id,
                    "role": use.role.value,
                    "hash": item.evidence_hash,
                    "lineage_ref": item.lineage_ref,
                    "provenance_ref": item.provenance_ref,
                }
            )
        events = [
            asdict(event)
            for event in self._events
            if event.recommendation_id == recommendation.recommendation_id
            and event.version <= recommendation.version
        ]
        result = {
            "recommendation": {
                "id": recommendation.recommendation_id,
                "version": recommendation.version,
                "state": recommendation.state.value,
                "finding": recommendation.finding,
                "proposed_action": recommendation.proposed_action,
                "expected_outcome": recommendation.expected_outcome,
                "alternatives": [asdict(item) for item in recommendation.alternatives],
                "proposer": asdict(recommendation.proposer),
                "ai_proposed": recommendation.ai_proposed,
                "evidence_package_id": package.package_id,
                "evidence_package_hash": package.package_hash,
                "lineage_refs": recommendation.lineage_refs,
                "provenance_refs": recommendation.provenance_refs,
                "supersedes": recommendation.supersedes_recommendation_id,
                "created_at": recommendation.created_at,
            },
            "evidence": sorted(evidence, key=lambda item: (item["role"], item["evidence_id"])),
            "decision": asdict(decision),
            "history": events,
            "fact_inference_boundary": {
                "facts": "recommendation fields and governed evidence",
                "derived": "proposed action, expected outcome, and confidence",
            },
        }
        result["reconstruction_hash"] = _SERIALIZER.content_hash(result)
        return result

    def decision_history(
        self, context: TenantContext, recommendation_id: str
    ) -> tuple[Decision, ...]:
        return tuple(
            sorted(
                (
                    decision
                    for (organization_id, tenant_id, _), decision in self._decisions.items()
                    if organization_id == context.organization_id
                    and tenant_id == context.tenant_id
                    and decision.recommendation_id == recommendation_id
                ),
                key=lambda item: (item.recommendation_version, item.created_at, item.decision_id),
            )
        )

    def _approved_package(self, context, package_id):
        package = self._evidence.get_package(context, package_id)
        if package.status is not EvidencePackageStatus.APPROVED:
            raise RecommendationDecisionError("evidence package must be approved")
        return package

    def _evidence_result(self, context, package):
        if self._evidence.is_package_superseded(context, package.package_id):
            return "SUPERSEDED"
        roles = {entry.role for entry in package.evidence}
        states = set()
        for entry in package.evidence:
            item = self._evidence.get_evidence(context, entry.evidence_id)
            if self._evidence.is_evidence_superseded(context, item.evidence_id):
                states.add("SUPERSEDED")
            elif item.metadata.get("conflicting"):
                states.add("CONFLICTING")
            elif str(item.metadata.get("freshness", "")).lower() == "stale":
                states.add("STALE")
            else:
                states.add("AVAILABLE")
        if CaseRole.SUPPORTING not in roles:
            return "MISSING"
        for state in ("SUPERSEDED", "CONFLICTING", "STALE"):
            if state in states:
                return state
        return "AVAILABLE"

    def _evidence_refs(self, context, package):
        items = [
            self._evidence.get_evidence(context, use.evidence_id)
            for use in package.evidence
        ]
        return (
            tuple(sorted({item.lineage_ref for item in items if item.lineage_ref})),
            tuple(sorted({item.provenance_ref for item in items if item.provenance_ref})),
        )

    def _decision_transition(self, context, recommendation, target, actor, occurred_at):
        updated = replace(recommendation, state=target)
        self._replace_current(updated)
        self._events.append(
            LifecycleEvent(
                recommendation.recommendation_id,
                recommendation.version,
                recommendation.state,
                target,
                actor,
                occurred_at,
                "governed decision",
            )
        )

    def _store(self, recommendation):
        key = (
            recommendation.organization_id,
            recommendation.tenant_id,
            recommendation.recommendation_id,
            recommendation.version,
        )
        self._recommendations[key] = recommendation
        self._current[
            (
                recommendation.organization_id,
                recommendation.tenant_id,
                recommendation.recommendation_id,
            )
        ] = recommendation.version

    def _replace_current(self, recommendation):
        key = (
            recommendation.organization_id,
            recommendation.tenant_id,
            recommendation.recommendation_id,
            recommendation.version,
        )
        self._recommendations[key] = recommendation

    @staticmethod
    def _current_key(context, recommendation_id):
        return context.organization_id, context.tenant_id, recommendation_id
