from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID

import pytest
from cryptography.fernet import Fernet

from auth.authenticated_tenant import AuthenticatedTenantContext
from services.enterprise_spend_service import EnterpriseSpendService
from services.prospect_data_intake_service import create_prospect_tenant
from universal_evidence.financial import (
    CanonicalFinancialRepository,
    GovernedFinancialWorkflow,
)
from universal_evidence.financial import ui as financial_ui
from universal_evidence.financial.governance import (
    FinancialDecisionKind,
    FinancialDecisionState,
    FinancialGovernanceError,
)
from universal_evidence.financial.production import configured_governed_financial_workflow
from universal_evidence.persistence import SQLiteLifecycleRepository
from universal_evidence.pilot.admission import admit_uploaded_evidence
from universal_evidence.pilot.runtime import reset_configured_runtime_cache
from universal_evidence.production_workflow import (
    persist_production_workspace,
    resumable_production_workspaces,
    resume_production_workspace,
)
from universal_evidence.security import WorkspaceAuthorizationContext

ROOT = Path("tests/fixtures/cmp_p1")
ORG = str(UUID(int=301))


def _context(org=ORG):
    return AuthenticatedTenantContext(
        org,
        "ExampleCo-Test",
        "governor-test",
        "governor@example.invalid",
        "super_admin",
        frozenset({"financial:read"}),
        org,
    )


def _admission(name="fixture_f_temporal_billing.xlsx", org=ORG, prospect="prospect-gov"):
    now = datetime.now(timezone.utc)
    tenant = SimpleNamespace(
        tenant_id=prospect,
        audit_id="audit-governance",
        expires_at=(now + timedelta(days=30)).isoformat(),
    )
    return admit_uploaded_evidence(
        tenant,
        filename="governed-financial-evidence.xlsx",
        content=(ROOT / name).read_bytes(),
        now=now,
        tenant_context=_context(org).fabric_context,
    )


def _workflow(database):
    return GovernedFinancialWorkflow(
        SQLiteLifecycleRepository(database), CanonicalFinancialRepository(database)
    )


def test_persisted_user_currency_authorizes_publication_and_restart(tmp_path):
    database = tmp_path / "financial-governance.db"
    admission = _admission()
    workflow = _workflow(database)

    proposed = workflow.analyze(admission)
    assert not proposed.authorized
    assert workflow.effective(admission, FinancialDecisionKind.DOMAIN)
    assert workflow.effective(admission, FinancialDecisionKind.SEMANTIC_MEASURE)
    assert workflow.effective(admission, FinancialDecisionKind.CURRENCY) is None

    workflow.decide(
        admission,
        FinancialDecisionKind.CURRENCY,
        FinancialDecisionState.CONFIRMED,
        "USD",
        actor_id="governor@example.invalid",
        actor_role="super_admin",
    )
    published = workflow.publish(admission, _context())
    spend = EnterpriseSpendService(
        workflow.publication_repository, cache_ttl_seconds=0
    ).get_financial_posture(_context())
    assert len(published.observations) == 6
    assert spend.cloud_spend == Decimal("54.00")

    restarted = _workflow(database)
    reconstructed = restarted.publish(admission, _context())
    restarted_spend = EnterpriseSpendService(
        restarted.publication_repository, cache_ttl_seconds=0
    ).get_financial_posture(_context())
    assert len(reconstructed.observations) == 6
    assert restarted_spend.cloud_spend == spend.cloud_spend
    assert len(restarted.history(admission, FinancialDecisionKind.CURRENCY)) == 1


def test_rejection_blocks_and_override_preserves_history(tmp_path):
    database = tmp_path / "financial-rejection.db"
    admission = _admission()
    workflow = _workflow(database)
    workflow.analyze(admission)
    rejected = workflow.decide(
        admission,
        FinancialDecisionKind.CURRENCY,
        FinancialDecisionState.REJECTED,
        "USD",
        actor_id="governor@example.invalid",
        actor_role="super_admin",
        reason="currency evidence rejected",
    )
    with pytest.raises(FinancialGovernanceError, match="blocked"):
        workflow.publish(admission, _context())
    assert not EnterpriseSpendService(
        workflow.publication_repository, cache_ttl_seconds=0
    ).get_financial_posture(_context()).has_data

    overridden = workflow.decide(
        admission,
        FinancialDecisionKind.CURRENCY,
        FinancialDecisionState.OVERRIDDEN,
        "EUR",
        actor_id="governor@example.invalid",
        actor_role="super_admin",
        reason="finance supplied authoritative currency",
    )
    result = workflow.publish(admission, _context())
    history = workflow.history(admission, FinancialDecisionKind.CURRENCY)
    assert [item.decision_id for item in history] == [
        rejected.decision_id,
        overridden.decision_id,
    ]
    assert overridden.supersedes_decision_id == rejected.decision_id
    assert {item.currency for item in result.observations} == {"EUR"}


@pytest.mark.parametrize(
    "kind",
    (FinancialDecisionKind.DOMAIN, FinancialDecisionKind.SEMANTIC_MEASURE),
)
def test_relevant_rejection_removes_stale_publication(tmp_path, kind):
    database = tmp_path / f"financial-{kind.value}.db"
    admission = _admission("fixture_a_cloud_cost.xlsx")
    workflow = _workflow(database)
    workflow.publish(admission, _context())
    assert EnterpriseSpendService(workflow.publication_repository).get_financial_posture(
        _context()
    ).has_data
    current = workflow.effective(admission, kind)
    workflow.decide(
        admission,
        kind,
        FinancialDecisionState.REJECTED,
        current.value,
        actor_id="governor@example.invalid",
        actor_role="super_admin",
        reason="governance rejection",
    )
    with pytest.raises(FinancialGovernanceError, match="blocked"):
        workflow.publish(admission, _context())
    assert not EnterpriseSpendService(
        workflow.publication_repository, cache_ttl_seconds=0
    ).get_financial_posture(_context()).has_data


def test_authority_cannot_cross_analysis_or_tenant_and_purge_removes_it(tmp_path):
    database = tmp_path / "financial-scope.db"
    first = _admission(prospect="prospect-a")
    second = _admission(prospect="prospect-b")
    workflow = _workflow(database)
    workflow.analyze(first)
    workflow.decide(
        first,
        FinancialDecisionKind.CURRENCY,
        FinancialDecisionState.CONFIRMED,
        "USD",
        actor_id="governor@example.invalid",
        actor_role="super_admin",
    )
    assert not workflow.analyze(second).authorized
    assert workflow.effective(second, FinancialDecisionKind.CURRENCY) is None

    scope = workflow._scope(first)
    workflow.lifecycle.purge_scope(
        scope, actor_id="governor@example.invalid", reason="authorized test purge"
    )
    restarted = _workflow(database)
    assert restarted.effective(first, FinancialDecisionKind.CURRENCY) is None
    assert not restarted.analyze(first).authorized


class _UiControl:
    def __init__(self, parent):
        self.parent = parent

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def button(self, label, **_kwargs):
        return self.parent.button(label)


class _Ui:
    def __init__(self, pressed):
        self.pressed = pressed
        self.messages = []

    def markdown(self, value):
        self.messages.append(value)

    def caption(self, value):
        self.messages.append(value)

    def write(self, value):
        self.messages.append(value)

    def info(self, value):
        self.messages.append(value)

    def error(self, value):
        self.messages.append(value)

    def success(self, value):
        self.messages.append(value)

    def selectbox(self, *_args, **_kwargs):
        return "USD"

    def checkbox(self, *_args, **_kwargs):
        return True

    def text_input(self, *_args, **_kwargs):
        return "authorized governance reason"

    def button(self, label, **_kwargs):
        return label == self.pressed

    def expander(self, *_args, **_kwargs):
        return _UiControl(self)

    def columns(self, count):
        return tuple(_UiControl(self) for _ in range(count))

    def rerun(self):
        raise RuntimeError("rerun")


def test_production_ui_persists_confirmation_then_publishes(monkeypatch, tmp_path):
    admission = _admission()
    workflow = _workflow(tmp_path / "financial-ui.db")
    monkeypatch.setattr(
        financial_ui, "configured_governed_financial_workflow", lambda: workflow
    )
    with pytest.raises(RuntimeError, match="rerun"):
        financial_ui.render_financial_governance(
            _Ui("Confirm financial currency"),
            admission,
            context=_context(),
            actor_id="governor@example.invalid",
            actor_role="super_admin",
        )
    decision = workflow.effective(admission, FinancialDecisionKind.CURRENCY)
    assert decision and decision.actor_id == "governor@example.invalid"

    rendered = _Ui("Publish governed financial observations")
    financial_ui.render_financial_governance(
        rendered,
        admission,
        context=_context(),
        actor_id="governor@example.invalid",
        actor_role="super_admin",
    )
    assert any("Published 6 governed observations" in str(item) for item in rendered.messages)


def test_encrypted_workspace_resume_reconstructs_financial_authority(monkeypatch, tmp_path):
    database = tmp_path / "financial-resume.db"
    prospect_root = tmp_path / "prospects"
    key = Fernet.generate_key().decode("ascii")
    monkeypatch.setenv("NEXORA_UNIVERSAL_EVIDENCE_DB", str(database))
    monkeypatch.setenv("NEXORA_PROSPECT_DATA_ROOT", str(prospect_root))
    monkeypatch.setenv("NEXORA_PROSPECT_DATA_KEY", key)
    reset_configured_runtime_cache()
    context = _context()
    tenant = create_prospect_tenant(
        "ExampleCo-Test",
        consent=True,
        actor=context.user_id,
        role=context.role,
        root=prospect_root,
        key=key,
    )
    admission = admit_uploaded_evidence(
        tenant,
        filename="provider-neutral-periods.xlsx",
        content=(ROOT / "fixture_f_temporal_billing.xlsx").read_bytes(),
        tenant_context=context,
    )
    authorization = WorkspaceAuthorizationContext.from_authenticated(context)
    persist_production_workspace(
        admission,
        prospect_tenant=tenant,
        prospect_name="ExampleCo-Test",
        input_profile="Generic governed XLSX",
        authorization=authorization,
    )
    workflow = configured_governed_financial_workflow()
    workflow.analyze(admission)
    workflow.decide(
        admission,
        FinancialDecisionKind.CURRENCY,
        FinancialDecisionState.CONFIRMED,
        "USD",
        actor_id=context.user_id,
        actor_role=context.role,
    )
    before = workflow.publish(admission, context)
    before_spend = EnterpriseSpendService(
        workflow.publication_repository, cache_ttl_seconds=0
    ).get_financial_posture(context)

    del admission, workflow
    reset_configured_runtime_cache()
    locator = resumable_production_workspaces(authorization)[0]
    resumed, _tenant, _name, _profile = resume_production_workspace(
        locator, authorization=authorization
    )
    restarted = configured_governed_financial_workflow()
    after = restarted.publish(resumed, context)
    after_spend = EnterpriseSpendService(
        restarted.publication_repository, cache_ttl_seconds=0
    ).get_financial_posture(context)
    assert len(before.observations) == len(after.observations) == 6
    assert after_spend.cloud_spend == before_spend.cloud_spend
    assert len(restarted.history(resumed, FinancialDecisionKind.CURRENCY)) == 1
    reset_configured_runtime_cache()
