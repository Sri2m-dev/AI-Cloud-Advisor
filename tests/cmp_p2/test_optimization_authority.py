from __future__ import annotations

from dataclasses import replace
from decimal import Decimal
from types import SimpleNamespace

import pytest

from components.optimization_governance import OptimizationGovernanceController
from services.ai_copilot_service import AICopilotService
from services.canonical_optimization_service import CanonicalOptimizationService
from services.executive_workspace_composition_service import ExecutiveWorkspaceCompositionService
from services.savings_governance_service import SavingsGovernanceService
from universal_evidence.optimization import (
    CanonicalOptimizationRepository,
    GovernedOptimizationRepository,
    OpportunityState,
    OpportunityType,
    OptimizationEvidence,
    OptimizationGovernanceError,
    aggregate_portfolio,
    detect_opportunity,
)
from universal_evidence.persistence import LifecycleScope, SQLiteLifecycleRepository


def evidence(
    kind,
    *,
    entity="entity-1",
    cost="100",
    currency="USD",
    signals=(),
    fingerprints=("evidence-v1",),
    observations=("finobs-1",),
):
    return OptimizationEvidence(
        kind,
        "org-1",
        "tenant-1",
        "prospect-1",
        "analysis-1",
        entity,
        "RESOURCE" if "LICENSE" not in kind.value else "APPLICATION",
        fingerprints,
        ("evidence-ref-1",),
        ("lineage-1",),
        ("provenance-1",),
        Decimal(cost) if cost is not None else None,
        "MONTHLY",
        currency,
        "currency-decision-1" if currency else None,
        observations,
        tuple(signals),
    )


IDLE = (
    ("utilization_window_days", 30),
    ("average_utilization", 2),
    ("peak_utilization", 12),
    ("activity_state", "IDLE"),
    ("shutdown_feasible", True),
)
RIGHTSIZE = (
    ("utilization_window_days", 30),
    ("peak_utilization", 55),
    ("current_configuration", "fictional-large"),
    ("target_configuration", "fictional-medium"),
    ("target_cost", "62"),
    ("target_cost_period", "MONTHLY"),
    ("target_currency", "USD"),
)
STORAGE = (
    ("attachment_state", "UNATTACHED"),
    ("observation_window_days", 45),
    ("retention_state", "DISPOSABLE"),
    ("deletion_approved", True),
)
SAAS = (
    ("purchased_seats", 20),
    ("active_seats", 12),
    ("usage_window_days", 60),
    ("removable_unit_cost", "9"),
    ("unit_cost_period", "MONTHLY"),
    ("unit_currency", "USD"),
    ("contract_state", "REMOVABLE"),
)


def test_three_production_paths_have_reproducible_evidence_derived_savings():
    idle = detect_opportunity(evidence(OpportunityType.IDLE_COMPUTE, signals=IDLE))
    rightsize = detect_opportunity(evidence(OpportunityType.RIGHTSIZE_COMPUTE, signals=RIGHTSIZE))
    storage = detect_opportunity(
        evidence(OpportunityType.UNATTACHED_STORAGE, entity="disk-1", cost="18", signals=STORAGE)
    )
    saas = detect_opportunity(
        evidence(OpportunityType.UNUSED_LICENSE, entity="fictional-saas", cost="180", signals=SAAS)
    )
    assert (idle.potential_savings, idle.calculation_model) == (
        Decimal("100"),
        "REMOVABLE_GOVERNED_COST",
    )
    assert (rightsize.potential_savings, dict(rightsize.calculation_inputs)["target_cost"]) == (
        Decimal("38"),
        "62",
    )
    assert storage.potential_savings == Decimal("18")
    assert (saas.potential_savings, saas.savings_percentage) == (Decimal("72"), Decimal("40.00"))
    assert all(
        item.calculation_model_version == "cmp-p2-calculation-1"
        for item in (idle, rightsize, storage, saas)
    )


def test_healthy_evidence_emits_no_recommendation():
    signals = tuple(
        (key, 80 if key in {"average_utilization", "peak_utilization"} else value)
        for key, value in IDLE
    )
    assert detect_opportunity(evidence(OpportunityType.IDLE_COMPUTE, signals=signals)) is None


@pytest.mark.parametrize(
    "change,reason",
    [
        ({"current_cost": None}, "MISSING_GOVERNED_CURRENT_COST"),
        ({"currency": None}, "MISSING_GOVERNED_CURRENCY"),
    ],
)
def test_missing_financial_authority_fails_closed(change, reason):
    kwargs = {"cost": "100", "currency": "USD"}
    kwargs["cost" if "current_cost" in change else "currency"] = None
    item = detect_opportunity(evidence(OpportunityType.IDLE_COMPUTE, signals=IDLE, **kwargs))
    assert item.state is OpportunityState.BLOCKED
    assert item.potential_savings is None
    assert reason in item.eligibility_reason_codes


def test_false_positive_compute_and_storage_controls():
    short = detect_opportunity(
        evidence(
            OpportunityType.IDLE_COMPUTE,
            signals=tuple((k, 2 if k == "utilization_window_days" else v) for k, v in IDLE),
        )
    )
    bursty = detect_opportunity(
        evidence(
            OpportunityType.IDLE_COMPUTE,
            signals=tuple((k, 95 if k == "peak_utilization" else v) for k, v in IDLE),
        )
    )
    dr = detect_opportunity(
        evidence(OpportunityType.IDLE_COMPUTE, signals=IDLE + (("dr_standby", True),))
    )
    retained = detect_opportunity(
        evidence(
            OpportunityType.UNATTACHED_STORAGE,
            signals=tuple((k, "RETAIN" if k == "retention_state" else v) for k, v in STORAGE),
        )
    )
    assert short.state is OpportunityState.BLOCKED and short.potential_savings is None
    assert bursty is None
    assert dr.state is OpportunityState.BLOCKED
    assert retained.state is OpportunityState.BLOCKED


def test_missing_target_price_and_non_cancellable_saas_are_blocked():
    rightsize = detect_opportunity(
        evidence(
            OpportunityType.RIGHTSIZE_COMPUTE,
            signals=tuple(pair for pair in RIGHTSIZE if pair[0] != "target_cost"),
        )
    )
    saas = detect_opportunity(
        evidence(
            OpportunityType.UNUSED_LICENSE,
            signals=tuple((k, "FIXED_TERM" if k == "contract_state" else v) for k, v in SAAS),
        )
    )
    assert (
        rightsize.potential_savings is None
        and "MISSING_TARGET_COST" in rightsize.eligibility_reason_codes
    )
    assert (
        saas.potential_savings is None and "CONTRACT_NOT_REMOVABLE" in saas.eligibility_reason_codes
    )


def test_incompatible_currency_or_period_blocks_calculation():
    wrong_period = detect_opportunity(
        evidence(
            OpportunityType.RIGHTSIZE_COMPUTE,
            signals=tuple(
                (key, "ANNUAL" if key == "target_cost_period" else value)
                for key, value in RIGHTSIZE
            ),
        )
    )
    wrong_currency = detect_opportunity(
        evidence(
            OpportunityType.UNUSED_LICENSE,
            signals=tuple((key, "EUR" if key == "unit_currency" else value) for key, value in SAAS),
        )
    )
    assert wrong_period.potential_savings is None
    assert wrong_currency.potential_savings is None


def test_overlap_uses_one_cost_basis_and_currency_totals_remain_separate():
    idle = detect_opportunity(evidence(OpportunityType.IDLE_COMPUTE, signals=IDLE))
    rightsize = detect_opportunity(evidence(OpportunityType.RIGHTSIZE_COMPUTE, signals=RIGHTSIZE))
    eur = detect_opportunity(
        evidence(
            OpportunityType.UNATTACHED_STORAGE,
            entity="disk-eur",
            cost="20",
            currency="EUR",
            signals=STORAGE,
            observations=("finobs-eur",),
        )
    )
    portfolio = aggregate_portfolio((idle, rightsize, eur))
    assert portfolio.totals_by_currency == (("EUR", Decimal("20")), ("USD", Decimal("100")))
    assert rightsize.opportunity_id in portfolio.excluded_overlap_ids


def test_governance_restart_history_and_realization_are_separate(tmp_path):
    database = tmp_path / "cmp-p2.db"
    scope = LifecycleScope("org-1", "tenant-1", "prospect-1", "analysis-1")
    item = detect_opportunity(evidence(OpportunityType.UNUSED_LICENSE, signals=SAAS))
    repo = GovernedOptimizationRepository(SQLiteLifecycleRepository(database))
    repo.save(item)
    for state in (
        OpportunityState.PROPOSED,
        OpportunityState.UNDER_REVIEW,
        OpportunityState.APPROVED,
        OpportunityState.IMPLEMENTING,
        OpportunityState.IMPLEMENTED,
        OpportunityState.VERIFYING,
    ):
        item = repo.transition(
            scope,
            item.opportunity_id,
            state,
            actor_id="authorized-user",
            actor_role="admin",
            reason=f"move to {state.value}",
        )
    assert item.realized_savings is None
    restarted = GovernedOptimizationRepository(SQLiteLifecycleRepository(database))
    reconstructed = restarted.get(scope, item.opportunity_id)
    assert reconstructed.fingerprint == item.fingerprint and reconstructed.realized_savings is None
    realized = restarted.verify_realization(
        scope,
        item.opportunity_id,
        actor_id="finance-verifier",
        actor_role="executive",
        post_change_cost="40",
        evidence_references=("post-change-bill",),
        comparable_period="MONTHLY",
        currency="USD",
        attribution_confirmed=True,
        reason="verified comparable bill",
    )
    assert realized.realized_savings == Decimal("60")
    assert realized.state is OpportunityState.PARTIALLY_REALIZED
    assert len(restarted.history(scope, item.opportunity_id)) == 7


def test_realization_cannot_be_inferred_from_approval_or_implementation(tmp_path):
    scope = LifecycleScope("org-1", "tenant-1", "prospect-1", "analysis-1")
    repo = GovernedOptimizationRepository(SQLiteLifecycleRepository(tmp_path / "states.db"))
    item = repo.save(detect_opportunity(evidence(OpportunityType.IDLE_COMPUTE, signals=IDLE)))
    for state in (
        OpportunityState.PROPOSED,
        OpportunityState.UNDER_REVIEW,
        OpportunityState.APPROVED,
        OpportunityState.IMPLEMENTING,
        OpportunityState.IMPLEMENTED,
    ):
        item = repo.transition(
            scope,
            item.opportunity_id,
            state,
            actor_id="user",
            actor_role="admin",
            reason="governed transition",
        )
    assert item.realized_savings is None
    with pytest.raises(OptimizationGovernanceError):
        repo.verify_realization(
            scope,
            item.opportunity_id,
            actor_id="user",
            actor_role="admin",
            post_change_cost="0",
            evidence_references=(),
            comparable_period="MONTHLY",
            currency="USD",
            attribution_confirmed=True,
            reason="missing evidence",
        )


def test_evidence_change_supersedes_without_mutation(tmp_path):
    scope = LifecycleScope("org-1", "tenant-1", "prospect-1", "analysis-1")
    repo = GovernedOptimizationRepository(SQLiteLifecycleRepository(tmp_path / "supersede.db"))
    old = repo.save(detect_opportunity(evidence(OpportunityType.IDLE_COMPUTE, signals=IDLE)))
    new = detect_opportunity(
        evidence(OpportunityType.IDLE_COMPUTE, signals=IDLE, fingerprints=("evidence-v2",))
    )
    replacement = repo.supersede(old, new, actor_id="policy", reason="material evidence change")
    assert replacement.version == 2
    assert repo.get(scope, old.opportunity_id).superseded_by == replacement.opportunity_id


def test_publication_is_tenant_safe_and_bounded_consumers_share_authority(tmp_path):
    item = detect_opportunity(
        evidence(OpportunityType.UNATTACHED_STORAGE, entity="disk-1", cost="18", signals=STORAGE)
    )
    repository = CanonicalOptimizationRepository(tmp_path / "publication.db")
    context = SimpleNamespace(organization_id="org-1", tenant_id="tenant-1")
    repository.publish(item, context)
    summary = repository.savings_summary(context)
    assert summary["potential_by_currency"] == (("USD", Decimal("18")),)
    assert summary["realized_by_currency"] == ()
    assert (
        "disk-1",
        "HAS_OPTIMIZATION_OPPORTUNITY",
        item.opportunity_id,
    ) in repository.relationships(context)
    service = CanonicalOptimizationService(repository)
    assert service.savings_governance(context) == summary
    assert (
        service.executive_summary(context)["governed_potential_savings"]
        == summary["potential_by_currency"]
    )
    assert service.ask(context, "potential_savings") == summary["potential_by_currency"]
    with pytest.raises(PermissionError):
        repository.publish(item, SimpleNamespace(organization_id="org-2", tenant_id="tenant-2"))


def test_stale_cross_scope_and_static_demo_inputs_cannot_enter_authority(tmp_path):
    stale = detect_opportunity(
        evidence(OpportunityType.IDLE_COMPUTE, signals=IDLE + (("evidence_stale", True),))
    )
    assert stale.state is OpportunityState.BLOCKED
    repo = GovernedOptimizationRepository(SQLiteLifecycleRepository(tmp_path / "scope.db"))
    repo.save(stale)
    with pytest.raises(Exception):
        repo.get(
            LifecycleScope("org-2", "tenant-2", "prospect-1", "analysis-1"), stale.opportunity_id
        )
    assert "estimated_savings" not in stale.__dataclass_fields__


def _production_authority(tmp_path, name="governance.db"):
    database = tmp_path / name
    governance = GovernedOptimizationRepository(SQLiteLifecycleRepository(database))
    publication = CanonicalOptimizationRepository(database)
    context = SimpleNamespace(organization_id="org-1", tenant_id="tenant-1")
    item = detect_opportunity(evidence(OpportunityType.UNUSED_LICENSE, signals=SAAS))
    governance.save(item)
    publication.publish(item, context)
    return database, governance, publication, context, item


def test_production_approve_and_cross_consumer_restart_consistency(tmp_path):
    database, governance, publication, context, item = _production_authority(tmp_path)
    controller = OptimizationGovernanceController(governance, publication)
    approved = controller.act(
        item,
        "APPROVE",
        context=context,
        actor_id="authorized@example.test",
        actor_role="executive",
        reason="evidence and calculation reviewed",
    )
    assert approved.state is OpportunityState.APPROVED
    restarted_publication = CanonicalOptimizationRepository(database)
    restarted_governance = GovernedOptimizationRepository(SQLiteLifecycleRepository(database))
    scope = LifecycleScope("org-1", "tenant-1", "prospect-1", "analysis-1")
    assert restarted_governance.get(scope, item.opportunity_id).state is OpportunityState.APPROVED
    savings = SavingsGovernanceService.get_canonical_authority(context, restarted_publication)
    executive = ExecutiveWorkspaceCompositionService.get_canonical_optimization(
        context, restarted_publication
    )
    ask = AICopilotService.ask_canonical_optimization(
        context, "approved_savings", restarted_publication
    )
    assert savings["approved_by_currency"] == executive["governed_approved_savings"] == ask
    assert savings["realized_by_currency"] == ()


def test_rejection_is_historical_excluded_and_restarts(tmp_path):
    database, governance, publication, context, item = _production_authority(tmp_path, "reject.db")
    rejected = OptimizationGovernanceController(governance, publication).act(
        item,
        "REJECT",
        context=context,
        actor_id="reviewer@example.test",
        actor_role="client_admin",
        reason="workload is contractually retained",
    )
    assert rejected.state is OpportunityState.REJECTED
    service = CanonicalOptimizationService(CanonicalOptimizationRepository(database))
    assert service.savings_governance(context)["approved_by_currency"] == ()
    assert service.rejected(context)[0].opportunity_id == item.opportunity_id
    scope = LifecycleScope("org-1", "tenant-1", "prospect-1", "analysis-1")
    restarted = GovernedOptimizationRepository(SQLiteLifecycleRepository(database))
    assert restarted.get(scope, item.opportunity_id).state is OpportunityState.REJECTED
    assert len(restarted.history(scope, item.opportunity_id)) == 3


def test_revision_request_preserves_history_and_can_be_superseded(tmp_path):
    _, governance, publication, context, item = _production_authority(tmp_path, "revision.db")
    revised = OptimizationGovernanceController(governance, publication).act(
        item,
        "REQUEST_REVISION",
        context=context,
        actor_id="cio@example.test",
        actor_role="cio",
        reason="target economics need refreshed evidence",
    )
    replacement = detect_opportunity(
        evidence(
            OpportunityType.UNUSED_LICENSE,
            signals=SAAS,
            fingerprints=("evidence-v2",),
        )
    )
    replacement = governance.supersede(
        revised,
        replacement,
        actor_id="optimization-policy",
        reason="refreshed governed economics",
    )
    scope = LifecycleScope("org-1", "tenant-1", "prospect-1", "analysis-1")
    assert governance.get(scope, item.opportunity_id).state is OpportunityState.SUPERSEDED
    assert replacement.version == 2
    assert (
        governance.history(scope, item.opportunity_id)[-1].to_state
        is OpportunityState.REVISION_REQUIRED
    )


def test_unauthorized_and_cross_scope_governance_fail_closed(tmp_path):
    _, governance, publication, context, item = _production_authority(tmp_path, "auth.db")
    controller = OptimizationGovernanceController(governance, publication)
    with pytest.raises(PermissionError):
        controller.act(
            item,
            "APPROVE",
            context=context,
            actor_id="viewer@example.test",
            actor_role="viewer",
            reason="forged",
        )
    forged = replace(item, tenant_id="tenant-2")
    with pytest.raises(Exception):
        controller.act(
            forged,
            "APPROVE",
            context=context,
            actor_id="admin@example.test",
            actor_role="admin",
            reason="cross tenant",
        )


def test_production_empty_authority_never_uses_legacy_demo_fallback(tmp_path):
    repository = CanonicalOptimizationRepository(tmp_path / "empty.db")
    context = SimpleNamespace(organization_id="org-1", tenant_id="tenant-1")
    summary = SavingsGovernanceService.get_canonical_authority(context, repository)
    assert summary["opportunity_count"] == 0
    assert summary["potential_by_currency"] == ()
