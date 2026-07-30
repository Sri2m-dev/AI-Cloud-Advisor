from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest

from models.contracts.enterprise_financial_posture import EnterpriseFinancialPosture
from services.executive_dashboard_certification_service import (
    ExecutiveDashboardCertificationService,
)
from services.supabase_client import (
    TenantScopeRequiredError,
    _TenantGuardedQuery,
)
from tests.financial_data_fabric.test_pvt003c1_financial_data_fabric import (
    ORG_A,
    context,
    posture_row,
)

ROOT = Path(__file__).resolve().parents[2]
MIGRATION = ROOT / "supabase/migrations/202607290001_enterprise_financial_data_fabric.sql"
PERFORMANCE_MIGRATION = (
    ROOT / "supabase/migrations/202607290002_optimize_enterprise_financial_posture.sql"
)
PROJECTION_MIGRATION = (
    ROOT / "supabase/migrations/202607290003_materialize_cloud_financial_projections.sql"
)
FACT_COUNT_MIGRATION = ROOT / "supabase/migrations/202607290004_correct_persisted_fact_posture.sql"


class StubSpendService:
    def __init__(self, posture):
        self.posture = posture

    def get_financial_posture(self, tenant):
        assert tenant.organization_id == self.posture.organization_id
        return self.posture


def test_executive_dashboard_uses_canonical_quarantined_spend_not_legacy_zero():
    posture = EnterpriseFinancialPosture.from_mapping(posture_row(ORG_A, "127678.2170275708"))
    result = ExecutiveDashboardCertificationService.get_dashboard(
        context(),
        StubSpendService(posture),
    )
    assert result["legacy_metrics"]["cloud_cost"] == pytest.approx(127678.2170275708)
    assert result["financial_posture"].quarantined_spend == Decimal("127678.2170275708")
    assert result["financial_model"]["allocated_spend"] == Decimal("0")
    assert result["reconciliation"]["unknown_accounts"] == 2


def test_executive_narrative_is_plain_deterministic_and_posture_driven():
    posture = EnterpriseFinancialPosture.from_mapping(posture_row(ORG_A, "127678.2170275708"))
    result = ExecutiveDashboardCertificationService.get_dashboard(
        context(),
        StubSpendService(posture),
    )
    narrative = result["executive_summary"]
    assert narrative == (
        "Enterprise technology spend is 127,678.22 USD. The quarantined amount "
        "is 127,678.22 USD because ownership has not yet been approved for 2 "
        "AWS accounts. Financial reconciliation is complete with variance of "
        "0.00 USD, while allocation coverage remains 0.0%."
    )
    assert "$" not in narrative


def test_executive_reconciliation_governance_and_allocation_are_separate():
    posture = EnterpriseFinancialPosture.from_mapping(posture_row(ORG_A, "100"))
    result = ExecutiveDashboardCertificationService.get_dashboard(
        context(),
        StubSpendService(posture),
    )
    assert result["reconciliation"] == {
        "status": "reconciled",
        "allocation_coverage": Decimal("0"),
        "unallocated_spend": Decimal("0"),
        "variance": Decimal("0"),
        "unknown_accounts": 2,
        "source_rows": 2,
        "persisted_facts": 2,
    }
    assert result["governance"]["status"] == "quarantined"
    assert result["governance"]["unknown_accounts"] == 2
    assert result["allocation"]["coverage"] == Decimal("0")
    assert result["allocation"]["allocated_spend"] == Decimal("0")


def test_executive_page_contains_required_primary_kpis_in_order():
    source = (ROOT / "pages/executive_dashboard.py").read_text(encoding="utf-8")
    labels = [
        "Total Enterprise Spend",
        "Cloud Spend",
        "Quarantined Spend",
        "Allocation Coverage",
        "Reconciliation Variance",
        "Unknown Cloud Accounts",
    ]
    positions = [source.index(f'"{label}"') for label in labels]
    assert positions == sorted(positions)
    assert '"Unallocated Spend"' not in source
    assert "Unallocated resolved spend:" in source


class FakeQuery:
    def __init__(self):
        self.executed = False

    def select(self, *_args, **_kwargs):
        return self

    def insert(self, *_args, **_kwargs):
        return self

    def eq(self, *_args, **_kwargs):
        return self

    def execute(self):
        self.executed = True
        return SimpleNamespace(data=[{"value": 1}])


def test_unscoped_legacy_financial_read_is_safely_disabled():
    target = FakeQuery()
    response = (
        _TenantGuardedQuery(
            target,
            table_name="unified_cloud_costs",
        )
        .select("*")
        .execute()
    )
    assert response.data == []
    assert target.executed is False


def test_scoped_legacy_compatibility_read_continues_to_rls():
    target = FakeQuery()
    response = (
        _TenantGuardedQuery(target, table_name="mart_enterprise_spend_v2")
        .select("*")
        .eq("organization_id", ORG_A)
        .execute()
    )
    assert response.data == [{"value": 1}]
    assert target.executed is True


def test_unscoped_legacy_financial_write_is_rejected():
    target = FakeQuery()
    with pytest.raises(TenantScopeRequiredError, match="tenant scope"):
        _TenantGuardedQuery(
            target,
            table_name="unified_cloud_costs",
        ).insert({"cost": 1}).execute()


def test_canonical_migration_is_guarded_and_never_grants_anonymous_execution():
    sql = MIGRATION.read_text(encoding="utf-8").lower()
    assert "security definer" in sql
    assert "set search_path = pg_catalog, public" in sql
    assert "pvt003c1_can_read_organization(requested_organization_id)" in sql
    assert "revoke all on function public.tenant_cloud_financial_posture" in sql
    assert "from public, anon" in sql
    assert "grant execute on function public.tenant_cloud_financial_posture" in sql
    assert "to authenticated, service_role" in sql


def test_canonical_aggregations_are_database_side_and_do_not_return_raw_evidence():
    sql = MIGRATION.read_text(encoding="utf-8").lower()
    assert "sum(unblended_cost)" in sql
    assert "count(*)" in sql
    posture_signature = sql.split(
        "create or replace function public.tenant_cloud_financial_posture", 1
    )[1].split("language plpgsql", 1)[0]
    assert "raw_fields" not in posture_signature
    assert "source_evidence" not in posture_signature


def test_posture_uses_certified_rollups_instead_of_fact_level_spend_sum():
    sql = PERFORMANCE_MIGRATION.read_text(encoding="utf-8").lower()
    posture = sql.split("create or replace function public.tenant_cloud_financial_posture", 1)[1]
    assert "coalesce(r.normalized_cost_total" in posture
    assert "sum(certified_total)" in posture
    assert "sum(f.unblended_cost)" not in posture
    assert "cloud_cost_fact_tenant_account_idx" in sql


def test_fact_rollups_are_private_bounded_and_explicitly_invalidated():
    sql = PROJECTION_MIGRATION.read_text(encoding="utf-8").lower()
    assert "tenant_cloud_import_fact_rollup" in sql
    assert "tenant_cloud_account_fact_rollup" in sql
    assert "tenant_cloud_service_fact_rollup" in sql
    assert "refresh_tenant_cloud_financial_projections" in sql
    assert "service role required" in sql
    assert "from public, anon, authenticated" in sql
    assert "cloud_cost_fact f" in sql
    assert "raw_fields" not in sql
    assert "source_evidence" not in sql


def test_persisted_fact_posture_counts_quarantined_materialized_facts():
    sql = FACT_COUNT_MIGRATION.read_text(encoding="utf-8").lower()
    assert "tenant_cloud_import_fact_rollup" in sql
    assert "sum(fr.persisted_facts)" in sql
    assert "accepted_row_count" not in sql
    assert "tenant_cloud_financial_posture_v1" in sql


def test_migrated_financial_services_contain_no_unfiltered_select():
    paths = (
        ROOT / "repositories/enterprise_spend_repository.py",
        ROOT / "services/enterprise_spend_service.py",
        ROOT / "services/enterprise_spend_composition.py",
    )
    source = "\n".join(path.read_text(encoding="utf-8") for path in paths)
    assert '.select("*").execute()' not in source
    assert "get_all(" not in source
    assert "list_all_costs(" not in source
