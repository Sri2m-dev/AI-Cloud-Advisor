from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest

from business_service_posture import (
    BusinessServicePosture,
    PostureAvailability,
    PostureDimension,
    PostureDimensionResult,
)
from data_fabric.foundation import TenantContext
from governed_queries import (
    EvidenceReference,
    EvidenceState,
    GovernedQueryResult,
    QueryPath,
)
from governed_queries.models import QueryMetadata
from policy_approval import (
    Approval,
    ApprovalState,
    AuthorityScope,
    ExceptionState,
    PolicyEvaluation,
    PolicyEvaluationResult,
    PolicyException,
)
from portfolio_risk_decision_product import (
    DomainEvidenceReference,
    DomainProfile,
    InputState,
    LifecycleSignal,
    PortfolioRiskDecisionError,
    PortfolioRiskDecisionProduct,
    RationalizationDisposition,
    RiskPriority,
    RiskSignal,
    ScenarioReference,
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

NOW = datetime(2026, 7, 25, 10, tzinfo=timezone.utc)


def context(suffix: str = "a") -> TenantContext:
    return TenantContext(f"org-{suffix}", f"tenant-{suffix}")


def actor(name: str) -> Actor:
    return Actor(name, ActorType.HUMAN)


def evidence(ctx: TenantContext, name: str) -> DomainEvidenceReference:
    return DomainEvidenceReference(
        f"evidence-{name}",
        ctx.organization_id,
        ctx.tenant_id,
        "canonical-registry",
        name,
        f"hash-{name}",
        NOW,
        f"lineage-{name}",
        f"provenance-{name}",
    )


def lifecycle(
    ctx: TenantContext,
    *,
    state: InputState = InputState.AVAILABLE,
    lifecycle_state: str = "active",
) -> LifecycleSignal:
    return LifecycleSignal(
        ctx.organization_id,
        ctx.tenant_id,
        "app-1",
        "application",
        lifecycle_state,
        3,
        NOW,
        state,
        evidence(ctx, "lifecycle"),
    )


def risk(
    ctx: TenantContext,
    *,
    likelihood: float = 50,
    impact: float = 50,
    state: InputState = InputState.AVAILABLE,
) -> RiskSignal:
    return RiskSignal(
        ctx.organization_id,
        ctx.tenant_id,
        "app-1",
        "risk-1",
        likelihood,
        impact,
        NOW,
        state,
        evidence(ctx, "risk"),
    )


def posture(ctx: TenantContext) -> BusinessServicePosture:
    dimensions = {
        dimension: PostureDimensionResult(
            dimension,
            PostureAvailability.AVAILABLE,
            80,
            "business-service-posture",
            NOW,
            0,
            (),
            {"status": "available"},
            1.0,
            "available",
        )
        for dimension in PostureDimension
    }
    return BusinessServicePosture(
        ctx.organization_id, ctx.tenant_id, "svc-1", 2, 4, NOW, dimensions
    )


def graph(
    ctx: TenantContext,
    *,
    partial: bool = False,
    include_path: bool = True,
    evidence_state: EvidenceState = EvidenceState.AVAILABLE,
) -> GovernedQueryResult:
    metadata = QueryMetadata(
        "impact_analysis",
        ctx.organization_id,
        ctx.tenant_id,
        {"entity_id": "app-1"},
        9,
        "projection-hash",
        NOW,
        NOW,
        None,
        100,
        4,
        False,
        None,
        partial,
        ("truncated",) if partial else (),
    )
    graph_evidence = EvidenceReference(
        "app-1",
        ctx.organization_id,
        ctx.tenant_id,
        None if evidence_state is EvidenceState.MISSING else "graph-evidence",
        None if evidence_state is EvidenceState.MISSING else NOW,
        evidence_state,
        "knowledge-graph",
        "graph-lineage",
        "graph-provenance",
    )
    return GovernedQueryResult(
        metadata,
        ("app-1", "svc-1", "dep-1"),
        ("rel-1", "rel-2"),
        {"app-1": 3, "dep-1": 1, "svc-1": 2},
        {"rel-1": 1, "rel-2": 1},
        (QueryPath(("app-1", "svc-1"), ("rel-1",)),) if include_path else (),
        (graph_evidence,),
        "existing governed graph projection",
    )


def decision_chain(ctx: TenantContext):
    recommendation = Recommendation(
        "rec-1",
        ctx.organization_id,
        ctx.tenant_id,
        2,
        "portfolio risk",
        "retain",
        "controlled outcome",
        (Alternative("alt-1", "retain", "stable service"),),
        "package-1",
        "package-hash",
        actor("proposer"),
        RecommendationState.APPROVED,
        NOW,
        assumptions=("graph projection current",),
    )
    decision = Decision(
        "decision-1",
        ctx.organization_id,
        ctx.tenant_id,
        recommendation.recommendation_id,
        recommendation.version,
        DecisionDisposition.APPROVE,
        actor("decider"),
        "AUTHORIZED",
        "AVAILABLE",
        "approved",
        NOW,
    )
    scope = AuthorityScope("profile", "application", "app-1")
    evaluation = PolicyEvaluation(
        "evaluation-1",
        ctx.organization_id,
        ctx.tenant_id,
        decision.decision_id,
        decision.recommendation_version,
        "package-1",
        "package-hash",
        "policy-1",
        3,
        "deterministic-v1",
        NOW,
        PolicyEvaluationResult.ALLOW,
        ("all rules passed",),
        {"evidence": "available"},
        {"risk": 25},
        scope,
        "input-hash",
    )
    approval = Approval(
        "approval-1",
        ctx.organization_id,
        ctx.tenant_id,
        1,
        decision.decision_id,
        decision.recommendation_version,
        evaluation.evaluation_id,
        actor("requester"),
        actor("approver"),
        scope,
        NOW,
        NOW,
        NOW + timedelta(days=7),
        ApprovalState.ACTIVE,
    )
    return recommendation, decision, evaluation, approval


def inputs(ctx: TenantContext | None = None) -> dict:
    ctx = ctx or context()
    recommendation, decision, evaluation, authority = decision_chain(ctx)
    return {
        "case_id": "case-1",
        "recommendation": recommendation,
        "decision": decision,
        "evaluation": evaluation,
        "authority": authority,
        "posture": posture(ctx),
        "lifecycle": lifecycle(ctx),
        "risk": risk(ctx),
        "graph": graph(ctx),
        "created_at": NOW,
    }


def test_portfolio_profile_reuses_one_decision_and_governed_graph():
    ctx = context()
    product = PortfolioRiskDecisionProduct(ctx)
    case = product.create_portfolio_case(**inputs(ctx))
    assert case.profile is DomainProfile.PORTFOLIO_RATIONALIZATION
    assert case.rationalization is RationalizationDisposition.RETAIN
    assert case.decision_id == "decision-1"
    assert case.policy_evaluation_id == "evaluation-1"
    assert case.query_paths == ("rel-1",)
    assert case.evidence_ids == (
        "evidence-lifecycle",
        "evidence-risk",
        "graph-evidence",
    )


@pytest.mark.parametrize(
    ("changes", "duplicates", "expected"),
    [
        ({"lifecycle_state": "retired"}, (), RationalizationDisposition.RETIRE),
        ({}, ("app-duplicate",), RationalizationDisposition.CONSOLIDATE),
        ({"risk_score": 80}, (), RationalizationDisposition.MODERNIZE),
    ],
)
def test_rationalization_is_deterministic(changes, duplicates, expected):
    ctx = context()
    values = inputs(ctx)
    if "lifecycle_state" in changes:
        values["lifecycle"] = lifecycle(ctx, lifecycle_state=changes["lifecycle_state"])
    if "risk_score" in changes:
        values["risk"] = risk(ctx, likelihood=100, impact=changes["risk_score"])
    result = PortfolioRiskDecisionProduct(ctx).create_portfolio_case(
        **values, duplicate_candidate_ids=duplicates
    )
    assert result.rationalization is expected


@pytest.mark.parametrize(
    ("likelihood", "impact", "expected"),
    [
        (90, 90, RiskPriority.CRITICAL),
        (70, 80, RiskPriority.HIGH),
        (40, 50, RiskPriority.MEDIUM),
        (10, 10, RiskPriority.LOW),
    ],
)
def test_risk_priority_is_explicit_and_deterministic(likelihood, impact, expected):
    ctx = context()
    values = inputs(ctx)
    values["risk"] = risk(ctx, likelihood=likelihood, impact=impact)
    result = PortfolioRiskDecisionProduct(ctx).create_risk_case(**values)
    assert result.risk_priority is expected


@pytest.mark.parametrize(
    ("field", "replacement", "missing"),
    [
        ("lifecycle", None, "lifecycle"),
        ("risk", None, "risk"),
        ("risk", InputState.STALE, "fresh_risk"),
    ],
)
def test_missing_or_stale_domain_inputs_are_indeterminate(field, replacement, missing):
    ctx = context()
    values = inputs(ctx)
    values[field] = (
        risk(ctx, state=replacement)
        if field == "risk" and replacement is not None
        else replacement
    )
    result = PortfolioRiskDecisionProduct(ctx).create_risk_case(**values)
    assert result.risk_priority is RiskPriority.INDETERMINATE
    assert missing in result.missing_inputs


@pytest.mark.parametrize(
    ("partial", "include_path", "state", "missing"),
    [
        (True, True, EvidenceState.AVAILABLE, "complete_graph"),
        (False, False, EvidenceState.AVAILABLE, "dependency_or_impact_paths"),
        (False, True, EvidenceState.MISSING, "graph_evidence"),
    ],
)
def test_partial_graph_disclosure_never_fabricates_a_profile(
    partial, include_path, state, missing
):
    ctx = context()
    values = inputs(ctx)
    values["graph"] = graph(
        ctx, partial=partial, include_path=include_path, evidence_state=state
    )
    result = PortfolioRiskDecisionProduct(ctx).create_portfolio_case(**values)
    assert result.rationalization is RationalizationDisposition.INDETERMINATE
    assert missing in result.missing_inputs


@pytest.mark.parametrize(
    "field",
    [
        "recommendation",
        "decision",
        "evaluation",
        "authority",
        "posture",
        "lifecycle",
        "risk",
        "graph",
    ],
)
def test_cross_tenant_inputs_are_rejected(field):
    own, foreign = context(), context("b")
    values, foreign_values = inputs(own), inputs(foreign)
    values[field] = foreign_values[field]
    with pytest.raises(PortfolioRiskDecisionError, match="tenant|graph"):
        PortfolioRiskDecisionProduct(own).create_portfolio_case(**values)


def test_policy_and_authority_must_bind_exact_approved_decision():
    ctx = context()
    values = inputs(ctx)
    values["evaluation"] = replace(
        values["evaluation"], result=PolicyEvaluationResult.DENY
    )
    with pytest.raises(PortfolioRiskDecisionError, match="ALLOW"):
        PortfolioRiskDecisionProduct(ctx).create_portfolio_case(**values)
    values = inputs(ctx)
    values["authority"] = replace(values["authority"], state=ApprovalState.REVOKED)
    with pytest.raises(PortfolioRiskDecisionError, match="not active"):
        PortfolioRiskDecisionProduct(ctx).create_portfolio_case(**values)


def test_inactive_policy_exception_is_rejected():
    ctx = context()
    values = inputs(ctx)
    approval = values["authority"]
    values["authority"] = PolicyException(
        "exception-1",
        ctx.organization_id,
        ctx.tenant_id,
        1,
        approval.decision_id,
        approval.decision_version,
        approval.evaluation_id,
        "policy-1",
        3,
        "rule-1",
        actor("requester"),
        actor("approver"),
        "temporary",
        "package-1",
        approval.scope,
        NOW,
        NOW,
        NOW + timedelta(days=1),
        ExceptionState.EXPIRED,
    )
    with pytest.raises(PortfolioRiskDecisionError, match="not active"):
        PortfolioRiskDecisionProduct(ctx).create_portfolio_case(**values)


def test_scope_and_entity_attribution_are_exact():
    ctx = context()
    values = inputs(ctx)
    values["authority"] = replace(
        values["authority"],
        scope=AuthorityScope("profile", "application", "other"),
    )
    with pytest.raises(PortfolioRiskDecisionError, match="scope"):
        PortfolioRiskDecisionProduct(ctx).create_portfolio_case(**values)
    values = inputs(ctx)
    values["graph"] = replace(values["graph"], entity_ids=("app-1", "dep-1"))
    with pytest.raises(PortfolioRiskDecisionError, match="business service"):
        PortfolioRiskDecisionProduct(ctx).create_portfolio_case(**values)


def test_scenario_is_attribution_not_authority_and_is_tenant_bound():
    ctx = context()
    values = inputs(ctx)
    values["scenario"] = ScenarioReference(
        "scenario-1",
        ctx.organization_id,
        ctx.tenant_id,
        "existing-digital-twin",
        "v2",
        "scenario-hash",
        NOW,
        ("app-1",),
        ("demand stable",),
        ("scenario-lineage",),
        ("scenario-provenance",),
    )
    result = PortfolioRiskDecisionProduct(ctx).create_portfolio_case(**values)
    assert result.scenario_hash == "scenario-hash"
    assert result.authority_id == "approval-1"
    values["scenario"] = replace(
        values["scenario"], organization_id="org-b", tenant_id="tenant-b"
    )
    values["case_id"] = "case-2"
    with pytest.raises(PortfolioRiskDecisionError, match="scenario crosses tenant"):
        PortfolioRiskDecisionProduct(ctx).create_portfolio_case(**values)


def test_reconstruction_and_queries_are_deterministic_and_bounded():
    ctx = context()
    product = PortfolioRiskDecisionProduct(ctx)
    portfolio = product.create_portfolio_case(**inputs(ctx))
    risk_values = inputs(ctx)
    risk_values["case_id"] = "risk-case"
    risk_case = product.create_risk_case(**risk_values)
    first = product.reconstruct(portfolio.case_id)
    assert first == product.reconstruct(portfolio.case_id)
    assert first["single_decision_contract"]["decision_id"] == "decision-1"
    assert first["graph"]["checkpoint"] == 9
    assert first["evidence"]["lineage"]
    assert product.cases_for_decision("decision-1") == (portfolio, risk_case)
    assert product.cases_for_service("svc-1") == (portfolio, risk_case)
    assert product.prioritized_risks() == (risk_case,)


def test_revision_preserves_governed_decision_chain_and_history():
    ctx = context()
    product = PortfolioRiskDecisionProduct(ctx)
    values = inputs(ctx)
    first = product.create_portfolio_case(**values)
    second = product.revise_case(
        first.case_id,
        recommendation=values["recommendation"],
        decision=values["decision"],
        reason="refresh presentation",
        created_at=NOW + timedelta(hours=1),
    )
    assert second.version == 2
    assert product.history(first.case_id) == (first, second)
    with pytest.raises(PortfolioRiskDecisionError, match="cannot replace"):
        product.revise_case(
            first.case_id,
            recommendation=replace(values["recommendation"], version=3),
            decision=replace(values["decision"], recommendation_version=3),
            reason="replace decision",
        )


def test_same_inputs_have_same_case_hash_without_persistence_or_schema():
    ctx = context()
    first = PortfolioRiskDecisionProduct(ctx).create_portfolio_case(**inputs(ctx))
    second = PortfolioRiskDecisionProduct(ctx).create_portfolio_case(**inputs(ctx))
    assert first.case_hash == second.case_hash
