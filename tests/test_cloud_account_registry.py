from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from io import BytesIO
from types import SimpleNamespace

import pandas as pd
import pytest

import repositories.cloud_account_registry_repository as registry_repository_module
from auth.authenticated_tenant import AuthenticatedTenantContext
from components.navigation.sidebar import build_persona_navigation_items
from components.sidebar_navigation import PAGE_PATHS, ROLE_PAGES
from repositories.cloud_account_registry_repository import (
    CloudAccountRegistryRepository,
    LocalCloudAccountRegistryRepository,
)
from services.cloud_account_registry_composition import cloud_account_registry_repository
from services.cloud_account_registry_service import (
    CloudAccountRegistryService,
    RegistryValidationError,
)

ORG = "71cf875a-2103-47a0-8886-41a97c5750ec"


def context(role="finance"):
    return AuthenticatedTenantContext(
        ORG, "Default Org", "user-1", "user@example.com", role, frozenset(), ORG
    )


class Repo:
    def __init__(self):
        self.rows = []
        self.audit = []

    def list_accounts(self, _context):
        return list(self.rows)

    def create(self, _context, payload):
        row = {**payload, "id": str(len(self.rows) + 1)}
        self.rows.append(row)
        return row

    def update(self, _context, registry_id, payload):
        row = next(r for r in self.rows if r["id"] == registry_id)
        row.update(payload)
        return row

    def append_audit(self, _context, payload):
        self.audit.append(dict(payload))
        return payload

    def audit_history(self, _context, registry_id):
        return [r for r in self.audit if r["registry_id"] == registry_id]


class Discovery:
    def __init__(self, rows):
        self.rows = rows
        self.contexts = []

    def get_unknown_account_posture(self, ctx):
        self.contexts.append(ctx)
        return tuple(self.rows)

    def get_financial_posture(self, ctx):
        self.contexts.append(ctx)
        return SimpleNamespace(
            period_start=datetime(2026, 7, 1).date(),
            period_end=datetime(2026, 8, 1).date(),
            latest_import_id="import-1",
            currency="USD",
        )


def complete(account_id="123456789012"):
    return {
        "provider": "aws",
        "account_id": account_id,
        "account_name": "Production",
        "owner": "owner",
        "technical_owner": "tech",
        "finance_owner": "finance",
        "business_unit": "Platform",
        "department": "Engineering",
        "application": "Nexora",
        "business_service": "Cloud",
        "cost_center": "CC-1",
        "budget": 1000,
        "monthly_budget": 100,
        "tags_coverage": 100,
        "last_synchronization": datetime.now(timezone.utc).isoformat(),
        "status": "active",
    }


def test_governance_score_and_kpis_update_automatically():
    repo = Repo()
    service = CloudAccountRegistryService(repo)
    saved = service.save(context(), complete(), reason="onboard")
    assert saved["governance_score"] == 100
    assert service.governance_label(100) == "Excellent"
    assert service.dashboard(context())["aws"] == 1
    assert service.dashboard(context())["average_governance"] == 100


def test_duplicate_provider_identity_is_blocked_and_audited_changes_recorded():
    repo = Repo()
    service = CloudAccountRegistryService(repo)
    service.save(context(), complete(), reason="onboard")
    with pytest.raises(RegistryValidationError, match="duplicate aws"):
        service.save(context(), complete(), reason="duplicate")
    assert repo.audit[0]["actor_email"] == "user@example.com"
    assert repo.audit[0]["old_value"] == {}
    assert repo.audit[0]["reason"] == "onboard"


def test_rbac_read_edit_and_lifecycle_permissions():
    service = CloudAccountRegistryService(Repo())
    with pytest.raises(PermissionError):
        service.save(context("executive"), complete(), reason="no")
    saved = service.save(context(), complete(), reason="yes")
    with pytest.raises(PermissionError):
        service.transition(context(), saved["id"], "archived", "policy")
    archived = service.transition(context("super_admin"), saved["id"], "archived", "policy")
    assert archived["status"] == "archived"


def test_csv_preview_rejects_existing_and_file_duplicates():
    repo = Repo()
    service = CloudAccountRegistryService(repo)
    service.save(context(), complete(), reason="seed")
    frame = pd.DataFrame(
        [
            {
                "Provider": "aws",
                "Account ID": "123456789012",
                "Account Name": "Duplicate",
                "Owner": "o",
                "Business Unit": "b",
                "Department": "d",
                "Application": "a",
                "Environment": "prod",
                "Budget": "1",
            }
        ]
    )
    preview = service.preview_csv(context(), frame.to_csv(index=False).encode())
    assert preview["duplicates"] == [0]
    assert preview["can_commit"] is False


def test_valid_csv_preview_commits_only_after_explicit_call():
    repo = Repo()
    service = CloudAccountRegistryService(repo)
    frame = pd.DataFrame(
        [
            {
                "Provider": "gcp",
                "Account ID": "project-1",
                "Account Name": "Analytics",
                "Owner": "o",
                "Business Unit": "b",
                "Department": "d",
                "Application": "a",
                "Environment": "prod",
                "Budget": "10",
            }
        ]
    )
    preview = service.preview_csv(context(), frame.to_csv(index=False).encode())
    assert repo.rows == [] and preview["can_commit"]
    service.commit_preview(context(), preview, reason="approved import")
    assert repo.rows[0]["account_id"] == "project-1"


def test_csv_and_excel_exports_are_valid():
    rows = [complete()]
    service = CloudAccountRegistryService(Repo())
    assert b"account_id" in service.export_csv(rows)
    assert pd.read_excel(BytesIO(service.export_excel(rows))).iloc[0]["account_id"] == 123456789012


def test_migration_has_tenant_rls_unique_identity_and_no_delete_grant():
    sql = (
        open("supabase/migrations/202607310002_cloud_account_registry.sql", encoding="utf-8")
        .read()
        .lower()
    )
    assert "unique(organization_id,tenant_id,provider,account_id)" in sql
    assert "enable row level security" in sql
    assert "pvt003c1_can_read_organization" in sql
    assert "revoke delete" in sql
    assert "cloud_account_registry_audit" in sql


def test_active_navigation_registers_route_and_authorized_personas():
    assert PAGE_PATHS["Cloud Account Registry"] == "pages/cloud_account_registry.py"
    authorized = {role for role, pages in ROLE_PAGES.items() if "Cloud Account Registry" in pages}
    assert {"super_admin", "client_admin", "cio", "finance", "auditor"} <= authorized
    assert "executive" not in authorized
    for role in ("executive", "cio", "finance"):
        items = build_persona_navigation_items(role=role, page_paths=PAGE_PATHS)
        assert any(
            child["page"] == "pages/cloud_account_registry.py" for child in items[0]["children"]
        )
    assert "Cloud Account Registry" not in ROLE_PAGES.get("technical", [])
    assert "Cloud Account Registry" not in ROLE_PAGES.get("viewer", [])


def test_server_side_unauthorized_role_is_denied():
    assert CloudAccountRegistryService.permissions(context("client_admin"))["full"]
    with pytest.raises(PermissionError, match="read denied"):
        CloudAccountRegistryService(Repo()).list_accounts(context("viewer"))


def test_page_path_exists_and_has_no_hard_delete_action():
    from pathlib import Path

    path = Path(PAGE_PATHS["Cloud Account Registry"])
    assert path.exists()
    source = path.read_text(encoding="utf-8")
    assert "Deactivate" in source and "Archive" in source
    assert 'button("Delete' not in source


def discovered(account_id="123456789012", spend="10.50"):
    return {
        "payer_account_id": "payer-1",
        "account_id": account_id,
        "mapping_status": "unknown",
        "row_count": 2,
        "unblended_spend": spend,
        "blended_spend": spend,
        "first_usage_at": "2026-07-01T00:00:00Z",
        "last_usage_at": "2026-07-31T23:59:59Z",
        "currency": "USD",
    }


def test_discovered_accounts_are_projected_as_unapproved_pending_posture():
    source = Discovery([discovered()])
    service = CloudAccountRegistryService(Repo(), source)
    dashboard = service.dashboard(context())
    assert (
        dashboard["total"] == dashboard["aws"] == dashboard["unknown"] == dashboard["pending"] == 1
    )
    assert dashboard["active"] == 0 and dashboard["average_governance"] == "Not assessed"
    row = dashboard["accounts"][0]
    assert row["account_name"] == row["account_id"]
    assert row["record_origin"] == "financial_data_fabric_projection"
    assert row["discovery_status"] == "discovered"
    assert row["mapping_status"] == "unknown"
    assert row["ownership_status"] == "unassigned"
    assert row["lifecycle_status"] == "quarantined"
    assert row["source"] == "aws_cur" and row["source_import_id"] == "import-1"
    assert not row.get("owner") and not row.get("business_unit") and not row.get("application")


def test_discovered_union_is_deterministic_and_does_not_duplicate_governed_identity():
    repo = Repo()
    repo.rows.append({**complete(), "id": "registry-1", "status": "pending_mapping"})
    source = Discovery([discovered(), discovered()])
    service = CloudAccountRegistryService(repo, source)
    rows = service.list_accounts(context())
    assert len(rows) == 1 and rows[0]["id"] == "registry-1"
    assert rows[0]["mapping_status"] == "unknown"


def test_discovery_uses_exact_authenticated_tenant_context():
    source = Discovery([discovered()])
    service = CloudAccountRegistryService(Repo(), source)
    tenant = context()
    service.list_accounts(tenant)
    assert source.contexts == [tenant, tenant]
    foreign = AuthenticatedTenantContext(
        "972ee726-c5ab-427a-b77c-bd0e60bc322f",
        "Other",
        "user-2",
        "other@example.com",
        "finance",
        frozenset(),
        "972ee726-c5ab-427a-b77c-bd0e60bc322f",
    )
    service.list_accounts(foreign)
    assert source.contexts[-2:] == [foreign, foreign]


def test_new_manual_record_remains_pending_and_audited():
    repo = Repo()
    service = CloudAccountRegistryService(repo)
    saved = service.save(
        context(), {**complete(), "status": "active"}, reason="review discovered account"
    )
    assert saved["status"] == "pending_mapping"
    assert repo.audit[0]["action"] == "create"


def test_repository_selection_uses_supabase_when_configured():
    client = object()
    repository = cloud_account_registry_repository(
        supabase_url="https://project.supabase.co", client=client
    )
    assert isinstance(repository, CloudAccountRegistryRepository)
    assert repository.client is client


def test_repository_selection_uses_local_when_supabase_absent():
    assert isinstance(
        cloud_account_registry_repository(supabase_url=""),
        LocalCloudAccountRegistryRepository,
    )


def test_local_fallback_preserves_crud_audit_import_export_and_tenant_isolation(
    monkeypatch, tmp_path
):
    database_path = tmp_path / "registry.db"

    def get_test_db():
        conn = sqlite3.connect(database_path)
        conn.row_factory = sqlite3.Row
        return conn

    monkeypatch.setattr(registry_repository_module, "get_db", get_test_db)
    service = CloudAccountRegistryService(LocalCloudAccountRegistryRepository())
    tenant_a = context("super_admin")
    tenant_b = AuthenticatedTenantContext(
        "972ee726-c5ab-427a-b77c-bd0e60bc322f",
        "Other Org",
        "user-2",
        "other@example.com",
        "super_admin",
        frozenset(),
        "972ee726-c5ab-427a-b77c-bd0e60bc322f",
    )

    saved = service.save(tenant_a, complete(), reason="local create")
    assert len(service.list_accounts(tenant_a)) == 1
    assert service.list_accounts(tenant_b) == []
    updated = service.transition(tenant_a, saved["id"], "archived", "local archive")
    assert updated["status"] == "archived"
    history = service.repository.audit_history(tenant_a, saved["id"])
    assert [entry["action"] for entry in history] == ["update", "create"]
    assert service.repository.audit_history(tenant_b, saved["id"]) == []

    csv_content = (
        pd.DataFrame(
            [
                {
                    "Provider": "gcp",
                    "Account ID": "project-local",
                    "Account Name": "Local",
                    "Owner": "owner",
                    "Business Unit": "Platform",
                    "Department": "Engineering",
                    "Application": "Nexora",
                    "Environment": "dev",
                    "Budget": "10",
                }
            ]
        )
        .to_csv(index=False)
        .encode()
    )
    preview = service.preview_csv(tenant_a, csv_content)
    service.commit_preview(tenant_a, preview, reason="local import")
    rows = service.list_accounts(tenant_a)
    assert len(rows) == 2
    assert b"project-local" in service.export_csv(rows)
    assert pd.read_excel(BytesIO(service.export_excel(rows))).shape[0] == 2


def test_page_uses_automatic_composition_and_has_no_direct_supabase_repository():
    source = open("pages/cloud_account_registry.py", encoding="utf-8").read()
    assert "cloud_account_registry_service()" in source
    assert "CloudAccountRegistryRepository(supabase)" not in source
