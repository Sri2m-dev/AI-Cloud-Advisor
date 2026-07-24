from dataclasses import FrozenInstanceError
from datetime import datetime, timedelta, timezone

import pytest

from data_fabric.foundation import TenantContext
from evidence_registry import CaseEvidence, CaseRole, EvidenceItem, InMemoryEvidenceRegistry
from execution.base_adapter import AdapterResult
from execution.mock_adapter import MockExecutionAdapter
from execution_outcome import (
    CompensationPlan,
    ExecutionOutcomeError,
    ExecutionOutcomeService,
    ExecutionState,
    OutcomeCriterion,
    OutcomeObservation,
    OutcomePlan,
    OutcomeState,
)
from policy_approval import (
    ApprovalAuthorityRegistry,
    AuthorityScope,
    PolicyApprovalService,
    PolicyReference,
    PolicyRule,
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

NOW = datetime(2026, 7, 24, 12, tzinfo=timezone.utc)
SCOPE = AuthorityScope("remediate", "application", "app-1")


def actor(name, actor_type=ActorType.HUMAN):
    return Actor(name, actor_type)


def context(name="a"):
    return TenantContext(f"org-{name}", f"tenant-{name}")


def harness(adapter=None, *, authority_expires=None, policy_allow=True):
    ctx = context()
    evidence = InMemoryEvidenceRegistry()
    evidence.register_evidence(
        ctx,
        EvidenceItem(
            "ev-1",
            ctx.organization_id,
            ctx.tenant_id,
            "finding-1",
            "connector",
            "source-1",
            "evidence-hash",
            NOW,
            NOW,
            "lineage-1",
            "provenance-1",
        ),
    )
    evidence.create_package(
        ctx,
        package_id="pkg-1",
        case_id="case-1",
        evidence=(CaseEvidence("ev-1", CaseRole.SUPPORTING, "governed"),),
        created_by="author",
        created_at=NOW,
    )
    package = evidence.approve_package(ctx, "pkg-1", approved_by="reviewer", approved_at=NOW)
    recommendation = Recommendation(
        "rec-1",
        ctx.organization_id,
        ctx.tenant_id,
        1,
        "Risk",
        "Remediate",
        "Risk reduced",
        (
            Alternative("none", "No action", "Risk remains"),
            Alternative("fix", "Remediate", "Risk reduced"),
        ),
        "pkg-1",
        package.package_hash or "",
        actor("proposer"),
        RecommendationState.APPROVED,
        NOW,
    )
    decision = Decision(
        "dec-1",
        ctx.organization_id,
        ctx.tenant_id,
        "rec-1",
        1,
        DecisionDisposition.APPROVE,
        actor("decision-approver"),
        "AUTHORIZED",
        "AVAILABLE",
        "approved",
        NOW,
    )
    authority = ApprovalAuthorityRegistry()
    authority.grant(ctx, "authority-approver", (SCOPE,))
    policy = PolicyApprovalService(evidence, authority)
    policy.register_policy(
        ctx,
        PolicyReference(
            "policy-1",
            ctx.organization_id,
            ctx.tenant_id,
            1,
            "wp-012-v1",
            (PolicyRule("rule-1", "eligible", True, "not eligible"),),
            ("eligible",),
            NOW - timedelta(days=1),
        ),
    )
    evaluation = policy.evaluate(
        ctx,
        evaluation_id="eval-1",
        decision=decision,
        recommendation=recommendation,
        policy_id="policy-1",
        policy_version=1,
        evidence_package_id="pkg-1",
        inputs={"eligible": policy_allow},
        scope=SCOPE,
        evaluated_at=NOW,
    )
    approval = None
    if policy_allow:
        approval = policy.issue_approval(
            ctx,
            approval_id="approval-1",
            evaluation_id="eval-1",
            decision=decision,
            recommendation=recommendation,
            requester=actor("requester"),
            approver=actor("authority-approver"),
            scope=SCOPE,
            issued_at=NOW,
            effective_at=NOW,
            expires_at=authority_expires or NOW + timedelta(hours=4),
        )
    service = ExecutionOutcomeService(policy, adapter or MockExecutionAdapter())
    return ctx, policy, service, recommendation, decision, evaluation, approval


def outcome_plan():
    return OutcomePlan(
        baseline={"risk_score": 90},
        criteria=(OutcomeCriterion("risk-reduced", "risk_score", "<=", 40),),
        required_evidence=("outcome-ev",),
        verification_window_ends_at=NOW + timedelta(hours=3),
    )


def compensation_plan():
    return CompensationPlan(
        ("command_failed", "outcome_not_achieved", "operator_requested"),
        ("restore previous state", "verify restoration"),
    )


def create_plan(service, ctx, decision, **overrides):
    values = {
        "plan_id": "plan-1",
        "decision": decision,
        "evaluation_id": "eval-1",
        "authority_type": "approval",
        "authority_id": "approval-1",
        "scope": SCOPE,
        "connector_id": "mock-connector",
        "connector_action": "remediate",
        "requested_by": actor("requester"),
        "executor": actor("executor"),
        "parameters": {"resource_id": "app-1"},
        "outcome_plan": outcome_plan(),
        "compensation_plan": compensation_plan(),
        "created_at": NOW,
    }
    values.update(overrides)
    return service.create_plan(ctx, **values)


def observation(value=30, **overrides):
    values = {
        "metric": "risk_score",
        "value": value,
        "evidence_id": "outcome-ev",
        "evidence_hash": "outcome-hash",
        "source_connector_id": "mock-connector",
        "observed_at": NOW + timedelta(hours=1),
        "lineage_ref": "outcome-lineage",
        "provenance_ref": "outcome-provenance",
    }
    values.update(overrides)
    return OutcomeObservation(**values)


def execute(service, ctx):
    return service.execute(
        ctx, "plan-1", execution_id="exec-1", actor=actor("executor"), executed_at=NOW
    )


def test_exact_active_authority_creates_immutable_bounded_plan():
    ctx, _, service, _, decision, _, _ = harness()
    plan = create_plan(service, ctx, decision)
    assert plan.decision_id == "dec-1"
    assert plan.authority_id == "approval-1"
    assert plan.scope == SCOPE
    assert len(plan.plan_hash) == 64
    with pytest.raises(FrozenInstanceError):
        plan.connector_action = "other"


def test_deny_result_cannot_create_execution_plan():
    ctx, _, service, _, decision, evaluation, _ = harness(policy_allow=False)
    assert evaluation.result.value == "deny"
    with pytest.raises(ExecutionOutcomeError, match="authority denied"):
        create_plan(service, ctx, decision)


def test_expired_or_revoked_authority_blocks_plan_and_execution():
    ctx, policy, service, _, decision, _, _ = harness(authority_expires=NOW + timedelta(minutes=5))
    create_plan(service, ctx, decision)
    policy.revoke_approval(
        ctx,
        "approval-1",
        actor=actor("authority-approver"),
        reason="revoked",
        occurred_at=NOW,
    )
    with pytest.raises(ExecutionOutcomeError, match="not active"):
        execute(service, ctx)


def test_scope_and_connector_action_must_match_exact_authority():
    ctx, _, service, _, decision, _, _ = harness()
    with pytest.raises(ExecutionOutcomeError, match="exactly match"):
        create_plan(service, ctx, decision, connector_action="delete")


def test_ai_executor_is_rejected_before_plan_creation():
    ctx, _, service, _, decision, _, _ = harness()
    with pytest.raises(ExecutionOutcomeError, match="agent-control"):
        create_plan(service, ctx, decision, executor=actor("agent", ActorType.AI))


def test_command_success_is_only_awaiting_independent_outcome_verification():
    ctx, _, service, _, decision, _, _ = harness()
    create_plan(service, ctx, decision)
    record = execute(service, ctx)
    assert record.command_status == "Completed"
    assert record.state is ExecutionState.AWAITING_VERIFICATION
    assert record.state is not ExecutionState.OUTCOME_VERIFIED


def test_execution_plan_is_single_use_and_bound_to_executor():
    ctx, _, service, _, decision, _, _ = harness()
    create_plan(service, ctx, decision)
    with pytest.raises(ExecutionOutcomeError, match="bound executor"):
        service.execute(
            ctx,
            "plan-1",
            execution_id="foreign",
            actor=actor("other"),
            executed_at=NOW,
        )
    execute(service, ctx)
    with pytest.raises(ExecutionOutcomeError, match="single-use"):
        service.execute(
            ctx,
            "plan-1",
            execution_id="again",
            actor=actor("executor"),
            executed_at=NOW,
        )


def test_independent_governed_verification_marks_outcome_verified():
    ctx, _, service, _, decision, _, _ = harness()
    create_plan(service, ctx, decision)
    execute(service, ctx)
    result = service.verify_outcome(
        ctx,
        "exec-1",
        verification_id="verify-1",
        verifier=actor("independent-verifier"),
        observations=(observation(),),
        verified_at=NOW + timedelta(hours=1),
    )
    assert result.state is OutcomeState.VERIFIED
    assert service.get_execution(ctx, "exec-1").state is ExecutionState.OUTCOME_VERIFIED


@pytest.mark.parametrize(
    "verifier",
    [actor("executor"), actor("requester"), actor("verifier-ai", ActorType.AI)],
)
def test_outcome_verifier_must_be_independent_human(verifier):
    ctx, _, service, _, decision, _, _ = harness()
    create_plan(service, ctx, decision)
    execute(service, ctx)
    with pytest.raises(ExecutionOutcomeError, match="independent|AI"):
        service.verify_outcome(
            ctx,
            "exec-1",
            verification_id="unsafe",
            verifier=verifier,
            observations=(observation(),),
            verified_at=NOW + timedelta(hours=1),
        )


def test_missing_or_wrong_connector_evidence_is_indeterminate_not_success():
    ctx, _, service, _, decision, _, _ = harness()
    create_plan(service, ctx, decision)
    execute(service, ctx)
    result = service.verify_outcome(
        ctx,
        "exec-1",
        verification_id="verify-1",
        verifier=actor("verifier"),
        observations=(observation(evidence_id="other", source_connector_id="foreign"),),
        verified_at=NOW + timedelta(hours=1),
    )
    assert result.state is OutcomeState.INDETERMINATE
    assert service.get_execution(ctx, "exec-1").state is ExecutionState.AWAITING_VERIFICATION


def test_failed_outcome_is_not_command_success_and_triggers_compensation():
    ctx, _, service, _, decision, _, _ = harness()
    create_plan(service, ctx, decision)
    execute(service, ctx)
    result = service.verify_outcome(
        ctx,
        "exec-1",
        verification_id="verify-1",
        verifier=actor("verifier"),
        observations=(observation(value=80),),
        verified_at=NOW + timedelta(hours=1),
    )
    assert result.state is OutcomeState.NOT_VERIFIED
    assert service.get_execution(ctx, "exec-1").state is ExecutionState.COMPENSATED


class FailingAdapter(MockExecutionAdapter):
    def execute_stage(self, stage, tasks, context):
        return AdapterResult("mock", "Failed", "command failed", {"external_calls": 0})


def test_command_failure_executes_approved_compensation():
    ctx, _, service, _, decision, _, _ = harness(adapter=FailingAdapter())
    create_plan(service, ctx, decision)
    record = execute(service, ctx)
    assert record.state is ExecutionState.COMPENSATED
    assert record.result_details["compensation"]["status"] == "Rollback Completed"


class FailedRollbackAdapter(FailingAdapter):
    def rollback(self, context):
        return AdapterResult("mock", "Rollback Failed", "rollback failed")


def test_compensation_failure_is_explicit():
    ctx, _, service, _, decision, _, _ = harness(adapter=FailedRollbackAdapter())
    create_plan(service, ctx, decision)
    assert execute(service, ctx).state is ExecutionState.COMPENSATION_FAILED


def test_unapproved_compensation_reason_is_rejected():
    ctx, _, service, _, decision, _, _ = harness()
    create_plan(service, ctx, decision)
    execute(service, ctx)
    with pytest.raises(ExecutionOutcomeError, match="outside the approved plan"):
        service.compensate(
            ctx,
            "exec-1",
            actor=actor("operator"),
            reason="unplanned",
            occurred_at=NOW,
        )


def test_cross_tenant_plan_execution_and_reconstruction_are_rejected():
    ctx, _, service, _, decision, _, _ = harness()
    create_plan(service, ctx, decision)
    execute(service, ctx)
    other = context("b")
    with pytest.raises(ExecutionOutcomeError, match="tenant scope"):
        service.get_plan(other, "plan-1")
    with pytest.raises(ExecutionOutcomeError, match="tenant scope"):
        service.get_execution(other, "exec-1")
    with pytest.raises(ExecutionOutcomeError, match="tenant scope"):
        service.reconstruct(other, "exec-1")


def test_reconstruction_preserves_exact_chain_and_command_outcome_boundary():
    ctx, _, service, _, decision, _, _ = harness()
    create_plan(service, ctx, decision)
    execute(service, ctx)
    service.verify_outcome(
        ctx,
        "exec-1",
        verification_id="verify-1",
        verifier=actor("verifier"),
        observations=(observation(),),
        verified_at=NOW + timedelta(hours=1),
    )
    first = service.reconstruct(ctx, "exec-1")
    second = service.reconstruct(ctx, "exec-1")
    assert first == second
    assert first["authority_chain"]["decision"] == {"id": "dec-1", "version": 1}
    assert first["authority_chain"]["policy_evaluation"]["result"] == "allow"
    assert first["authority_chain"]["authority"]["id"] == "approval-1"
    assert first["execution"]["state"] == "outcome_verified"
    assert first["outcome_verification"]["state"] == "verified"
    assert first["command_success_is_not_outcome"]
    assert len(first["reconstruction_hash"]) == 64


def test_no_database_persistence_or_authority_bypass_interface():
    ctx, _, service, _, decision, _, _ = harness()
    create_plan(service, ctx, decision)
    assert not hasattr(service, "force_authorized")
    assert not hasattr(service, "persist")
    assert not hasattr(service, "grant_authority")
