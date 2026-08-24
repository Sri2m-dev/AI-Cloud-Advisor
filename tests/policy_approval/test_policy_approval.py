from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timedelta, timezone

import pytest

from data_fabric.foundation import TenantContext
from evidence_registry import (
    CaseEvidence,
    CaseRole,
    EvidenceItem,
    InMemoryEvidenceRegistry,
)
from policy_approval import (
    ApprovalAuthorityRegistry,
    ApprovalState,
    AuthorityScope,
    EvidenceState,
    ExceptionState,
    PolicyApprovalError,
    PolicyApprovalService,
    PolicyEvaluationResult,
    PolicyReference,
    PolicyRule,
    PolicyState,
)
from recommendation_decision import (
    Actor,
    ActorType,
    Alternative,
    Decision,
    DecisionDisposition,
    Recommendation,
    RecommendationState,
)

NOW = datetime(2026, 7, 24, 10, tzinfo=timezone.utc)
SCOPE = AuthorityScope("remediate", "application", "app-1")
OTHER_SCOPE = AuthorityScope("remediate", "application", "app-2")


def context(name="a"):
    return TenantContext(f"org-{name}", f"tenant-{name}")


def actor(name, actor_type=ActorType.HUMAN):
    return Actor(name, actor_type)


def harness():
    ctx = context()
    registry = InMemoryEvidenceRegistry()
    item = EvidenceItem(
        evidence_id="ev-1",
        organization_id=ctx.organization_id,
        tenant_id=ctx.tenant_id,
        subject_id="finding-1",
        source_system="connector",
        source_identifier="source-1",
        evidence_hash="evidence-hash",
        observed_at=NOW,
        captured_at=NOW,
        lineage_ref="lineage-1",
        provenance_ref="provenance-1",
    )
    registry.register_evidence(ctx, item)
    registry.create_package(
        ctx,
        package_id="pkg-1",
        case_id="case-1",
        evidence=(CaseEvidence("ev-1", CaseRole.SUPPORTING, "risk evidence"),),
        created_by="evidence-author",
        created_at=NOW,
    )
    registry.approve_package(ctx, "pkg-1", approved_by="evidence-reviewer", approved_at=NOW)
    recommendation = Recommendation(
        recommendation_id="rec-1",
        organization_id=ctx.organization_id,
        tenant_id=ctx.tenant_id,
        version=1,
        finding="Application risk is elevated",
        proposed_action="Remediate application",
        expected_outcome="Risk reduced",
        alternatives=(
            Alternative("no-action", "No action", "Risk remains"),
            Alternative("remediate", "Remediate", "Risk reduced"),
        ),
        evidence_package_id="pkg-1",
        evidence_package_hash=registry.get_package(ctx, "pkg-1").package_hash or "",
        proposer=actor("proposer"),
        state=RecommendationState.APPROVED,
        created_at=NOW,
        lineage_refs=("lineage-1",),
        provenance_refs=("provenance-1",),
    )
    decision = Decision(
        decision_id="dec-1",
        organization_id=ctx.organization_id,
        tenant_id=ctx.tenant_id,
        recommendation_id="rec-1",
        recommendation_version=1,
        disposition=DecisionDisposition.APPROVE,
        approver=actor("decision-approver"),
        authority_result="AUTHORIZED",
        evidence_result="AVAILABLE",
        rationale="approved",
        created_at=NOW,
    )
    authority = ApprovalAuthorityRegistry()
    authority.grant(ctx, "policy-approver", (SCOPE,))
    service = PolicyApprovalService(registry, authority)
    policy = PolicyReference(
        policy_id="policy-1",
        organization_id=ctx.organization_id,
        tenant_id=ctx.tenant_id,
        version=1,
        evaluator_version="wp-012-v1",
        rules=(
            PolicyRule(
                "risk-accepted",
                "risk_accepted",
                True,
                "risk must be explicitly accepted",
            ),
        ),
        required_inputs=("risk_accepted", "change_window"),
        effective_at=NOW - timedelta(days=1),
        lineage_refs=("policy-lineage",),
        provenance_refs=("policy-provenance",),
    )
    service.register_policy(ctx, policy)
    return ctx, registry, authority, service, policy, recommendation, decision


def evaluate(
    service,
    ctx,
    recommendation,
    decision,
    *,
    evaluation_id="eval-1",
    policy_id="policy-1",
    policy_version=1,
    inputs=None,
    evidence_states=None,
    decision_active=True,
):
    return service.evaluate(
        ctx,
        evaluation_id=evaluation_id,
        decision=decision,
        recommendation=recommendation,
        policy_id=policy_id,
        policy_version=policy_version,
        evidence_package_id="pkg-1",
        inputs=inputs
        if inputs is not None
        else {"risk_accepted": True, "change_window": "approved"},
        scope=SCOPE,
        evidence_states=evidence_states,
        evaluated_at=NOW,
        decision_active=decision_active,
    )


def issue_approval(service, ctx, recommendation, decision, evaluation_id="eval-1"):
    return service.issue_approval(
        ctx,
        approval_id="approval-1",
        evaluation_id=evaluation_id,
        decision=decision,
        recommendation=recommendation,
        requester=actor("requester"),
        approver=actor("policy-approver"),
        scope=SCOPE,
        issued_at=NOW,
        effective_at=NOW,
        expires_at=NOW + timedelta(hours=1),
    )


def request_exception(service, ctx, recommendation, decision):
    requested = service.request_exception(
        ctx,
        exception_id="exception-1",
        evaluation_id="eval-1",
        decision=decision,
        requester=actor("requester"),
        policy_rule_id="risk-accepted",
        justification="Compensating control is active",
        evidence_package_id="pkg-1",
        scope=SCOPE,
        issued_at=NOW,
        effective_at=NOW,
        expires_at=NOW + timedelta(hours=1),
    )
    active = service.approve_exception(
        ctx,
        requested.exception_id,
        recommendation=recommendation,
        approver=actor("policy-approver"),
        occurred_at=NOW,
    )
    return requested, active


def test_allow_is_deterministic_and_only_eligible_for_approval():
    ctx, _, _, service, _, recommendation, decision = harness()
    first = evaluate(service, ctx, recommendation, decision)
    second = evaluate(service, ctx, recommendation, decision)
    assert first == second
    assert first.result is PolicyEvaluationResult.ALLOW
    assert first.reasons == ("all deterministic policy rules passed",)
    assert len(first.input_hash) == 64


def test_policy_preview_is_deterministic_non_authoritative_and_not_persisted():
    ctx, _, _, service, _, recommendation, _ = harness()
    candidate = replace(recommendation, state=RecommendationState.UNDER_REVIEW)
    values = dict(
        recommendation=candidate,
        recommendation_version=1,
        evidence_package_id="pkg-1",
        evidence_package_hash=candidate.evidence_package_hash,
        policy_id="policy-1",
        policy_version=1,
        proposed_scope=SCOPE,
        proposed_actor=actor("ai-proposer", ActorType.AI),
        inputs={"risk_accepted": True, "change_window": "approved"},
        evaluated_at=NOW,
    )
    first = service.preview(ctx, **values)
    second = service.preview(ctx, **values)
    assert first == second
    assert first.result is PolicyEvaluationResult.ALLOW
    assert first.authoritative is False
    assert first.matched_rules == ("risk-accepted",)
    with pytest.raises(PolicyApprovalError, match="not found"):
        service.get_evaluation(ctx, first.preview_id)


@pytest.mark.parametrize(
    ("inputs", "states", "expected"),
    [
        ({"risk_accepted": False, "change_window": "approved"}, None, PolicyEvaluationResult.DENY),
        ({"risk_accepted": True}, None, PolicyEvaluationResult.INDETERMINATE),
        (
            {"risk_accepted": True, "change_window": "approved"},
            {"ev-1": EvidenceState.STALE},
            PolicyEvaluationResult.INDETERMINATE,
        ),
    ],
)
def test_policy_preview_deny_and_fail_closed_states(inputs, states, expected):
    ctx, _, _, service, _, recommendation, _ = harness()
    candidate = replace(recommendation, state=RecommendationState.PROPOSED)
    result = service.preview(
        ctx,
        recommendation=candidate,
        recommendation_version=1,
        evidence_package_id="pkg-1",
        evidence_package_hash=candidate.evidence_package_hash,
        policy_id="policy-1",
        policy_version=1,
        proposed_scope=SCOPE,
        proposed_actor=actor("requester"),
        inputs=inputs,
        evidence_states=states,
        evaluated_at=NOW,
    )
    assert result.result is expected


def test_preview_version_tenant_and_authority_separation():
    ctx, _, _, service, _, recommendation, _ = harness()
    candidate = replace(recommendation, state=RecommendationState.PROPOSED)
    base = dict(
        recommendation=candidate,
        evidence_package_id="pkg-1",
        evidence_package_hash=candidate.evidence_package_hash,
        policy_id="policy-1",
        policy_version=1,
        proposed_scope=SCOPE,
        proposed_actor=actor("requester"),
        inputs={"risk_accepted": True, "change_window": "approved"},
        evaluated_at=NOW,
    )
    with pytest.raises(PolicyApprovalError, match="exact recommendation version"):
        service.preview(ctx, recommendation_version=2, **base)
    with pytest.raises(Exception):
        service.preview(context("other"), recommendation_version=1, **base)
    preview = service.preview(ctx, recommendation_version=1, **base)
    with pytest.raises(PolicyApprovalError, match="not found"):
        service.issue_approval(
            ctx,
            approval_id="bad",
            evaluation_id=preview.preview_id,
            decision=harness()[-1],
            recommendation=recommendation,
            requester=actor("requester"),
            approver=actor("policy-approver"),
            scope=SCOPE,
            issued_at=NOW,
            effective_at=NOW,
            expires_at=NOW + timedelta(hours=1),
        )


def test_deny_blocks_approval():
    ctx, _, _, service, _, recommendation, decision = harness()
    result = evaluate(
        service,
        ctx,
        recommendation,
        decision,
        inputs={"risk_accepted": False, "change_window": "approved"},
    )
    assert result.result is PolicyEvaluationResult.DENY
    with pytest.raises(PolicyApprovalError, match="only ALLOW"):
        issue_approval(service, ctx, recommendation, decision)


@pytest.mark.parametrize(
    "inputs,states,reason",
    [
        ({"risk_accepted": True}, None, "missing mandatory inputs"),
        (
            {"risk_accepted": True, "change_window": "approved"},
            {"ev-1": EvidenceState.STALE},
            "evidence is not available",
        ),
        (
            {"risk_accepted": True, "change_window": "approved"},
            {"ev-1": EvidenceState.MISSING},
            "evidence is not available",
        ),
        (
            {"risk_accepted": True, "change_window": "approved"},
            {"ev-1": EvidenceState.CONFLICTING},
            "evidence is not available",
        ),
        (
            {"risk_accepted": True, "change_window": "approved"},
            {"ev-1": EvidenceState.SUPERSEDED},
            "evidence is not available",
        ),
    ],
)
def test_indeterminate_inputs_fail_closed(inputs, states, reason):
    ctx, _, _, service, _, recommendation, decision = harness()
    result = evaluate(service, ctx, recommendation, decision, inputs=inputs, evidence_states=states)
    assert result.result is PolicyEvaluationResult.INDETERMINATE
    assert any(reason in item for item in result.reasons)
    check = service.check_authorization(ctx, evaluation_id="eval-1", scope=SCOPE, checked_at=NOW)
    assert not check.authorized


def test_missing_and_unsupported_policy_versions_are_indeterminate():
    ctx, _, _, service, policy, recommendation, decision = harness()
    missing = evaluate(
        service,
        ctx,
        recommendation,
        decision,
        evaluation_id="missing",
        policy_id="absent",
    )
    assert missing.result is PolicyEvaluationResult.INDETERMINATE
    unsupported = replace(policy, version=2, evaluator_version="future")
    service.register_policy(ctx, unsupported)
    result = evaluate(
        service,
        ctx,
        recommendation,
        decision,
        evaluation_id="unsupported",
        policy_version=2,
    )
    assert result.result is PolicyEvaluationResult.INDETERMINATE


@pytest.mark.parametrize("state", [PolicyState.REVOKED, PolicyState.SUPERSEDED])
def test_revoked_or_superseded_policy_authority_is_indeterminate(state):
    ctx, _, _, service, policy, recommendation, decision = harness()
    service.register_policy(ctx, replace(policy, version=2, state=state))
    result = evaluate(
        service,
        ctx,
        recommendation,
        decision,
        evaluation_id=f"eval-{state.value}",
        policy_version=2,
    )
    assert result.result is PolicyEvaluationResult.INDETERMINATE
    assert f"policy authority is {state.value}" in result.reasons


def test_expired_policy_authority_is_indeterminate():
    ctx, _, _, service, policy, recommendation, decision = harness()
    service.register_policy(ctx, replace(policy, version=2, expires_at=NOW - timedelta(seconds=1)))
    result = evaluate(
        service,
        ctx,
        recommendation,
        decision,
        evaluation_id="eval-expired-policy",
        policy_version=2,
    )
    assert result.result is PolicyEvaluationResult.INDETERMINATE
    assert "policy authority is expired" in result.reasons


def test_invalid_or_superseded_decision_is_indeterminate():
    ctx, _, _, service, _, recommendation, decision = harness()
    result = evaluate(service, ctx, recommendation, decision, decision_active=False)
    assert result.result is PolicyEvaluationResult.INDETERMINATE
    assert "Decision is invalid or superseded" in result.reasons


def test_policy_version_change_creates_new_evaluation_and_preserves_history():
    ctx, _, _, service, policy, recommendation, decision = harness()
    original = evaluate(service, ctx, recommendation, decision)
    service.register_policy(
        ctx,
        replace(
            policy,
            version=2,
            rules=(
                PolicyRule(
                    "risk-accepted",
                    "risk_accepted",
                    False,
                    "new policy rejects accepted risk",
                ),
            ),
        ),
    )
    updated = evaluate(
        service,
        ctx,
        recommendation,
        decision,
        evaluation_id="eval-2",
        policy_version=2,
    )
    assert original.result is PolicyEvaluationResult.ALLOW
    assert updated.result is PolicyEvaluationResult.DENY
    assert service.get_evaluation(ctx, "eval-1") == original


def test_decision_version_change_requires_new_exact_evaluation():
    ctx, _, _, service, _, recommendation, decision = harness()
    changed = replace(decision, recommendation_version=2)
    with pytest.raises(PolicyApprovalError, match="exact Decision version"):
        evaluate(service, ctx, recommendation, changed)


def test_valid_human_approval_authorizes_exact_scope_only():
    ctx, _, _, service, _, recommendation, decision = harness()
    evaluate(service, ctx, recommendation, decision)
    approval = issue_approval(service, ctx, recommendation, decision)
    exact = service.check_authorization(
        ctx,
        evaluation_id="eval-1",
        approval_id=approval.approval_id,
        scope=SCOPE,
        checked_at=NOW,
    )
    outside = service.check_authorization(
        ctx,
        evaluation_id="eval-1",
        approval_id=approval.approval_id,
        scope=OTHER_SCOPE,
        checked_at=NOW,
    )
    assert exact.authorized
    assert not outside.authorized


def test_expired_approval_fails_closed():
    ctx, _, _, service, _, recommendation, decision = harness()
    evaluate(service, ctx, recommendation, decision)
    issue_approval(service, ctx, recommendation, decision)
    check = service.check_authorization(
        ctx,
        evaluation_id="eval-1",
        approval_id="approval-1",
        scope=SCOPE,
        checked_at=NOW + timedelta(hours=2),
    )
    assert not check.authorized
    assert check.reason == "authority is expired"


@pytest.mark.parametrize(
    "transition,state",
    [
        ("revoke_approval", ApprovalState.REVOKED),
        ("supersede_approval", ApprovalState.SUPERSEDED),
        ("expire_approval", ApprovalState.EXPIRED),
    ],
)
def test_inactive_approval_states_fail_closed_and_preserve_prior_version(transition, state):
    ctx, _, _, service, _, recommendation, decision = harness()
    evaluate(service, ctx, recommendation, decision)
    original = issue_approval(service, ctx, recommendation, decision)
    updated = getattr(service, transition)(
        ctx,
        "approval-1",
        actor=actor("policy-approver"),
        reason=state.value,
        occurred_at=NOW,
    )
    check = service.check_authorization(
        ctx,
        evaluation_id="eval-1",
        approval_id="approval-1",
        scope=SCOPE,
        checked_at=NOW,
    )
    assert not check.authorized
    assert updated.state is state
    assert service.get_approval(ctx, "approval-1", 1) == original


def test_unauthorized_and_segregation_approvers_are_blocked():
    ctx, _, authority, service, _, recommendation, decision = harness()
    evaluate(service, ctx, recommendation, decision)
    with pytest.raises(PolicyApprovalError, match="explicit scoped authority"):
        service.issue_approval(
            ctx,
            approval_id="unauthorized",
            evaluation_id="eval-1",
            decision=decision,
            recommendation=recommendation,
            requester=actor("requester"),
            approver=actor("unknown"),
            scope=SCOPE,
            issued_at=NOW,
            effective_at=NOW,
            expires_at=None,
        )
    authority.grant(ctx, "requester", (SCOPE,))
    with pytest.raises(PolicyApprovalError, match="segregation"):
        service.issue_approval(
            ctx,
            approval_id="self",
            evaluation_id="eval-1",
            decision=decision,
            recommendation=recommendation,
            requester=actor("requester"),
            approver=actor("requester"),
            scope=SCOPE,
            issued_at=NOW,
            effective_at=NOW,
            expires_at=None,
        )


@pytest.mark.parametrize("ai_id", ["request-ai", "other-ai"])
def test_ai_cannot_approve_or_issue_exception(ai_id):
    ctx, _, authority, service, _, recommendation, decision = harness()
    authority.grant(ctx, ai_id, (SCOPE,))
    evaluate(service, ctx, recommendation, decision)
    with pytest.raises(PolicyApprovalError, match="AI cannot"):
        service.issue_approval(
            ctx,
            approval_id=f"approval-{ai_id}",
            evaluation_id="eval-1",
            decision=decision,
            recommendation=recommendation,
            requester=actor("request-ai", ActorType.AI),
            approver=actor(ai_id, ActorType.AI),
            scope=SCOPE,
            issued_at=NOW,
            effective_at=NOW,
            expires_at=None,
        )


def test_ai_cannot_approve_exception_even_with_explicit_scope_grant():
    ctx, _, authority, service, _, recommendation, decision = harness()
    authority.grant(ctx, "exception-ai", (SCOPE,))
    evaluate(
        service,
        ctx,
        recommendation,
        decision,
        inputs={"risk_accepted": False, "change_window": "approved"},
    )
    requested = service.request_exception(
        ctx,
        exception_id="ai-exception",
        evaluation_id="eval-1",
        decision=decision,
        requester=actor("requester"),
        policy_rule_id="risk-accepted",
        justification="AI-proposed compensating control",
        evidence_package_id="pkg-1",
        scope=SCOPE,
        issued_at=NOW,
        effective_at=NOW,
        expires_at=NOW + timedelta(hours=1),
    )
    with pytest.raises(PolicyApprovalError, match="AI cannot"):
        service.approve_exception(
            ctx,
            requested.exception_id,
            recommendation=recommendation,
            approver=actor("exception-ai", ActorType.AI),
            occurred_at=NOW,
        )


def test_valid_bounded_exception_authorizes_deny_only_in_scope_and_time():
    ctx, _, _, service, _, recommendation, decision = harness()
    evaluation = evaluate(
        service,
        ctx,
        recommendation,
        decision,
        inputs={"risk_accepted": False, "change_window": "approved"},
    )
    assert evaluation.result is PolicyEvaluationResult.DENY
    requested, active = request_exception(service, ctx, recommendation, decision)
    assert requested.state is ExceptionState.REQUESTED
    assert active.state is ExceptionState.ACTIVE
    exact = service.check_authorization(
        ctx,
        evaluation_id="eval-1",
        exception_id="exception-1",
        scope=SCOPE,
        checked_at=NOW,
    )
    late = service.check_authorization(
        ctx,
        evaluation_id="eval-1",
        exception_id="exception-1",
        scope=SCOPE,
        checked_at=NOW + timedelta(hours=2),
    )
    assert exact.authorized
    assert not late.authorized


@pytest.mark.parametrize(
    "transition,state",
    [
        ("revoke_exception", ExceptionState.REVOKED),
        ("supersede_exception", ExceptionState.SUPERSEDED),
        ("expire_exception", ExceptionState.EXPIRED),
    ],
)
def test_inactive_exception_states_fail_closed(transition, state):
    ctx, _, _, service, _, recommendation, decision = harness()
    evaluate(
        service,
        ctx,
        recommendation,
        decision,
        inputs={"risk_accepted": False, "change_window": "approved"},
    )
    request_exception(service, ctx, recommendation, decision)
    getattr(service, transition)(
        ctx,
        "exception-1",
        actor=actor("policy-approver"),
        reason=state.value,
        occurred_at=NOW,
    )
    check = service.check_authorization(
        ctx,
        evaluation_id="eval-1",
        exception_id="exception-1",
        scope=SCOPE,
        checked_at=NOW,
    )
    assert not check.authorized


def test_exception_renewal_creates_version_without_rewriting_history():
    ctx, _, _, service, _, recommendation, decision = harness()
    evaluate(
        service,
        ctx,
        recommendation,
        decision,
        inputs={"risk_accepted": False, "change_window": "approved"},
    )
    _, active = request_exception(service, ctx, recommendation, decision)
    service.expire_exception(
        ctx,
        "exception-1",
        actor=actor("policy-approver"),
        reason="expired",
        occurred_at=NOW + timedelta(hours=1),
    )
    renewed = service.renew_exception(
        ctx,
        "exception-1",
        requester=actor("renewal-requester"),
        approver=actor("policy-approver"),
        recommendation=recommendation,
        effective_at=NOW + timedelta(hours=2),
        expires_at=NOW + timedelta(hours=3),
        occurred_at=NOW + timedelta(hours=2),
    )
    assert renewed.version == 4
    assert service.get_exception(ctx, "exception-1", 2) == active
    assert renewed.expires_at == NOW + timedelta(hours=3)


def test_exception_scope_expansion_requires_new_authority():
    ctx, _, authority, service, _, recommendation, decision = harness()
    evaluate(
        service,
        ctx,
        recommendation,
        decision,
        inputs={"risk_accepted": False, "change_window": "approved"},
    )
    authority.grant(ctx, "policy-approver", (OTHER_SCOPE,))
    request_exception(service, ctx, recommendation, decision)
    with pytest.raises(FrozenInstanceError):
        service.get_exception(ctx, "exception-1").scope = OTHER_SCOPE
    check = service.check_authorization(
        ctx,
        evaluation_id="eval-1",
        exception_id="exception-1",
        scope=OTHER_SCOPE,
        checked_at=NOW,
    )
    assert not check.authorized


def test_cross_tenant_evaluation_approval_exception_and_reconstruction_fail():
    ctx, _, _, service, _, recommendation, decision = harness()
    evaluate(service, ctx, recommendation, decision)
    issue_approval(service, ctx, recommendation, decision)
    other = context("b")
    with pytest.raises(Exception, match="tenant boundary"):
        evaluate(service, other, recommendation, decision, evaluation_id="foreign")
    with pytest.raises(PolicyApprovalError, match="tenant scope"):
        service.get_approval(other, "approval-1")
    with pytest.raises(PolicyApprovalError, match="tenant scope"):
        service.get_exception(other, "exception-1")
    with pytest.raises(PolicyApprovalError, match="tenant scope"):
        service.reconstruct(other, "eval-1", approval_id="approval-1", as_of=NOW)


def test_indeterminate_cannot_be_converted_by_exception():
    ctx, _, _, service, _, recommendation, decision = harness()
    evaluate(service, ctx, recommendation, decision, inputs={})
    with pytest.raises(PolicyApprovalError, match="INDETERMINATE"):
        service.request_exception(
            ctx,
            exception_id="unsafe",
            evaluation_id="eval-1",
            decision=decision,
            requester=actor("requester"),
            policy_rule_id="risk-accepted",
            justification="unsafe fallback",
            evidence_package_id="pkg-1",
            scope=SCOPE,
            effective_at=NOW,
            expires_at=NOW + timedelta(hours=1),
        )


def test_deterministic_reconstruction_answers_authorization_at_time():
    ctx, _, _, service, _, recommendation, decision = harness()
    evaluate(service, ctx, recommendation, decision)
    issue_approval(service, ctx, recommendation, decision)
    first = service.reconstruct(ctx, "eval-1", approval_id="approval-1", as_of=NOW)
    second = service.reconstruct(ctx, "eval-1", approval_id="approval-1", as_of=NOW)
    assert first == second
    assert first["decision"] == {"id": "dec-1", "version": 1}
    assert first["evidence"]["package_id"] == "pkg-1"
    assert first["policy"]["policy_id"] == "policy-1"
    assert first["evaluation"]["result"] == PolicyEvaluationResult.ALLOW.value
    assert first["authority"]["approver"]["actor_id"] == "policy-approver"
    assert first["authorization_at_time"]["authorized"]
    assert first["history"]
    assert first["fact_inference_boundary"]
    assert len(first["reconstruction_hash"]) == 64


def test_contracts_are_immutable_and_service_has_no_execution_interface():
    ctx, _, _, service, policy, recommendation, decision = harness()
    evaluation = evaluate(service, ctx, recommendation, decision)
    with pytest.raises(FrozenInstanceError):
        evaluation.result = PolicyEvaluationResult.DENY
    with pytest.raises(FrozenInstanceError):
        policy.version = 2
    assert not hasattr(service, "execute")
    assert not hasattr(service, "unlock_execution")
    assert not hasattr(service, "run_action")
