from __future__ import annotations

import hashlib
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from enum import Enum

from universal_evidence.domain import DomainClass
from universal_evidence.financial.intelligence import analyze_financial_evidence
from universal_evidence.financial.models import CurrencyAuthorityType, FinancialConcept
from universal_evidence.financial.workflow import table_from_admission
from universal_evidence.persistence import LifecycleScope


class FinancialDecisionKind(str, Enum):
    DOMAIN = "DOMAIN"
    SEMANTIC_MEASURE = "SEMANTIC_MEASURE"
    CURRENCY = "CURRENCY"


class FinancialDecisionState(str, Enum):
    AUTO_ACCEPTED = "AUTO_ACCEPTED"
    CONFIRMED = "CONFIRMED"
    REJECTED = "REJECTED"
    OVERRIDDEN = "OVERRIDDEN"


@dataclass(frozen=True, slots=True)
class FinancialGovernanceDecision:
    decision_id: str
    kind: FinancialDecisionKind
    state: FinancialDecisionState
    value: str
    actor_id: str
    actor_role: str
    reason: str | None
    decided_at: str
    evidence_fingerprint: str
    classifier_version: str
    policy_version: str
    supersedes_decision_id: str | None
    version: int
    fingerprint: str


class FinancialGovernanceError(RuntimeError):
    pass


class GovernedFinancialWorkflow:
    """Derive financial authority exclusively from scoped persisted decisions."""

    OBJECT_TYPE = "financial_governance_decision"
    POLICY_VERSION = "cmp-p1g-financial-authority-1"

    def __init__(self, lifecycle, publication_repository, *, clock=None):
        self.lifecycle = lifecycle
        self.publication_repository = publication_repository
        self.clock = clock or (lambda: datetime.now(timezone.utc))

    @staticmethod
    def _scope(admission):
        scope = admission.scope
        if not scope.organization_id or not scope.tenant_id:
            raise FinancialGovernanceError("authenticated organization and tenant are required")
        return LifecycleScope(
            scope.organization_id, scope.tenant_id, scope.prospect_id, scope.analysis_id
        )

    def history(self, admission, kind=None):
        decisions = []
        for record in self.lifecycle.list_scope(self._scope(admission)):
            if record.object_type != self.OBJECT_TYPE:
                continue
            payload = dict(record.payload or {})
            if payload.get("evidence_fingerprint") != admission.evidence_fingerprint:
                continue
            decision = self._decision(payload)
            if kind is None or decision.kind is kind:
                decisions.append(decision)
        return tuple(sorted(decisions, key=lambda item: (item.version, item.decided_at)))

    def effective(self, admission, kind):
        history = self.history(admission, kind)
        return history[-1] if history else None

    def decide(
        self,
        admission,
        kind,
        state,
        value,
        *,
        actor_id,
        actor_role,
        reason=None,
    ):
        kind = FinancialDecisionKind(kind)
        state = FinancialDecisionState(state)
        reason_required = state in {
            FinancialDecisionState.REJECTED,
            FinancialDecisionState.OVERRIDDEN,
        }
        if reason_required and not str(reason or "").strip():
            raise FinancialGovernanceError("rejection and override require a reason")
        if actor_role not in {"executive", "super_admin", "admin"}:
            raise PermissionError("actor is not authorized for financial governance")
        current = self.effective(admission, kind)
        if current and current.state is state and current.value == str(value):
            return current
        now = self.clock().isoformat()
        version = (current.version + 1) if current else 1
        identity = (
            self._scope(admission).values,
            admission.evidence_fingerprint,
            kind.value,
            state.value,
            str(value),
            actor_id,
            actor_role,
            reason,
            current.decision_id if current else None,
            version,
        )
        fingerprint = hashlib.sha256(repr(identity).encode()).hexdigest()
        decision = FinancialGovernanceDecision(
            "findec-" + fingerprint[:24],
            kind,
            state,
            str(value),
            str(actor_id),
            str(actor_role),
            str(reason) if reason else None,
            now,
            admission.evidence_fingerprint,
            "cmp-p1r-domain-2",
            self.POLICY_VERSION,
            current.decision_id if current else None,
            version,
            fingerprint,
        )
        self.lifecycle.put(
            self.OBJECT_TYPE,
            decision.decision_id,
            self._scope(admission),
            payload=self._payload(decision),
            fingerprint_value=decision.fingerprint,
            actor_id=decision.actor_id,
            reason=decision.reason or "financial governance decision",
        )
        self.publication_repository.purge_analysis(admission.scope, admission.scope.analysis_id)
        return decision

    def _ensure_policy_authority(self, admission):
        table = table_from_admission(admission)
        proposed = analyze_financial_evidence(table)
        policy_actor = dict(actor_id="financial-policy", actor_role="admin")
        if (
            self.effective(admission, FinancialDecisionKind.DOMAIN) is None
            and proposed.domain.domain is DomainClass.CLOUD_BILLING
            and proposed.domain.score >= 0.75
        ):
            self.decide(
                admission,
                FinancialDecisionKind.DOMAIN,
                FinancialDecisionState.AUTO_ACCEPTED,
                proposed.domain.domain.value,
                reason="explainable high-confidence domain policy",
                **policy_actor,
            )
        measure = next(
            (
                item
                for item in proposed.proposals
                if item.concept is FinancialConcept.EXTENDED_AMOUNT
                and item.score >= 0.80
                and {"RECONCILIATION", "TEMPORAL_FINANCIAL_MATRIX"} & set(item.signals)
            ),
            None,
        )
        if self.effective(admission, FinancialDecisionKind.SEMANTIC_MEASURE) is None and measure:
            self.decide(
                admission,
                FinancialDecisionKind.SEMANTIC_MEASURE,
                FinancialDecisionState.AUTO_ACCEPTED,
                FinancialConcept.EXTENDED_AMOUNT.value,
                reason="multi-signal additive measure policy",
                **policy_actor,
            )
        if (
            self.effective(admission, FinancialDecisionKind.CURRENCY) is None
            and proposed.currency.governed
            and proposed.currency.authority_type is not CurrencyAuthorityType.HUMAN_CONFIRMED
        ):
            self.decide(
                admission,
                FinancialDecisionKind.CURRENCY,
                FinancialDecisionState.AUTO_ACCEPTED,
                proposed.currency.currencies[0],
                reason="unconflicted governed source currency",
                **policy_actor,
            )

    def analyze(self, admission):
        self._ensure_policy_authority(admission)
        domain = self.effective(admission, FinancialDecisionKind.DOMAIN)
        measure = self.effective(admission, FinancialDecisionKind.SEMANTIC_MEASURE)
        currency = self.effective(admission, FinancialDecisionKind.CURRENCY)
        accepted = {
            FinancialDecisionState.AUTO_ACCEPTED,
            FinancialDecisionState.CONFIRMED,
            FinancialDecisionState.OVERRIDDEN,
        }
        result = analyze_financial_evidence(
            table_from_admission(admission),
            confirm_domain=bool(domain and domain.state in accepted),
            confirm_measure=bool(measure and measure.state in accepted),
            confirmed_currency=(
                currency.value if currency and currency.state in accepted else None
            ),
        )
        missing = []
        for kind, decision in (
            (FinancialDecisionKind.DOMAIN, domain),
            (FinancialDecisionKind.SEMANTIC_MEASURE, measure),
            (FinancialDecisionKind.CURRENCY, currency),
        ):
            if decision is None or decision.state not in accepted:
                missing.append(f"persisted {kind.value.lower()} authority is required")
        if missing:
            return replace(
                result,
                observations=(),
                authorized=False,
                blocked_reasons=tuple(dict.fromkeys((*result.blocked_reasons, *missing))),
            )
        if not result.authorized:
            return result
        decisions = (domain, measure, currency)
        authority_fp = hashlib.sha256(
            repr(tuple(item.fingerprint for item in decisions if item)).encode()
        ).hexdigest()
        version = max(item.version for item in decisions if item)
        observations = []
        for item in result.observations:
            publication_fp = hashlib.sha256(
                repr((item.publication_fingerprint, authority_fp, version)).encode()
            ).hexdigest()
            observations.append(
                replace(
                    item,
                    observation_id="finobs-" + publication_fp[:24],
                    domain_decision=domain.decision_id,
                    semantic_decision=measure.decision_id,
                    currency_authority=currency.decision_id,
                    publication_fingerprint=publication_fp,
                    version=version,
                )
            )
        return replace(result, observations=tuple(observations))

    def publish(self, admission, context):
        result = self.analyze(admission)
        if not result.authorized:
            raise FinancialGovernanceError("financial authority is blocked")
        self.publication_repository.publish(result.observations, context)
        return result

    @staticmethod
    def _payload(decision):
        return {
            "decision_id": decision.decision_id,
            "kind": decision.kind.value,
            "state": decision.state.value,
            "value": decision.value,
            "actor_id": decision.actor_id,
            "actor_role": decision.actor_role,
            "reason": decision.reason,
            "decided_at": decision.decided_at,
            "evidence_fingerprint": decision.evidence_fingerprint,
            "classifier_version": decision.classifier_version,
            "policy_version": decision.policy_version,
            "supersedes_decision_id": decision.supersedes_decision_id,
            "version": decision.version,
            "fingerprint": decision.fingerprint,
        }

    @staticmethod
    def _decision(payload):
        return FinancialGovernanceDecision(
            payload["decision_id"],
            FinancialDecisionKind(payload["kind"]),
            FinancialDecisionState(payload["state"]),
            payload["value"],
            payload["actor_id"],
            payload["actor_role"],
            payload.get("reason"),
            payload["decided_at"],
            payload["evidence_fingerprint"],
            payload["classifier_version"],
            payload["policy_version"],
            payload.get("supersedes_decision_id"),
            int(payload["version"]),
            payload["fingerprint"],
        )
