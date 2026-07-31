from __future__ import annotations

from datetime import datetime, timezone
from io import BytesIO

import pandas as pd
import pytest

from auth.authenticated_tenant import AuthenticatedTenantContext
from services.cloud_account_registry_service import (
    CloudAccountRegistryService,
    RegistryValidationError,
)

ORG = "71cf875a-2103-47a0-8886-41a97c5750ec"

def context(role="finance"):
    return AuthenticatedTenantContext(ORG,"Default Org","user-1","user@example.com",role,frozenset(),ORG)

class Repo:
    def __init__(self): self.rows=[]; self.audit=[]
    def list_accounts(self, _context): return list(self.rows)
    def create(self, _context, payload):
        row={**payload,"id":str(len(self.rows)+1)}; self.rows.append(row); return row
    def update(self, _context, registry_id, payload):
        row=next(r for r in self.rows if r["id"]==registry_id); row.update(payload); return row
    def append_audit(self, _context, payload): self.audit.append(dict(payload)); return payload
    def audit_history(self, _context, registry_id): return [r for r in self.audit if r["registry_id"]==registry_id]

def complete(account_id="123456789012"):
    return {"provider":"aws","account_id":account_id,"account_name":"Production","owner":"owner","technical_owner":"tech","finance_owner":"finance","business_unit":"Platform","department":"Engineering","application":"Nexora","business_service":"Cloud","cost_center":"CC-1","budget":1000,"monthly_budget":100,"tags_coverage":100,"last_synchronization":datetime.now(timezone.utc).isoformat(),"status":"active"}

def test_governance_score_and_kpis_update_automatically():
    repo=Repo(); service=CloudAccountRegistryService(repo)
    saved=service.save(context(),complete(),reason="onboard")
    assert saved["governance_score"]==100
    assert service.governance_label(100)=="Excellent"
    assert service.dashboard(context())["aws"]==1
    assert service.dashboard(context())["average_governance"]==100

def test_duplicate_provider_identity_is_blocked_and_audited_changes_recorded():
    repo=Repo(); service=CloudAccountRegistryService(repo)
    service.save(context(),complete(),reason="onboard")
    with pytest.raises(RegistryValidationError,match="duplicate aws"):
        service.save(context(),complete(),reason="duplicate")
    assert repo.audit[0]["actor_email"]=="user@example.com"
    assert repo.audit[0]["old_value"]=={}
    assert repo.audit[0]["reason"]=="onboard"

def test_rbac_read_edit_and_lifecycle_permissions():
    service=CloudAccountRegistryService(Repo())
    with pytest.raises(PermissionError): service.save(context("executive"),complete(),reason="no")
    saved=service.save(context(),complete(),reason="yes")
    with pytest.raises(PermissionError): service.transition(context(),saved["id"],"archived","policy")
    archived=service.transition(context("super_admin"),saved["id"],"archived","policy")
    assert archived["status"]=="archived"

def test_csv_preview_rejects_existing_and_file_duplicates():
    repo=Repo(); service=CloudAccountRegistryService(repo); service.save(context(),complete(),reason="seed")
    frame=pd.DataFrame([{"Provider":"aws","Account ID":"123456789012","Account Name":"Duplicate","Owner":"o","Business Unit":"b","Department":"d","Application":"a","Environment":"prod","Budget":"1"}])
    preview=service.preview_csv(context(),frame.to_csv(index=False).encode())
    assert preview["duplicates"]==[0]
    assert preview["can_commit"] is False

def test_valid_csv_preview_commits_only_after_explicit_call():
    repo=Repo(); service=CloudAccountRegistryService(repo)
    frame=pd.DataFrame([{"Provider":"gcp","Account ID":"project-1","Account Name":"Analytics","Owner":"o","Business Unit":"b","Department":"d","Application":"a","Environment":"prod","Budget":"10"}])
    preview=service.preview_csv(context(),frame.to_csv(index=False).encode())
    assert repo.rows == [] and preview["can_commit"]
    service.commit_preview(context(),preview,reason="approved import")
    assert repo.rows[0]["account_id"]=="project-1"

def test_csv_and_excel_exports_are_valid():
    rows=[complete()]; service=CloudAccountRegistryService(Repo())
    assert b"account_id" in service.export_csv(rows)
    assert pd.read_excel(BytesIO(service.export_excel(rows))).iloc[0]["account_id"]==123456789012

def test_migration_has_tenant_rls_unique_identity_and_no_delete_grant():
    sql=open("supabase/migrations/202607310002_cloud_account_registry.sql",encoding="utf-8").read().lower()
    assert "unique(organization_id,tenant_id,provider,account_id)" in sql
    assert "enable row level security" in sql
    assert "pvt003c1_can_read_organization" in sql
    assert "revoke delete" in sql
    assert "cloud_account_registry_audit" in sql
