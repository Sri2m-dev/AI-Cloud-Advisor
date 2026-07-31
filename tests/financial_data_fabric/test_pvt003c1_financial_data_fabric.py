from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest

from auth.authenticated_tenant import (
    AuthenticatedTenantContext,
    AuthenticatedTenantError,
)
from models.contracts.enterprise_financial_posture import EnterpriseFinancialPosture
from repositories.enterprise_spend_repository import EnterpriseSpendRepository
from services.enterprise_spend_service import EnterpriseSpendService

ORG_A = str(uuid4())
ORG_B = str(uuid4())


def context(org: str = ORG_A, *, role: str = "cio") -> AuthenticatedTenantContext:
    return AuthenticatedTenantContext(
        organization_id=org,
        organization_name=f"Organization {org[-4:]}",
        user_id=f"user-{org[-4:]}",
        user_email=f"user-{org[-4:]}@example.test",
        role=role,
        authorization_claims=frozenset({"financial:read"}),
        tenant_id=org,
    )


def posture_row(org: str, spend: str = "100.1234567890", *, status: str = "quarantined"):
    resolved = spend if status == "active" else "0"
    quarantined = spend if status == "quarantined" else "0"
    return {
        "organization_id": org,
        "currency": "USD",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "import_count": 1,
        "latest_import_id": str(uuid4()),
        "latest_import_status": "quarantined",
        "source_rows": 2,
        "persisted_facts": 2,
        "total_ingested_spend": spend,
        "cloud_spend": spend,
        "resolved_spend": resolved,
        "quarantined_spend": quarantined,
        "allocated_spend": "0",
        "unallocated_resolved_spend": resolved,
        "reconciled_spend": spend,
        "unreconciled_spend": "0",
        "resolved_account_count": 0 if status == "quarantined" else 1,
        "unknown_account_count": 2 if status == "quarantined" else 0,
        "allocation_coverage_percentage": "0",
        "reconciliation_status": "quarantined" if status == "quarantined" else "reconciled",
        "reconciliation_variance": "0",
        "warnings": ["ownership unresolved"] if status == "quarantined" else [],
    }


class RpcCall:
    def __init__(self, client, name, params):
        self.client = client
        self.name = name
        self.params = params

    def execute(self):
        self.client.calls.append((self.name, self.params))
        org = self.params["requested_organization_id"]
        if org not in self.client.allowed:
            raise PermissionError("organization membership required")
        if self.name == "tenant_cloud_financial_posture":
            return SimpleNamespace(data=[self.client.postures[org]])
        return SimpleNamespace(data=self.client.rows.get((org, self.name), []))


class FakeClient:
    def __init__(self):
        self.allowed = {ORG_A, ORG_B}
        self.postures = {
            ORG_A: posture_row(ORG_A, "12.0000000001"),
            ORG_B: posture_row(ORG_B, "89.9999999999"),
        }
        self.rows = {}
        self.calls = []

    def rpc(self, name, params):
        return RpcCall(self, name, params)


def test_missing_organization_is_denied():
    with pytest.raises(AuthenticatedTenantError, match="organization_id"):
        AuthenticatedTenantContext.from_session(
            {"authenticated": True, "email": "a@example.test", "role": "cio"},
            organization_resolver=lambda _: "A",
        )


def test_invalid_organization_uuid_is_denied():
    with pytest.raises(AuthenticatedTenantError, match="valid UUID"):
        context("not-a-uuid")


def test_unauthenticated_session_is_denied_without_resolver_call():
    called = False

    def resolver(_):
        nonlocal called
        called = True
        return "A"

    with pytest.raises(AuthenticatedTenantError, match="authenticated"):
        AuthenticatedTenantContext.from_session({}, organization_resolver=resolver)
    assert called is False


def test_profile_membership_must_match_session_organization():
    with pytest.raises(AuthenticatedTenantError, match="profile"):
        AuthenticatedTenantContext.from_session(
            {
                "authenticated": True,
                "organization_id": ORG_A,
                "profile": {"org_id": ORG_B},
                "email": "a@example.test",
                "user_id": "user-a",
                "role": "cio",
            },
            organization_resolver=lambda _: "A",
        )


def test_organization_name_must_resolve_and_is_not_a_display_fallback():
    with pytest.raises(AuthenticatedTenantError, match="could not be resolved"):
        AuthenticatedTenantContext.from_session(
            {
                "authenticated": True,
                "organization_id": ORG_A,
                "email": "a@example.test",
                "user_id": "user-a",
                "role": "cto",
            },
            organization_resolver=lambda _: None,
        )


def test_authorized_session_normalizes_role_and_exposes_existing_fabric_context():
    result = AuthenticatedTenantContext.from_session(
        {
            "authenticated": True,
            "organization_id": ORG_A,
            "authorized_organization_ids": [ORG_A],
            "email": "A@Example.Test",
            "user_id": "user-a",
            "role": "cto",
            "permissions": ["financial:read"],
        },
        organization_resolver=lambda org: "Tenant A" if org == ORG_A else None,
    )
    assert result.organization_name == "Tenant A"
    assert result.user_email == "a@example.test"
    assert result.role == "cio"
    assert result.fabric_context.organization_id == ORG_A


def test_financial_contract_preserves_exact_decimal_and_invariants():
    result = EnterpriseFinancialPosture.from_mapping(posture_row(ORG_A, "127678.2170275708"))
    assert result.total_ingested_spend == Decimal("127678.2170275708")
    assert result.total_ingested_spend == result.resolved_spend + result.quarantined_spend
    assert result.resolved_spend == result.allocated_spend + result.unallocated_resolved_spend
    assert result.total_ingested_spend == result.reconciled_spend + result.unreconciled_spend


def test_invalid_financial_invariant_is_rejected():
    row = posture_row(ORG_A)
    row["quarantined_spend"] = "99"
    with pytest.raises(ValueError, match="total_ingested"):
        EnterpriseFinancialPosture.from_mapping(row)


def test_no_data_state_is_explicit():
    result = EnterpriseFinancialPosture.empty(ORG_A)
    assert result.has_data is False
    assert result.reconciliation_status == "no_data"
    assert result.total_ingested_spend == Decimal("0")


def test_repository_has_no_unfiltered_financial_api_and_always_sends_scope():
    client = FakeClient()
    repository = EnterpriseSpendRepository(client)
    assert not hasattr(repository, "get_all")
    assert not hasattr(repository, "list_all_costs")
    repository.get_posture(context())
    assert client.calls[0][1]["requested_organization_id"] == ORG_A


def test_foreign_organization_is_blocked_by_database_boundary():
    client = FakeClient()
    client.allowed.remove(ORG_B)
    repository = EnterpriseSpendRepository(client)
    with pytest.raises(PermissionError, match="membership"):
        repository.get_posture(context(ORG_B))


def test_tenant_cache_entries_never_cross():
    client = FakeClient()
    service = EnterpriseSpendService(EnterpriseSpendRepository(client), cache_ttl_seconds=60)
    a = service.get_financial_posture(context(ORG_A))
    b = service.get_financial_posture(context(ORG_B))
    assert a.organization_id == ORG_A
    assert b.organization_id == ORG_B
    assert a.total_ingested_spend != b.total_ingested_spend
    assert len(client.calls) == 2


def test_repeated_load_uses_tenant_safe_cache_and_invalidation_refreshes():
    client = FakeClient()
    service = EnterpriseSpendService(EnterpriseSpendRepository(client), cache_ttl_seconds=60)
    service.get_financial_posture(context())
    service.get_financial_posture(context())
    assert len(client.calls) == 1
    service.invalidate(ORG_A)
    service.get_financial_posture(context())
    assert len(client.calls) == 2


def test_role_scope_separates_cache_entries():
    client = FakeClient()
    service = EnterpriseSpendService(EnterpriseSpendRepository(client), cache_ttl_seconds=60)
    service.get_financial_posture(context(role="cio"))
    service.get_financial_posture(context(role="finance"))
    assert len(client.calls) == 2


def test_import_and_account_reads_are_tenant_scoped():
    client = FakeClient()
    client.rows[(ORG_A, "tenant_cloud_import_history")] = [{"import_id": "import-a"}]
    client.rows[(ORG_A, "tenant_cloud_account_posture")] = [
        {"account_id": "1", "payer_account_id": "p", "mapping_status": "unknown"},
        {"account_id": "2", "payer_account_id": "p", "mapping_status": "resolved"},
    ]
    service = EnterpriseSpendService(EnterpriseSpendRepository(client))
    assert service.get_import_history(context()) == ({"import_id": "import-a"},)
    assert service.get_unknown_account_posture(context()) == (
        {"account_id": "1", "payer_account_id": "p", "mapping_status": "unknown"},
    )
