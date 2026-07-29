from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from models.contracts.enterprise_financial_posture import EnterpriseFinancialPosture
from services.executive_dashboard_certification_service import (
    ExecutiveDashboardCertificationService,
)
from tests.financial_data_fabric.test_pvt003c1_financial_data_fabric import (
    ORG_A,
    context,
    posture_row,
)

ROOT = Path(__file__).resolve().parents[2]
MIGRATION = ROOT / "supabase/migrations/202607290001_enterprise_financial_data_fabric.sql"


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
