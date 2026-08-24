"""Tenant-bound WP-012 policy, approval, exception, and reconstruction service."""

from __future__ import annotations

from dataclasses import asdict, fields, replace
from datetime import datetime, timezone
from typing import Any

from data_fabric.foundation import DefaultDeterministicSerializer, TenantContext
from evidence_registry import EvidencePackage, EvidencePackageStatus, InMemoryEvidenceRegistry
from policy_approval.models import (
    Approval,
    ApprovalState,
    AuthorityEvent,
    AuthorityScope,
    AuthorizationCheck,
    EvidenceState,
    ExceptionState,
    PolicyEvaluation,
    PolicyEvaluationResult,
    PolicyException,
    PolicyPreviewResult,
    PolicyReference,
    PolicyState,
)
from recommendation_decision import (
    Actor,
    ActorType,
    Decision,
    DecisionDisposition,
    Recommendation,
    RecommendationState,
)

_SERIALIZER = DefaultDeterministicSerializer()
_EVALUATOR_VERSION = "wp-012-v1"


class PolicyApprovalError(ValueError):
    """Policy evaluation or governed authority invariant failure."""


class ApprovalAuthorityRegistry:
    """Tenant-scoped adapter over existing explicit authority concepts."""

    def __init__(self) -> None:
        self._grants: dict[tuple[str, str, str], set[AuthorityScope]] = {}

    def grant(
        self,
        context: TenantContext,
        actor_id: str,
        scopes: tuple[AuthorityScope, ...],
    ) -> None:
        if not actor_id or not scopes:
            raise PolicyApprovalError("explicit actor and authority scope are required")
        self._grants.setdefault(
            (context.organization_id, context.tenant_id, actor_id), set()
        ).update(scopes)

    def is_authorized(
        self,
        context: TenantContext,
        actor: Actor,
        scope: AuthorityScope,
    ) -> bool:
        return scope in self._grants.get(
            (context.organization_id, context.tenant_id, actor.actor_id), set()
        )


class PolicyApprovalService:
    """Persistence-neutral orchestration with deliberately no execution interface."""

    def __init__(
        self,
        evidence_registry: InMemoryEvidenceRegistry,
        authority_registry: ApprovalAuthorityRegistry,
    ) -> None:
        self._evidence = evidence_registry
        self._authority = authority_registry
        self._policies: dict[tuple[str, str, str, int], PolicyReference] = {}
        self._evaluations: dict[tuple[str, str, str], PolicyEvaluation] = {}
        self._approvals: dict[tuple[str, str, str, int], Approval] = {}
        self._approval_current: dict[tuple[str, str, str], int] = {}
        self._exceptions: dict[tuple[str, str, str, int], PolicyException] = {}
        self._exception_current: dict[tuple[str, str, str], int] = {}
        self._events: list[AuthorityEvent] = []

    def register_policy(self, context: TenantContext, policy: PolicyReference) -> PolicyReference:
        context.assert_record_matches(policy, "policy")
        key = self._policy_key(context, policy.policy_id, policy.version)
        existing = self._policies.get(key)
        if existing is not None and existing != policy:
            raise PolicyApprovalError("policy version is immutable")
        self._policies[key] = policy
        return policy

    def evaluate(
        self,
        context: TenantContext,
        *,
        evaluation_id: str,
        decision: Decision,
        recommendation: Recommendation,
        policy_id: str,
        policy_version: int,
        evidence_package_id: str,
        inputs: dict[str, Any],
        scope: AuthorityScope,
        evidence_states: dict[str, EvidenceState] | None = None,
        evaluated_at: datetime | None = None,
        decision_active: bool = True,
    ) -> PolicyEvaluation:
        context.assert_record_matches(decision, "decision")
        context.assert_record_matches(recommendation, "recommendation")
        if decision.recommendation_id != recommendation.recommendation_id:
            raise PolicyApprovalError("Decision and Recommendation do not match")
        if decision.recommendation_version != recommendation.version:
            raise PolicyApprovalError("exact Decision version is required")
        package = self._approved_package(context, evidence_package_id)
        if recommendation.evidence_package_id != package.package_id:
            raise PolicyApprovalError("Decision evidence package binding does not match")
        now = evaluated_at or datetime.now(timezone.utc)
        policy, normalized, states, result, reasons, matched, unmet = self._evaluate_rules(
            context, package, policy_id, policy_version, inputs, evidence_states, now
        )
        if decision.disposition is not DecisionDisposition.APPROVE:
            result, reasons = (
                PolicyEvaluationResult.INDETERMINATE,
                [*reasons, "invalid Decision disposition"],
            )
        if recommendation.state is not RecommendationState.APPROVED or not decision_active:
            result, reasons = (
                PolicyEvaluationResult.INDETERMINATE,
                [*reasons, "Decision is invalid or superseded"],
            )

        content = {
            "tenant": context.to_serializable(),
            "decision_id": decision.decision_id,
            "decision_version": decision.recommendation_version,
            "evidence_package_id": package.package_id,
            "evidence_package_hash": package.package_hash,
            "policy_id": policy.policy_id if policy is not None else policy_id,
            "policy_version": policy.version if policy is not None else policy_version,
            "evaluator_version": (
                policy.evaluator_version if policy is not None else _EVALUATOR_VERSION
            ),
            "inputs": normalized,
            "evidence_states": states,
            "scope": scope,
        }
        evaluation = PolicyEvaluation(
            evaluation_id=evaluation_id,
            organization_id=context.organization_id,
            tenant_id=context.tenant_id,
            decision_id=decision.decision_id,
            decision_version=decision.recommendation_version,
            evidence_package_id=package.package_id,
            evidence_package_hash=package.package_hash or "",
            policy_id=policy.policy_id if policy is not None else policy_id,
            policy_version=policy.version if policy is not None else policy_version,
            evaluator_version=(
                policy.evaluator_version if policy is not None else _EVALUATOR_VERSION
            ),
            evaluated_at=now,
            result=result,
            reasons=tuple(reasons),
            evidence_states=states,
            normalized_inputs=normalized,
            scope=scope,
            input_hash=_SERIALIZER.content_hash(content),
            lineage_refs=policy.lineage_refs if policy is not None else (),
            provenance_refs=policy.provenance_refs if policy is not None else (),
        )
        key = self._evaluation_key(context, evaluation_id)
        existing = self._evaluations.get(key)
        if existing is not None:
            if existing == evaluation:
                return existing
            raise PolicyApprovalError("evaluation is immutable")
        self._evaluations[key] = evaluation
        return evaluation

    def preview(
        self,
        context: TenantContext,
        *,
        recommendation: Recommendation,
        recommendation_version: int,
        evidence_package_id: str,
        evidence_package_hash: str,
        policy_id: str,
        policy_version: int,
        proposed_scope: AuthorityScope,
        proposed_actor: Actor,
        inputs: dict[str, Any],
        evidence_states: dict[str, EvidenceState] | None = None,
        evaluated_at: datetime | None = None,
    ) -> PolicyPreviewResult:
        context.assert_record_matches(recommendation, "recommendation")
        if recommendation.version != recommendation_version:
            raise PolicyApprovalError("exact recommendation version is required")
        if recommendation.state not in {
            RecommendationState.PROPOSED,
            RecommendationState.UNDER_REVIEW,
        }:
            raise PolicyApprovalError("recommendation is not eligible for policy preview")
        package = self._approved_package(context, evidence_package_id)
        if (
            recommendation.evidence_package_id != package.package_id
            or package.package_hash != evidence_package_hash
        ):
            raise PolicyApprovalError("exact approved evidence package binding is required")
        now = evaluated_at or datetime.now(timezone.utc)
        policy, normalized, states, result, reasons, matched, unmet = self._evaluate_rules(
            context, package, policy_id, policy_version, inputs, evidence_states, now
        )
        content = {
            "tenant": context.to_serializable(),
            "recommendation_id": recommendation.recommendation_id,
            "recommendation_version": recommendation.version,
            "package": package.package_hash,
            "policy_id": policy_id,
            "policy_version": policy_version,
            "scope": proposed_scope,
            "actor": proposed_actor,
            "inputs": normalized,
            "states": states,
            "evaluated_at": now,
        }
        integrity_hash = _SERIALIZER.content_hash(content)
        return PolicyPreviewResult(
            f"preview:{integrity_hash[:24]}",
            context.organization_id,
            context.tenant_id,
            recommendation.recommendation_id,
            recommendation.version,
            package.package_id,
            package.package_hash or "",
            policy_id,
            policy_version,
            proposed_scope,
            proposed_actor,
            result,
            tuple(matched),
            tuple(unmet),
            tuple(reasons),
            states,
            ("explicit scoped human authority required",),
            ("proposer/requester cannot self-approve", "AI cannot approve"),
            ("authorization must be effective and unexpired",),
            bool(unmet),
            now,
            integrity_hash,
            False,
        )

    def _evaluate_rules(
        self, context, package, policy_id, policy_version, inputs, evidence_states, now
    ):
        try:
            policy = self._get_policy(context, policy_id, policy_version)
        except PolicyApprovalError:
            policy = None
        normalized = dict(sorted(inputs.items()))
        states = (
            dict(evidence_states)
            if evidence_states is not None
            else {use.evidence_id: EvidenceState.AVAILABLE for use in package.evidence}
        )
        for use in package.evidence:
            states.setdefault(use.evidence_id, EvidenceState.MISSING)
        reasons, matched, unmet = [], [], []
        result = PolicyEvaluationResult.ALLOW
        if policy is None or policy.evaluator_version != _EVALUATOR_VERSION:
            result = PolicyEvaluationResult.INDETERMINATE
            reasons.append("missing or unsupported policy version")
        elif policy.state is not PolicyState.ACTIVE or now < policy.effective_at:
            result = PolicyEvaluationResult.INDETERMINATE
            reasons.append(f"policy authority is {policy.state.value}")
        if policy is not None and policy.expires_at is not None and now >= policy.expires_at:
            result = PolicyEvaluationResult.INDETERMINATE
            reasons.append("policy authority is expired")
        missing = sorted(
            name
            for name in (() if policy is None else policy.required_inputs)
            if name not in normalized
        )
        unsafe = sorted(
            f"{key}:{EvidenceState(value).value}"
            for key, value in states.items()
            if EvidenceState(value) is not EvidenceState.AVAILABLE
        )
        if missing or unsafe or self._evidence.is_package_superseded(context, package.package_id):
            result = PolicyEvaluationResult.INDETERMINATE
            if missing:
                reasons.append(f"missing mandatory inputs: {', '.join(missing)}")
            if unsafe:
                reasons.append(f"evidence is not available: {', '.join(unsafe)}")
            if self._evidence.is_package_superseded(context, package.package_id):
                reasons.append("evidence package is superseded")
        if policy is not None:
            for rule in policy.rules:
                (
                    matched if normalized.get(rule.input_name) == rule.expected_value else unmet
                ).append(rule.rule_id)
            if result is PolicyEvaluationResult.ALLOW and unmet:
                result = PolicyEvaluationResult.DENY
                reasons.extend(
                    rule.failure_reason for rule in policy.rules if rule.rule_id in unmet
                )
        if result is PolicyEvaluationResult.ALLOW:
            reasons.append("all deterministic policy rules passed")
        return policy, normalized, states, result, reasons, matched, unmet

    def issue_approval(
        self,
        context: TenantContext,
        *,
        approval_id: str,
        evaluation_id: str,
        decision: Decision,
        recommendation: Recommendation,
        requester: Actor,
        approver: Actor,
        scope: AuthorityScope,
        effective_at: datetime,
        expires_at: datetime | None,
        issued_at: datetime | None = None,
    ) -> Approval:
        evaluation = self.get_evaluation(context, evaluation_id)
        self._validate_evaluation_binding(evaluation, decision, scope)
        if evaluation.result is not PolicyEvaluationResult.ALLOW:
            raise PolicyApprovalError("only ALLOW is eligible for governed approval")
        self._validate_approver(context, recommendation, requester, approver, scope)
        if self._approval_current_key(context, approval_id) in self._approval_current:
            raise PolicyApprovalError("approval id already exists")
        approval = Approval(
            approval_id=approval_id,
            organization_id=context.organization_id,
            tenant_id=context.tenant_id,
            version=1,
            decision_id=decision.decision_id,
            decision_version=decision.recommendation_version,
            evaluation_id=evaluation.evaluation_id,
            requester=requester,
            approver=approver,
            scope=scope,
            issued_at=issued_at or datetime.now(timezone.utc),
            effective_at=effective_at,
            expires_at=expires_at,
            state=ApprovalState.ACTIVE,
            lineage_refs=evaluation.lineage_refs,
            provenance_refs=evaluation.provenance_refs,
        )
        self._store_approval(context, approval)
        self._event(
            "approval",
            approval_id,
            1,
            None,
            approval.state.value,
            approver,
            approval.issued_at,
            "approval issued",
        )
        return approval

    def revoke_approval(
        self,
        context: TenantContext,
        approval_id: str,
        *,
        actor: Actor,
        reason: str,
        occurred_at: datetime | None = None,
    ) -> Approval:
        return self._transition_approval(
            context, approval_id, ApprovalState.REVOKED, actor, reason, occurred_at
        )

    def supersede_approval(
        self,
        context: TenantContext,
        approval_id: str,
        *,
        actor: Actor,
        reason: str,
        occurred_at: datetime | None = None,
    ) -> Approval:
        return self._transition_approval(
            context, approval_id, ApprovalState.SUPERSEDED, actor, reason, occurred_at
        )

    def expire_approval(
        self,
        context: TenantContext,
        approval_id: str,
        *,
        actor: Actor,
        reason: str,
        occurred_at: datetime | None = None,
    ) -> Approval:
        return self._transition_approval(
            context, approval_id, ApprovalState.EXPIRED, actor, reason, occurred_at
        )

    def request_exception(
        self,
        context: TenantContext,
        *,
        exception_id: str,
        evaluation_id: str,
        decision: Decision,
        requester: Actor,
        policy_rule_id: str,
        justification: str,
        evidence_package_id: str,
        scope: AuthorityScope,
        effective_at: datetime,
        expires_at: datetime,
        issued_at: datetime | None = None,
    ) -> PolicyException:
        evaluation = self.get_evaluation(context, evaluation_id)
        self._validate_evaluation_binding(evaluation, decision, scope)
        if evaluation.result is PolicyEvaluationResult.INDETERMINATE:
            raise PolicyApprovalError("INDETERMINATE cannot be excepted into authorization")
        package = self._approved_package(context, evidence_package_id)
        policy = self._get_policy(context, evaluation.policy_id, evaluation.policy_version)
        if policy_rule_id not in {rule.rule_id for rule in policy.rules}:
            raise PolicyApprovalError("exception must identify an applicable policy rule")
        if self._exception_current_key(context, exception_id) in self._exception_current:
            raise PolicyApprovalError("exception id already exists")
        requested = PolicyException(
            exception_id=exception_id,
            organization_id=context.organization_id,
            tenant_id=context.tenant_id,
            version=1,
            decision_id=decision.decision_id,
            decision_version=decision.recommendation_version,
            evaluation_id=evaluation.evaluation_id,
            policy_id=evaluation.policy_id,
            policy_version=evaluation.policy_version,
            rule_id=policy_rule_id,
            requester=requester,
            approver=None,
            justification=justification,
            evidence_package_id=package.package_id,
            scope=scope,
            issued_at=issued_at or datetime.now(timezone.utc),
            effective_at=effective_at,
            expires_at=expires_at,
            state=ExceptionState.REQUESTED,
            lineage_refs=evaluation.lineage_refs,
            provenance_refs=evaluation.provenance_refs,
        )
        self._store_exception(context, requested)
        self._event(
            "exception",
            exception_id,
            1,
            None,
            requested.state.value,
            requester,
            requested.issued_at,
            "exception requested",
        )
        return requested

    def approve_exception(
        self,
        context: TenantContext,
        exception_id: str,
        *,
        recommendation: Recommendation,
        approver: Actor,
        occurred_at: datetime | None = None,
    ) -> PolicyException:
        current = self.get_exception(context, exception_id)
        if current.state is not ExceptionState.REQUESTED:
            raise PolicyApprovalError("only a requested exception may be approved")
        self._validate_approver(context, recommendation, current.requester, approver, current.scope)
        now = occurred_at or datetime.now(timezone.utc)
        active = replace(
            current,
            version=current.version + 1,
            approver=approver,
            state=ExceptionState.ACTIVE,
        )
        self._store_exception(context, active)
        self._event(
            "exception",
            exception_id,
            active.version,
            current.state.value,
            active.state.value,
            approver,
            now,
            "exception approved",
        )
        return active

    def renew_exception(
        self,
        context: TenantContext,
        exception_id: str,
        *,
        requester: Actor,
        approver: Actor,
        recommendation: Recommendation,
        effective_at: datetime,
        expires_at: datetime,
        occurred_at: datetime | None = None,
    ) -> PolicyException:
        current = self.get_exception(context, exception_id)
        if current.state not in {ExceptionState.ACTIVE, ExceptionState.EXPIRED}:
            raise PolicyApprovalError("only active or expired exception may be renewed")
        self._validate_approver(context, recommendation, requester, approver, current.scope)
        now = occurred_at or datetime.now(timezone.utc)
        renewed = replace(
            current,
            version=current.version + 1,
            requester=requester,
            approver=approver,
            issued_at=now,
            effective_at=effective_at,
            expires_at=expires_at,
            state=ExceptionState.ACTIVE,
        )
        self._store_exception(context, renewed)
        self._event(
            "exception",
            exception_id,
            renewed.version,
            current.state.value,
            renewed.state.value,
            approver,
            now,
            "exception renewed",
        )
        return renewed

    def revoke_exception(
        self,
        context: TenantContext,
        exception_id: str,
        *,
        actor: Actor,
        reason: str,
        occurred_at: datetime | None = None,
    ) -> PolicyException:
        return self._transition_exception(
            context, exception_id, ExceptionState.REVOKED, actor, reason, occurred_at
        )

    def supersede_exception(
        self,
        context: TenantContext,
        exception_id: str,
        *,
        actor: Actor,
        reason: str,
        occurred_at: datetime | None = None,
    ) -> PolicyException:
        return self._transition_exception(
            context, exception_id, ExceptionState.SUPERSEDED, actor, reason, occurred_at
        )

    def expire_exception(
        self,
        context: TenantContext,
        exception_id: str,
        *,
        actor: Actor,
        reason: str,
        occurred_at: datetime | None = None,
    ) -> PolicyException:
        return self._transition_exception(
            context, exception_id, ExceptionState.EXPIRED, actor, reason, occurred_at
        )

    def check_authorization(
        self,
        context: TenantContext,
        *,
        evaluation_id: str,
        scope: AuthorityScope,
        checked_at: datetime,
        approval_id: str | None = None,
        exception_id: str | None = None,
    ) -> AuthorizationCheck:
        evaluation = self.get_evaluation(context, evaluation_id)
        if evaluation.scope != scope:
            return AuthorizationCheck(
                False,
                "requested scope does not match evaluation",
                evaluation.result,
                None,
                None,
                checked_at,
            )
        if evaluation.result is PolicyEvaluationResult.INDETERMINATE:
            return AuthorizationCheck(
                False,
                "INDETERMINATE blocks authorization",
                evaluation.result,
                None,
                None,
                checked_at,
            )
        if approval_id is not None:
            approval = self.get_approval(context, approval_id)
            reason = self._authority_reason(
                approval.state.value,
                approval.effective_at,
                approval.expires_at,
                approval.scope,
                evaluation_id,
                scope,
                checked_at,
                approval.evaluation_id,
            )
            return AuthorizationCheck(
                reason == "active exact-scope authority",
                reason,
                evaluation.result,
                "approval",
                approval.approval_id,
                checked_at,
            )
        if exception_id is not None:
            exception = self.get_exception(context, exception_id)
            reason = self._authority_reason(
                exception.state.value,
                exception.effective_at,
                exception.expires_at,
                exception.scope,
                evaluation_id,
                scope,
                checked_at,
                exception.evaluation_id,
            )
            return AuthorizationCheck(
                reason == "active exact-scope authority",
                reason,
                evaluation.result,
                "exception",
                exception.exception_id,
                checked_at,
            )
        return AuthorizationCheck(
            False,
            "explicit approval or exception is required",
            evaluation.result,
            None,
            None,
            checked_at,
        )

    def get_evaluation(self, context: TenantContext, evaluation_id: str) -> PolicyEvaluation:
        try:
            return self._evaluations[self._evaluation_key(context, evaluation_id)]
        except KeyError as exc:
            raise PolicyApprovalError("evaluation not found in tenant scope") from exc

    def get_approval(
        self, context: TenantContext, approval_id: str, version: int | None = None
    ) -> Approval:
        selected = version or self._approval_current.get(
            self._approval_current_key(context, approval_id)
        )
        try:
            return self._approvals[
                (context.organization_id, context.tenant_id, approval_id, selected)
            ]
        except KeyError as exc:
            raise PolicyApprovalError("approval not found in tenant scope") from exc

    def get_exception(
        self, context: TenantContext, exception_id: str, version: int | None = None
    ) -> PolicyException:
        selected = version or self._exception_current.get(
            self._exception_current_key(context, exception_id)
        )
        try:
            return self._exceptions[
                (context.organization_id, context.tenant_id, exception_id, selected)
            ]
        except KeyError as exc:
            raise PolicyApprovalError("exception not found in tenant scope") from exc

    def reconstruct(
        self,
        context: TenantContext,
        evaluation_id: str,
        *,
        approval_id: str | None = None,
        exception_id: str | None = None,
        as_of: datetime,
    ) -> dict[str, Any]:
        evaluation = self.get_evaluation(context, evaluation_id)
        policy = self._get_policy(context, evaluation.policy_id, evaluation.policy_version)
        package = self._approved_package(context, evaluation.evidence_package_id)
        authority: Approval | PolicyException | None = None
        authority_type = None
        if approval_id:
            authority = self.get_approval(context, approval_id)
            authority_type = "approval"
        elif exception_id:
            authority = self.get_exception(context, exception_id)
            authority_type = "exception"
        check = self.check_authorization(
            context,
            evaluation_id=evaluation_id,
            scope=evaluation.scope,
            checked_at=as_of,
            approval_id=approval_id,
            exception_id=exception_id,
        )
        events = [
            asdict(event)
            for event in self._events
            if authority is not None
            and event.authority_type == authority_type
            and event.authority_id == getattr(authority, f"{authority_type}_id")
        ]
        result = {
            "tenant": context.to_serializable(),
            "decision": {
                "id": evaluation.decision_id,
                "version": evaluation.decision_version,
            },
            "evidence": {
                "package_id": package.package_id,
                "package_hash": package.package_hash,
                "states": evaluation.evidence_states,
            },
            "policy": _record_content(policy),
            "evaluation": _record_content(evaluation),
            "authority": _record_content(authority) if authority else None,
            "authorization_at_time": _record_content(check),
            "history": _SERIALIZER.to_json_compatible(events),
            "fact_inference_boundary": {
                "facts": "Decision, governed evidence, policy version, and authority history",
                "derived": "policy result, reasons, and authorization-at-time conclusion",
            },
        }
        result["reconstruction_hash"] = _SERIALIZER.content_hash(result)
        return result

    def _validate_approver(
        self,
        context: TenantContext,
        recommendation: Recommendation,
        requester: Actor,
        approver: Actor,
        scope: AuthorityScope,
    ) -> None:
        context.assert_record_matches(recommendation, "recommendation")
        if approver.actor_type is ActorType.AI:
            raise PolicyApprovalError("AI cannot approve authority or exception")
        if requester.actor_id == approver.actor_id:
            raise PolicyApprovalError("requester and approver segregation is required")
        if recommendation.proposer.actor_id == approver.actor_id:
            raise PolicyApprovalError("Decision proposer cannot grant policy authority")
        if not self._authority.is_authorized(context, approver, scope):
            raise PolicyApprovalError("approver lacks explicit scoped authority")

    @staticmethod
    def _validate_evaluation_binding(
        evaluation: PolicyEvaluation,
        decision: Decision,
        scope: AuthorityScope,
    ) -> None:
        if (
            evaluation.decision_id != decision.decision_id
            or evaluation.decision_version != decision.recommendation_version
        ):
            raise PolicyApprovalError("authority requires exact Decision version")
        if evaluation.scope != scope:
            raise PolicyApprovalError("authority scope must match policy evaluation")

    @staticmethod
    def _authority_reason(
        state: str,
        effective_at: datetime,
        expires_at: datetime | None,
        authority_scope: AuthorityScope,
        evaluation_id: str,
        requested_scope: AuthorityScope,
        checked_at: datetime,
        authority_evaluation_id: str | None = None,
    ) -> str:
        if state not in {ApprovalState.ACTIVE.value, ExceptionState.ACTIVE.value}:
            return f"authority is {state}"
        if checked_at < effective_at:
            return "authority is not yet effective"
        if expires_at is not None and checked_at >= expires_at:
            return "authority is expired"
        if authority_scope != requested_scope:
            return "authority is outside requested scope"
        if authority_evaluation_id is not None and authority_evaluation_id != evaluation_id:
            return "authority belongs to another evaluation"
        return "active exact-scope authority"

    def _transition_approval(
        self,
        context: TenantContext,
        approval_id: str,
        state: ApprovalState,
        actor: Actor,
        reason: str,
        occurred_at: datetime | None,
    ) -> Approval:
        current = self.get_approval(context, approval_id)
        if current.state is not ApprovalState.ACTIVE:
            raise PolicyApprovalError("only active approval may change state")
        now = occurred_at or datetime.now(timezone.utc)
        updated = replace(current, version=current.version + 1, state=state)
        self._store_approval(context, updated)
        self._event(
            "approval",
            approval_id,
            updated.version,
            current.state.value,
            state.value,
            actor,
            now,
            reason,
        )
        return updated

    def _transition_exception(
        self,
        context: TenantContext,
        exception_id: str,
        state: ExceptionState,
        actor: Actor,
        reason: str,
        occurred_at: datetime | None,
    ) -> PolicyException:
        current = self.get_exception(context, exception_id)
        if current.state not in {ExceptionState.REQUESTED, ExceptionState.ACTIVE}:
            raise PolicyApprovalError("exception state is terminal")
        now = occurred_at or datetime.now(timezone.utc)
        updated = replace(current, version=current.version + 1, state=state)
        self._store_exception(context, updated)
        self._event(
            "exception",
            exception_id,
            updated.version,
            current.state.value,
            state.value,
            actor,
            now,
            reason,
        )
        return updated

    def _store_approval(self, context: TenantContext, approval: Approval) -> None:
        self._approvals[
            (context.organization_id, context.tenant_id, approval.approval_id, approval.version)
        ] = approval
        self._approval_current[self._approval_current_key(context, approval.approval_id)] = (
            approval.version
        )

    def _store_exception(self, context: TenantContext, exception: PolicyException) -> None:
        self._exceptions[
            (
                context.organization_id,
                context.tenant_id,
                exception.exception_id,
                exception.version,
            )
        ] = exception
        self._exception_current[self._exception_current_key(context, exception.exception_id)] = (
            exception.version
        )

    def _event(
        self,
        authority_type: str,
        authority_id: str,
        version: int,
        from_state: str | None,
        to_state: str,
        actor: Actor,
        occurred_at: datetime,
        reason: str,
    ) -> None:
        self._events.append(
            AuthorityEvent(
                authority_type,
                authority_id,
                version,
                from_state,
                to_state,
                actor,
                occurred_at,
                reason,
            )
        )

    def _approved_package(self, context: TenantContext, package_id: str) -> EvidencePackage:
        package = self._evidence.get_package(context, package_id)
        if package.status is not EvidencePackageStatus.APPROVED:
            raise PolicyApprovalError("evidence package must be approved")
        return package

    def _get_policy(self, context: TenantContext, policy_id: str, version: int) -> PolicyReference:
        try:
            return self._policies[self._policy_key(context, policy_id, version)]
        except KeyError as exc:
            raise PolicyApprovalError("policy version not found in tenant scope") from exc

    @staticmethod
    def _policy_key(context: TenantContext, policy_id: str, version: int):
        return context.organization_id, context.tenant_id, policy_id, version

    @staticmethod
    def _evaluation_key(context: TenantContext, evaluation_id: str):
        return context.organization_id, context.tenant_id, evaluation_id

    @staticmethod
    def _approval_current_key(context: TenantContext, approval_id: str):
        return context.organization_id, context.tenant_id, approval_id

    @staticmethod
    def _exception_current_key(context: TenantContext, exception_id: str):
        return context.organization_id, context.tenant_id, exception_id


def _record_content(record: Any) -> Any:
    """Serialize a frozen record without deepcopying immutable mapping proxies."""

    return _SERIALIZER.to_json_compatible(
        {item.name: getattr(record, item.name) for item in fields(record)}
    )
