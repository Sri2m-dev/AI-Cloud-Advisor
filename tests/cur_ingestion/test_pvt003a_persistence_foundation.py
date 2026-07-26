"""Static security and data-model checks for the PVT-003A migration."""

from pathlib import Path

MIGRATION = (
    Path(__file__).parents[2]
    / "supabase"
    / "migrations"
    / "202607260001_aws_cur_ingestion_foundation.sql"
)


def _sql() -> str:
    return MIGRATION.read_text(encoding="utf-8")


def test_pvt003a_creates_the_approved_additive_foundation_objects():
    sql = _sql()
    for table in (
        "cloud_cost_tenant_scope",
        "cloud_cost_import",
        "cloud_cost_import_part",
        "cloud_account_mapping",
        "cloud_cost_fact",
        "cloud_cost_reconciliation",
    ):
        assert f"create table if not exists public.{table}" in sql
        assert f"alter table public.{table} enable row level security" in sql


def test_pvt003a_preserves_tenant_ownership_and_deterministic_identities():
    sql = _sql()
    for required in (
        "organization_id uuid not null",
        "tenant_id uuid not null",
        "source_file_sha256",
        "source_row_key",
        "source_row_hash",
        "supersedes_import_id",
        "supersedes_fact_id",
        "checkpoint_row",
        "billing_period_start",
        "payer_account_id",
        "source_evidence jsonb",
        "cloud_cost_fact_source_unique",
        "cloud_cost_fact_scope_identity_unique",
        "references public.cloud_cost_tenant_scope (organization_id, tenant_id)",
        "references public.cloud_cost_import (organization_id, tenant_id, import_id)",
        "references public.cloud_cost_import_part (organization_id, tenant_id, import_part_id)",
        "references public.cloud_cost_fact (organization_id, tenant_id, cloud_cost_fact_id)",
    ):
        assert required in sql
    assert "tenant_id = organization_id" not in sql
    assert sql.count("nullif(auth.jwt() ->> 'tenant_id', '')::uuid") == 4


def test_pvt003a_denies_anon_and_authenticated_writes_by_default():
    sql = _sql()
    assert "revoke all on public.cloud_cost_import" in sql
    assert "from anon, authenticated" in sql
    assert "grant select on public.cloud_cost_import" in sql
    assert "to service_role" in sql
    assert "for insert to authenticated" not in sql
    assert "for update to authenticated" not in sql
    assert "for delete to authenticated" not in sql
    assert "cloud_cost_fact_select_own_org" not in sql


def test_pvt003a_authenticated_reads_bind_both_org_and_tenant_to_jwt_email_resolution():
    sql = _sql()
    assert sql.count("lower(u.email) = lower(auth.jwt() ->> 'email')") == 8
    for policy in (
        "cloud_cost_import_select_own_org",
        "cloud_cost_import_part_select_own_org",
        "cloud_account_mapping_select_own_org",
        "cloud_cost_reconciliation_select_own_org",
    ):
        assert f"create policy {policy}" in sql


def test_pvt003a_is_transactional_additive_and_fails_closed():
    sql = _sql()
    assert sql.lstrip().startswith("-- PVT-003A")
    assert "begin;" in sql
    assert sql.rstrip().endswith("commit;")
    assert "create table if not exists" in sql
    assert "create index if not exists" in sql
    assert "Unsafe CUR policy remains" in sql
