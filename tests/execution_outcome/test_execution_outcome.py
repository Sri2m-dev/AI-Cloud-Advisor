from dataclasses import FrozenInstanceError, replace
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
        "connector_id": "mock",
        "connector_action": "remediate",
        "target_path": ("resource_id",),
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
        "organization_id": "org-a",
        "tenant_id": "tenant-a",
        "metric": "risk_score",
        "value": value,
        "evidence_id": "outcome-ev",
        "evidence_hash": "outcome-hash",
        "source_connector_id": "mock",
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
    assert first["authority_chain"]["recommendation"] == {"id": "rec-1", "version": 1}
    assert first["authority_chain"]["evidence_package"]["id"] == "pkg-1"
    assert len(first["authority_chain"]["evidence_package"]["hash"]) == 64
    assert first["authority_chain"]["policy_evaluation"]["result"] == "allow"
    assert first["authority_chain"]["policy_evaluation"]["policy_id"] == "policy-1"
    assert first["authority_chain"]["authority"]["id"] == "approval-1"
    assert first["authority_chain"]["execution_authorization"] == {
        "connector_id": "mock",
        "connector_action": "remediate",
        "target_path": ["resource_id"],
        "target": "app-1",
    }
    assert first["plan"]["executor"]["actor_id"] == "executor"
    assert first["plan"]["compensation_plan"]["rollback_steps"]
    assert first["execution"]["adapter"] == "mock"
    assert first["execution"]["command_status"] == "Completed"
    assert first["execution"]["result_details"]["details"]["external_calls"] == 0
    assert first["execution"]["state"] == "outcome_verified"
    assert first["outcome_verification"]["state"] == "verified"
    assert first["outcome_verification"]["observations"][0]["evidence_id"] == "outcome-ev"
    assert first["outcome_verification"]["observations"][0]["tenant_id"] == "tenant-a"
    assert first["command_success_is_not_outcome"]
    assert len(first["reconstruction_hash"]) == 64


def test_no_database_persistence_or_authority_bypass_interface():
    ctx, _, service, _, decision, _, _ = harness()
    create_plan(service, ctx, decision)
    assert not hasattr(service, "force_authorized")
    assert not hasattr(service, "persist")
    assert not hasattr(service, "grant_authority")


@pytest.mark.parametrize(
    ("values", "expected"),
    [
        ((30, 30), OutcomeState.VERIFIED),
        ((30, 80), OutcomeState.NOT_VERIFIED),
        ((80, 30), OutcomeState.NOT_VERIFIED),
        ((80, 80), OutcomeState.NOT_VERIFIED),
    ],
)
def test_duplicate_outcome_evidence_is_conservatively_aggregated(values, expected):
    ctx, _, service, _, decision, _, _ = harness()
    create_plan(service, ctx, decision)
    execute(service, ctx)
    result = service.verify_outcome(
        ctx,
        "exec-1",
        verification_id="verify-duplicates",
        verifier=actor("verifier"),
        observations=tuple(
            observation(value=value, evidence_hash=f"hash-{index}")
            for index, value in enumerate(values)
        ),
        verified_at=NOW + timedelta(hours=1),
    )
    assert result.state is expected


def test_missing_outcome_observation_is_indeterminate():
    ctx, _, service, _, decision, _, _ = harness()
    create_plan(service, ctx, decision)
    execute(service, ctx)
    result = service.verify_outcome(
        ctx,
        "exec-1",
        verification_id="verify-missing",
        verifier=actor("verifier"),
        observations=(),
        verified_at=NOW + timedelta(hours=1),
    )
    assert result.state is OutcomeState.INDETERMINATE


def test_duplicate_evidence_order_cannot_change_outcome():
    results = []
    hashes = []
    for values in ((30, 80), (80, 30)):
        ctx, _, service, _, decision, _, _ = harness()
        create_plan(service, ctx, decision)
        execute(service, ctx)
        verification = service.verify_outcome(
            ctx,
            "exec-1",
            verification_id="verify-order",
            verifier=actor("verifier"),
            observations=tuple(observation(value=value) for value in values),
            verified_at=NOW + timedelta(hours=1),
        )
        results.append(verification.state)
        hashes.append(verification.verification_hash)
    assert results == [OutcomeState.NOT_VERIFIED, OutcomeState.NOT_VERIFIED]
    assert hashes[0] == hashes[1]


@pytest.mark.parametrize(
    ("organization_id", "tenant_id"),
    [("org-b", "tenant-a"), ("org-a", "tenant-b")],
)
def test_foreign_outcome_observations_are_rejected(organization_id, tenant_id):
    ctx, _, service, _, decision, _, _ = harness()
    create_plan(service, ctx, decision)
    execute(service, ctx)
    with pytest.raises(ExecutionOutcomeError, match="tenant boundary"):
        service.verify_outcome(
            ctx,
            "exec-1",
            verification_id="verify-foreign",
            verifier=actor("verifier"),
            observations=(
                observation(organization_id=organization_id, tenant_id=tenant_id),
            ),
            verified_at=NOW + timedelta(hours=1),
        )


def test_mixed_tenant_observations_are_rejected():
    ctx, _, service, _, decision, _, _ = harness()
    create_plan(service, ctx, decision)
    execute(service, ctx)
    with pytest.raises(ExecutionOutcomeError, match="tenant boundary"):
        service.verify_outcome(
            ctx,
            "exec-1",
            verification_id="verify-mixed",
            verifier=actor("verifier"),
            observations=(observation(), observation(tenant_id="tenant-b")),
            verified_at=NOW + timedelta(hours=1),
        )


@pytest.mark.parametrize("tampered_record", ["plan", "execution"])
def test_stored_plan_and_execution_tenant_mismatch_is_rejected(tampered_record):
    ctx, _, service, _, decision, _, _ = harness()
    plan = create_plan(service, ctx, decision)
    execution = execute(service, ctx)
    if tampered_record == "plan":
        service._plans[service._plan_key(ctx, "plan-1")] = replace(plan, tenant_id="tenant-b")
    else:
        service._executions[service._execution_key(ctx, "exec-1")] = replace(
            execution, tenant_id="tenant-b"
        )
    with pytest.raises(ExecutionOutcomeError, match="tenant boundary"):
        service.verify_outcome(
            ctx,
            "exec-1",
            verification_id="verify-tampered",
            verifier=actor("verifier"),
            observations=(observation(),),
            verified_at=NOW + timedelta(hours=1),
        )


class CountingAdapter(MockExecutionAdapter):
    def __init__(self):
        self.calls = 0
        self.tasks = None

    def execute_stage(self, stage, tasks, context):
        self.calls += 1
        self.tasks = tasks
        return super().execute_stage(stage, tasks, context)


class MissingIdentityAdapter(CountingAdapter):
    adapter_name = ""


@pytest.mark.parametrize(
    ("adapter", "connector_id"),
    [(CountingAdapter(), "wrong"), (MissingIdentityAdapter(), "mock")],
)
def test_connector_identity_failure_blocks_before_adapter_execution(adapter, connector_id):
    ctx, _, service, _, decision, _, _ = harness(adapter=adapter)
    with pytest.raises(ExecutionOutcomeError, match="connector identity"):
        create_plan(service, ctx, decision, connector_id=connector_id)
    assert adapter.calls == 0


def test_explicit_nested_target_path_is_supported():
    ctx, _, service, _, decision, _, _ = harness()
    plan = create_plan(
        service,
        ctx,
        decision,
        parameters={"target": {"resource_id": "app-1"}},
        target_path=("target", "resource_id"),
    )
    assert plan.target_path == ("target", "resource_id")
    assert execute(service, ctx).state is ExecutionState.AWAITING_VERIFICATION


@pytest.mark.parametrize(
    ("parameters", "target_path", "message"),
    [
        ({"resource_id": "app-2"}, ("resource_id",), "exactly match"),
        ({"other": "app-1"}, ("resource_id",), "missing"),
        (
            {"resource_id": "app-1", "target_id": "app-2"},
            ("resource_id",),
            "ambiguous",
        ),
    ],
)
def test_wrong_missing_or_ambiguous_target_is_rejected(parameters, target_path, message):
    ctx, _, service, _, decision, _, _ = harness()
    with pytest.raises(ExecutionOutcomeError, match=message):
        create_plan(
            service,
            ctx,
            decision,
            parameters=parameters,
            target_path=target_path,
        )


def test_parameters_are_deeply_immutable_and_hash_bound_to_execution():
    adapter = CountingAdapter()
    ctx, _, service, _, decision, _, _ = harness(adapter=adapter)
    parameters = {
        "resource_id": "app-1",
        "nested": {"items": [1, {"flag": True}], "labels": {"b", "a"}},
    }
    plan = create_plan(service, ctx, decision, parameters=parameters)
    original_hash = plan.plan_hash
    parameters["nested"]["items"][1]["flag"] = False
    parameters["nested"]["items"].append(3)
    assert plan.parameters["nested"]["items"] == (1, {"flag": True})
    assert plan.parameters["nested"]["labels"] == ("a", "b")
    with pytest.raises(TypeError):
        plan.parameters["nested"]["items"][1]["flag"] = False
    execute(service, ctx)
    assert plan.plan_hash == original_hash
    assert adapter.tasks[0]["Parameters"]["nested"]["items"] == (1, {"flag": True})
    assert service.reconstruct(ctx, "exec-1")["plan"]["parameters"]["nested"]["items"] == [
        1,
        {"flag": True},
    ]


def test_unsupported_parameter_object_is_rejected():
    ctx, _, service, _, decision, _, _ = harness()
    with pytest.raises(ExecutionOutcomeError, match="unsupported"):
        create_plan(
            service,
            ctx,
            decision,
            parameters={"resource_id": "app-1", "unsafe": object()},
        )


def test_reconstruction_contains_complete_authority_and_evidence_chain():
    ctx, _, service, _, decision, _, _ = harness()
    create_plan(service, ctx, decision)
    execute(service, ctx)
    result = service.reconstruct(ctx, "exec-1")
    chain = result["authority_chain"]
    assert chain["recommendation"] == {"id": "rec-1", "version": 1}
    assert chain["evidence_package"]["id"] == "pkg-1"
    assert len(chain["evidence_package"]["hash"]) == 64
    assert chain["execution_authorization"]["target"] == "app-1"
    assert result["plan"]["compensation_plan"]["rollback_steps"]


def test_integrated_wp013_safety_path_and_critical_fail_closed_variants():
    ctx, _, service, _, decision, _, _ = harness()
    plan = create_plan(
        service,
        ctx,
        decision,
        parameters={"resource_id": "app-1", "nested": {"steps": ["remediate"]}},
    )
    command = execute(service, ctx)
    assert command.state is ExecutionState.AWAITING_VERIFICATION
    verified = service.verify_outcome(
        ctx,
        "exec-1",
        verification_id="verify-integrated",
        verifier=actor("independent-verifier"),
        observations=(observation(),),
        verified_at=NOW + timedelta(hours=1),
    )
    assert verified.state is OutcomeState.VERIFIED
    assert plan.parameters["nested"]["steps"] == ("remediate",)

    with pytest.raises(ExecutionOutcomeError, match="tenant scope"):
        service.get_plan(context("foreign"), "plan-1")

    ctx, _, service, _, decision, _, _ = harness()
    with pytest.raises(ExecutionOutcomeError, match="connector identity"):
        create_plan(service, ctx, decision, connector_id="wrong")

    ctx, _, service, _, decision, _, _ = harness()
    with pytest.raises(ExecutionOutcomeError, match="exactly match"):
        create_plan(service, ctx, decision, parameters={"resource_id": "app-2"})

    ctx, _, service, _, decision, _, _ = harness(
        authority_expires=NOW + timedelta(minutes=5)
    )
    create_plan(service, ctx, decision)
    with pytest.raises(ExecutionOutcomeError, match="not active"):
        service.execute(
            ctx,
            "plan-1",
            execution_id="exec-expired",
            actor=actor("executor"),
            executed_at=NOW + timedelta(minutes=10),
        )

    ctx, _, service, _, decision, _, _ = harness()
    create_plan(service, ctx, decision)
    execute(service, ctx)
    contradictory = service.verify_outcome(
        ctx,
        "exec-1",
        verification_id="verify-contradictory",
        verifier=actor("independent-verifier"),
        observations=(observation(30), observation(80)),
        verified_at=NOW + timedelta(hours=1),
    )
    assert contradictory.state is OutcomeState.NOT_VERIFIED
