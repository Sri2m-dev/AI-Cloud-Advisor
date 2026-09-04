from datetime import date, datetime, timezone
from decimal import Decimal
from types import SimpleNamespace

import pytest

from enterprise_intelligence.models import AvailabilityState, ReconciliationState
from models.contracts.enterprise_financial_posture import EnterpriseFinancialPosture
from services.enterprise_intelligence_query_service import EnterpriseIntelligenceQueryService
from services.executive_workspace_composition_service import ExecutiveWorkspaceCompositionService
from universal_evidence.pilot.governed_intelligence import AskState, GovernedAskNexoraService

CTX = SimpleNamespace(
    organization_id="org-a", tenant_id="tenant-a", authorization_scope=("executive", ())
)


class FinancialAuthority:
    def get_financial_posture(self, context, period=None, *, currency="USD"):
        assert context is CTX
        assert currency == "USD"
        total = Decimal("90") if period and period[0] == date(2026, 1, 1) else Decimal("100")
        return EnterpriseFinancialPosture(
            organization_id="org-a",
            currency="USD",
            period_start=period[0] if period else None,
            period_end=period[1] if period else None,
            generated_at=datetime.now(timezone.utc),
            import_count=1,
            source_rows=2,
            persisted_facts=2,
            total_ingested_spend=total,
            cloud_spend=total,
            resolved_spend=total,
            allocated_spend=total,
            reconciled_spend=total,
            allocation_coverage_percentage=Decimal("100"),
            reconciliation_status="reconciled",
        )

    def get_financial_evidence(self, context):
        assert context is CTX
        return (
            {
                "observation_id": "obs-1",
                "evidence_reference": "ev-1",
                "credential_reference": "must-not-leak",
            },
        )

    def get_spend_by_service(self, context, period=None):
        total = Decimal("90") if period and period[0] == date(2026, 1, 1) else Decimal("100")
        return ({"label": "Payments", "amount": total, "observation_ids": ("obs-1",)},)


class OptimizationAuthority:
    def list(self, context):
        return ()

    def savings_summary(self, context):
        return {
            "opportunity_count": 0,
            "potential_by_currency": (("USD", Decimal("0")),),
            "approved_by_currency": (),
            "implemented_by_currency": (),
            "realized_by_currency": (),
        }


@pytest.fixture
def service():
    return EnterpriseIntelligenceQueryService(
        financial_service=FinancialAuthority(),
        financial_context=CTX,
        optimization_service=OptimizationAuthority(),
    )


def test_p5a_financial_total_grouping_zero_unknown_and_restart_fingerprint(service):
    total = service.enterprise_spend_summary(CTX)
    grouped = service.spend_by(CTX, "business_service")
    unsupported_dimension = service.spend_by(CTX, "owner")
    restarted = EnterpriseIntelligenceQueryService(
        financial_service=FinancialAuthority(), financial_context=CTX
    ).enterprise_spend_summary(CTX)

    assert total.value == grouped.value == Decimal("100")
    assert total.reconciliation is ReconciliationState.RECONCILED
    assert grouped.reconciliation is ReconciliationState.RECONCILED
    assert total.fingerprint == restarted.fingerprint
    assert unsupported_dimension.availability is AvailabilityState.UNKNOWN
    assert unsupported_dimension.value is None
    assert service.optimization_summary(CTX).metadata["stages"]["potential"] == (
        ("USD", Decimal("0")),
    )


def test_p5c_p5d_executive_and_ask_share_result_identity(service):
    snapshot = ExecutiveWorkspaceCompositionService.get_snapshot(
        "ceo", CTX, FinancialAuthority(), query_service=service, role="ceo"
    )
    ask = GovernedAskNexoraService(intelligence_service=service).ask(
        "What is our total technology spend?", scope=CTX
    )

    assert ask.state is AskState.SUPPORTED
    assert ask.canonical_result.fingerprint == snapshot.canonical_results[0].fingerprint
    assert snapshot.metrics[0].value == "$100"
    assert snapshot.metrics[0].availability == "AVAILABLE"


def test_p5e_safe_period_comparison_and_cross_tenant_isolation(service):
    comparison = service.period_comparison(
        CTX,
        "enterprise_spend_summary",
        current_period=(date(2026, 2, 1), date(2026, 2, 28)),
        comparison_period=(date(2026, 1, 1), date(2026, 1, 31)),
    )
    assert comparison.availability is AvailabilityState.AVAILABLE
    assert comparison.absolute_change == Decimal("10")
    assert comparison.percentage_change == Decimal("11.11111111111111111111111111")

    foreign = SimpleNamespace(organization_id="org-b", tenant_id="tenant-b", authorization_scope=())
    with pytest.raises(PermissionError):
        service.enterprise_spend_summary(foreign)


def test_p5_trust_falls_back_to_redacted_p1_lineage(service):
    result = service.query(CTX, "source_explanation")
    assert result.availability is AvailabilityState.AVAILABLE
    assert result.authority == "P1_LINEAGE"
    assert "credential_reference" not in result.value[0]


def test_persona_projection_changes_visibility_not_values(service):
    ceo = ExecutiveWorkspaceCompositionService.get_snapshot(
        "ceo", CTX, FinancialAuthority(), query_service=service, role="ceo"
    )
    finops = ExecutiveWorkspaceCompositionService.get_snapshot(
        "finops", CTX, FinancialAuthority(), query_service=service, role="finops"
    )
    ceo_total = next(metric for metric in ceo.metrics if metric.title == "Total Technology Spend")
    finops_total = next(
        metric for metric in finops.metrics if metric.title == "Total Technology Spend"
    )
    assert (ceo_total.value, ceo_total.fingerprint) == (
        finops_total.value,
        finops_total.fingerprint,
    )
