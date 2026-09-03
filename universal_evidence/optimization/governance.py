from __future__ import annotations

import hashlib
from dataclasses import asdict, replace
from datetime import datetime, timezone
from decimal import Decimal

from universal_evidence.persistence import LifecycleScope

from .models import (
    EligibilityResult,
    EvidenceLevel,
    OpportunityState,
    OpportunityTransition,
    OpportunityType,
    OptimizationOpportunity,
    RealizationState,
)


class OptimizationGovernanceError(RuntimeError):
    pass


_TRANSITIONS = {
    OpportunityState.ELIGIBLE: {OpportunityState.PROPOSED, OpportunityState.BLOCKED},
    OpportunityState.PROPOSED: {OpportunityState.UNDER_REVIEW},
    OpportunityState.UNDER_REVIEW: {
        OpportunityState.APPROVED,
        OpportunityState.REJECTED,
        OpportunityState.REVISION_REQUIRED,
    },
    OpportunityState.APPROVED: {OpportunityState.IMPLEMENTING},
    OpportunityState.IMPLEMENTING: {OpportunityState.IMPLEMENTED},
    OpportunityState.IMPLEMENTED: {OpportunityState.VERIFYING},
    OpportunityState.VERIFYING: {
        OpportunityState.REALIZED,
        OpportunityState.PARTIALLY_REALIZED,
        OpportunityState.NOT_REALIZED,
    },
}


class GovernedOptimizationRepository:
    OBJECT_TYPE = "optimization_opportunity"
    EVENT_TYPE = "optimization_transition"

    def __init__(self, lifecycle, *, clock=None):
        self.lifecycle = lifecycle
        self.clock = clock or (lambda: datetime.now(timezone.utc))

    @staticmethod
    def scope(item_or_scope):
        if isinstance(item_or_scope, LifecycleScope):
            return item_or_scope
        return LifecycleScope(
            item_or_scope.organization_id,
            item_or_scope.tenant_id,
            item_or_scope.prospect_id,
            item_or_scope.analysis_id,
        )

    def save(
        self,
        opportunity: OptimizationOpportunity,
        *,
        actor_id="optimization-policy",
        reason="evidence-derived opportunity",
    ):
        self.lifecycle.put(
            self.OBJECT_TYPE,
            opportunity.opportunity_id,
            self.scope(opportunity),
            payload=self._payload(opportunity),
            fingerprint_value=opportunity.fingerprint,
            actor_id=actor_id,
            reason=reason,
        )
        return opportunity

    def get(self, scope: LifecycleScope, opportunity_id: str) -> OptimizationOpportunity:
        return self._opportunity(
            self.lifecycle.get(self.OBJECT_TYPE, opportunity_id, scope).payload
        )

    def list(self, scope: LifecycleScope) -> tuple[OptimizationOpportunity, ...]:
        return tuple(
            self._opportunity(row.payload)
            for row in self.lifecycle.list_scope(scope)
            if row.object_type == self.OBJECT_TYPE
        )

    def transition(self, scope, opportunity_id, to_state, *, actor_id, actor_role, reason):
        if actor_role not in {
            "executive",
            "super_admin",
            "client_admin",
            "cio",
            "admin",
            "operator",
        }:
            raise PermissionError("actor lacks optimization governance authority")
        if not reason.strip():
            raise OptimizationGovernanceError("transition reason is required")
        current = self.get(scope, opportunity_id)
        target = OpportunityState(to_state)
        if target not in _TRANSITIONS.get(current.state, set()):
            raise OptimizationGovernanceError(
                f"invalid transition: {current.state.value} -> {target.value}"
            )
        if target is OpportunityState.APPROVED and current.potential_savings is None:
            raise OptimizationGovernanceError(
                "monetary approval requires reproducible potential savings"
            )
        now = self.clock().isoformat()
        event_fp = hashlib.sha256(
            repr(
                (current.fingerprint, current.state.value, target.value, actor_id, reason, now)
            ).encode()
        ).hexdigest()
        event = OpportunityTransition(
            "oppevent-" + event_fp[:24],
            current.opportunity_id,
            current.version,
            current.state,
            target,
            actor_id,
            actor_role,
            reason,
            now,
            event_fp,
        )
        updated = replace(current, state=target, governance_state=target, updated_at=now)
        self.save(updated, actor_id=actor_id, reason=reason)
        self.lifecycle.put(
            self.EVENT_TYPE,
            event.event_id,
            self.scope(current),
            payload={
                **asdict(event),
                "from_state": event.from_state.value,
                "to_state": event.to_state.value,
            },
            fingerprint_value=event.fingerprint,
            actor_id=actor_id,
            reason=reason,
        )
        return updated

    def history(self, scope, opportunity_id):
        events = []
        for row in self.lifecycle.list_scope(scope):
            if (
                row.object_type != self.EVENT_TYPE
                or row.payload.get("opportunity_id") != opportunity_id
            ):
                continue
            payload = row.payload
            events.append(
                OpportunityTransition(
                    payload["event_id"],
                    payload["opportunity_id"],
                    int(payload["version"]),
                    OpportunityState(payload["from_state"]),
                    OpportunityState(payload["to_state"]),
                    payload["actor_id"],
                    payload["actor_role"],
                    payload["reason"],
                    payload["occurred_at"],
                    payload["fingerprint"],
                )
            )
        return tuple(sorted(events, key=lambda item: item.occurred_at))

    def supersede(self, current, replacement, *, actor_id, reason):
        if (
            current.opportunity_id == replacement.opportunity_id
            or current.affected_entity != replacement.affected_entity
        ):
            raise OptimizationGovernanceError(
                "supersession requires changed evidence for the same entity"
            )
        now = self.clock().isoformat()
        self.save(
            replace(
                current,
                state=OpportunityState.SUPERSEDED,
                governance_state=OpportunityState.SUPERSEDED,
                superseded_by=replacement.opportunity_id,
                updated_at=now,
            ),
            actor_id=actor_id,
            reason=reason,
        )
        return self.save(
            replace(replacement, version=current.version + 1), actor_id=actor_id, reason=reason
        )

    def verify_realization(
        self,
        scope,
        opportunity_id,
        *,
        actor_id,
        actor_role,
        post_change_cost,
        evidence_references,
        comparable_period,
        currency,
        attribution_confirmed,
        reason,
    ):
        current = self.get(scope, opportunity_id)
        if current.state is not OpportunityState.VERIFYING:
            raise OptimizationGovernanceError("opportunity must be VERIFYING")
        if actor_role not in {"executive", "super_admin", "admin"}:
            raise PermissionError("actor lacks realization verification authority")
        if not evidence_references or not comparable_period or not attribution_confirmed:
            raise OptimizationGovernanceError(
                "post-change evidence, comparable period, and attribution are required"
            )
        if currency != current.currency or current.current_cost is None:
            raise OptimizationGovernanceError("realization currency or baseline is incompatible")
        realized = max(Decimal("0"), current.current_cost - Decimal(str(post_change_cost)))
        target = (
            OpportunityState.REALIZED
            if realized >= (current.potential_savings or Decimal("0"))
            else (
                OpportunityState.PARTIALLY_REALIZED
                if realized > 0
                else OpportunityState.NOT_REALIZED
            )
        )
        updated = self.transition(
            scope, opportunity_id, target, actor_id=actor_id, actor_role=actor_role, reason=reason
        )
        state = RealizationState(target.value)
        updated = replace(
            updated,
            realized_savings=realized,
            realization_state=state,
            realization_evidence=tuple(evidence_references),
        )
        return self.save(updated, actor_id=actor_id, reason="governed realization verification")

    @staticmethod
    def _payload(item):
        data = asdict(item)
        for key in (
            "opportunity_type",
            "state",
            "eligibility_result",
            "confidence_band",
            "technical_risk",
            "business_risk",
            "effort",
            "governance_state",
            "realization_state",
        ):
            data[key] = getattr(item, key).value
        for key in ("current_cost", "potential_savings", "savings_percentage", "realized_savings"):
            data[key] = str(getattr(item, key)) if getattr(item, key) is not None else None
        return data

    @staticmethod
    def _opportunity(p):
        def decimal(key):
            return Decimal(p[key]) if p.get(key) is not None else None

        def tuple_pairs(key):
            return tuple(tuple(value) for value in p.get(key, ()))

        return OptimizationOpportunity(
            p["opportunity_id"],
            int(p["version"]),
            OpportunityType(p["opportunity_type"]),
            OpportunityState(p["state"]),
            p["tenant_id"],
            p["organization_id"],
            p.get("prospect_id", ""),
            p["analysis_id"],
            tuple(p["evidence_fingerprints"]),
            p["affected_entity"],
            p["affected_entity_type"],
            decimal("current_cost"),
            p.get("cost_period"),
            p.get("currency"),
            p.get("currency_authority"),
            decimal("potential_savings"),
            decimal("savings_percentage"),
            EligibilityResult(p["eligibility_result"]),
            tuple(p["eligibility_reason_codes"]),
            tuple_pairs("detection_signals"),
            p.get("calculation_model"),
            p.get("calculation_model_version"),
            tuple_pairs("calculation_inputs"),
            tuple(p["calculation_assumptions"]),
            tuple(p["evidence_references"]),
            tuple(p["lineage"]),
            tuple(p["provenance"]),
            float(p["confidence_score"]),
            EvidenceLevel(p["confidence_band"]),
            tuple_pairs("confidence_factors"),
            EvidenceLevel(p["technical_risk"]),
            EvidenceLevel(p["business_risk"]),
            EvidenceLevel(p["effort"]),
            p["recommendation"],
            tuple(p["alternatives"]),
            p.get("owner"),
            p.get("business_context"),
            p["created_at"],
            p["updated_at"],
            OpportunityState(p["governance_state"]),
            p.get("superseded_by"),
            RealizationState(p["realization_state"]),
            decimal("realized_savings"),
            tuple(p["realization_evidence"]),
            p["fingerprint"],
            p["cost_basis_id"],
        )
