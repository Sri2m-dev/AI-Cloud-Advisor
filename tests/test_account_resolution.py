from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from auth.authenticated_tenant import AuthenticatedTenantContext
from services.cloud_account_registry_service import (
    CloudAccountRegistryService,
    RegistryValidationError,
)

ORG = "71cf875a-2103-47a0-8886-41a97c5750ec"
OTHER_ORG = "972ee726-c5ab-427a-b77c-bd0e60bc322f"


def context(role="super_admin", organization_id=ORG):
    return AuthenticatedTenantContext(
        organization_id,
        "Default Org",
        "user-1",
        "user@example.com",
        role,
        frozenset(),
        organization_id,
    )


def discovered(account_id="123456789012"):
    return {
        "provider": "aws",
        "payer_account_id": "payer-1",
        "account_id": account_id,
        "mapping_status": "unknown",
        "source_import_id": "import-1",
        "first_seen_at": "2026-07-01T00:00:00Z",
        "last_seen_at": "2026-07-31T00:00:00Z",
        "billing_period": "2026-07-01 / 2026-08-01",
        "quarantined_spend": "123.4567890123",
        "currency": "USD",
    }


def complete(status="APPROVED"):
    return {
        "account_name": "Production",
        "owner": "owner",
        "business_unit": "Platform",
        "cost_center": "CC-1",
        "environment": "prod",
        "resolution_status": status,
        "effective_date": "2026-08-01",
    }


class Repo:
    def __init__(self):
        self.calls = []

    def list_accounts(self, _context):
        return []

    def resolve_account(self, ctx, source, mapping, **options):
        self.calls.append((ctx, source, mapping, options))
        spend = Decimal(source["quarantined_spend"])
        ready = CloudAccountRegistryService.allocation_ready(mapping)
        return {
            "allocation_ready": ready,
            "version": 1,
            "financial_before": {
                "total_ingested_spend": "127678.2170275708",
                "quarantined_spend": "127678.2170275708",
                "resolved_spend": "0",
                "reconciliation_variance": "0",
                "persisted_facts": 786745,
            },
            "financial_after": {
                "total_ingested_spend": "127678.2170275708",
                "quarantined_spend": str(Decimal("127678.2170275708") - spend)
                if ready
                else "127678.2170275708",
                "resolved_spend": str(spend) if ready else "0",
                "reconciliation_variance": "0",
                "persisted_facts": 786745,
            },
        }

    def bulk_resolve(self, ctx, accounts, mapping, **options):
        self.calls.append((ctx, list(accounts), mapping, options))
        return {"count": len(accounts)}


def service(repo=None):
    return CloudAccountRegistryService(repo or Repo())


def test_complete_approved_mapping_is_allocation_ready():
    assert service().allocation_ready(complete())


def test_incomplete_mapping_remains_quarantined():
    repo = Repo()
    result = service(repo).resolve_discovered(
        context(),
        discovered(),
        {"owner": "owner", "resolution_status": "APPROVED"},
        reason="review",
        confirmed=True,
    )
    assert result["allocation_ready"] is False
    assert (
        result["financial_after"]["quarantined_spend"]
        == result["financial_before"]["quarantined_spend"]
    )


def test_single_resolution_exact_financial_delta_and_invariants():
    result = service().resolve_discovered(
        context(),
        discovered(),
        complete(),
        reason="approved mapping",
        confirmed=True,
    )
    before, after = result["financial_before"], result["financial_after"]
    delta = Decimal("123.4567890123")
    assert Decimal(before["quarantined_spend"]) - Decimal(after["quarantined_spend"]) == delta
    assert Decimal(after["resolved_spend"]) - Decimal(before["resolved_spend"]) == delta
    assert before["total_ingested_spend"] == after["total_ingested_spend"]
    assert before["persisted_facts"] == after["persisted_facts"] == 786745
    assert Decimal(after["reconciliation_variance"]) == 0


@pytest.mark.parametrize("role", ["executive", "cio", "auditor", "technical", "viewer"])
def test_unauthorized_roles_cannot_resolve(role):
    with pytest.raises(PermissionError, match="resolution denied"):
        service().resolve_discovered(
            context(role), discovered(), complete(), reason="x", confirmed=True
        )


def test_finance_can_map_but_cannot_approve():
    with pytest.raises(PermissionError, match="approval denied"):
        service().resolve_discovered(
            context("finance"), discovered(), complete(), reason="x", confirmed=True
        )


def test_reason_confirmation_and_identity_are_required():
    with pytest.raises(RegistryValidationError, match="confirmation"):
        service().resolve_discovered(
            context(), discovered(), complete(), reason="x", confirmed=False
        )
    with pytest.raises(RegistryValidationError, match="reason"):
        service().resolve_discovered(context(), discovered(), complete(), reason="", confirmed=True)
    with pytest.raises(RegistryValidationError, match="identity"):
        service().resolve_discovered(
            context(), {"provider": "aws"}, complete(), reason="x", confirmed=True
        )


def test_exact_tenant_context_is_forwarded_to_atomic_repository():
    repo = Repo()
    tenant = context(organization_id=OTHER_ORG)
    service(repo).resolve_discovered(tenant, discovered(), complete(), reason="x", confirmed=True)
    assert repo.calls[0][0] is tenant


def test_bulk_preview_requires_explicit_commit_confirmation():
    svc = service()
    preview = svc.preview_bulk_resolution(
        context(), [discovered("1"), discovered("2")], {"business_unit": "Platform"}
    )
    assert preview["count"] == 2 and preview["quarantined_spend"] == pytest.approx(246.9135780246)
    with pytest.raises(RegistryValidationError, match="confirmation"):
        svc.commit_bulk_resolution(context(), preview, reason="bulk", confirmed=False)


def test_bulk_commit_is_one_repository_transaction():
    repo = Repo()
    svc = service(repo)
    preview = svc.preview_bulk_resolution(
        context(), [discovered("1"), discovered("2")], {"business_unit": "Platform"}
    )
    assert (
        svc.commit_bulk_resolution(context(), preview, reason="bulk review", confirmed=True)[
            "count"
        ]
        == 2
    )
    assert len(repo.calls) == 1


def test_migration_atomicity_versioning_replay_and_raw_fact_safety():
    sql = (
        Path("supabase/migrations/202608080001_fg002_account_resolution.sql")
        .read_text(encoding="utf-8")
        .lower()
    )
    assert "pg_advisory_xact_lock" in sql
    assert "stale account resolution state" in sql
    assert "account is already resolved" in sql
    assert "cloud_account_registry_version" in sql
    assert "financial_before" in sql and "financial_after" in sql
    assert "reconciliation invariant failed" in sql
    assert "update public.cloud_cost_fact" not in sql
    assert "delete from public.cloud_cost_fact" not in sql
    assert "fg002_bulk_resolve_cloud_accounts" in sql


def test_mapping_payload_preserves_immutable_discovery_evidence():
    repo = Repo()
    source = discovered()
    service(repo).resolve_discovered(context(), source, complete(), reason="x", confirmed=True)
    mapping = repo.calls[0][2]
    for key in (
        "source_import_id",
        "first_seen_at",
        "last_seen_at",
        "billing_period",
        "quarantined_spend",
        "currency",
    ):
        assert mapping[key] == source[key]
