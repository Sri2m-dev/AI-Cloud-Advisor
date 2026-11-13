"""Offline real route/auth code with synthetic configured API accounts and JWTs."""
import json
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.v1.approvals import router as approval_router
from auth.authenticated_tenant import AuthenticatedTenantContext, ProtectedWorkflowUnavailable
from auth.jwt_utils import create_jwt
from backend import security
from backend.middleware import tenant_isolation
from backend.routes import auth
from repositories.v1_approval_repository import V1ApprovalRepository
from scripts import provision_production_tenant as provisioning
from services.v1_approval_authority import SupabaseApprovalAuthority

ORG = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
OTHER = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"


@pytest.fixture
def application(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", "synthetic-m2c-offline-jwt-key-" + "x" * 32)
    store = {"operator": {"tenant_id": ORG, "role": "super_admin", "status": "active"}}
    monkeypatch.setattr(security, "_load_api_users", lambda: store)
    monkeypatch.setattr(security, "is_token_revoked", lambda jti: False)
    monkeypatch.setattr(tenant_isolation, "is_token_revoked", lambda jti: False)
    app = FastAPI()
    app.add_middleware(tenant_isolation.TenantIsolationMiddleware)
    app.include_router(approval_router, prefix="/api/v1")
    app.include_router(auth.router, prefix="/api/v1")
    headers = {"Authorization": "Bearer " + create_jwt("operator", "super_admin", ORG)}
    return TestClient(app), headers, store


@pytest.mark.parametrize("path", ["/approvals/list", "/approvals/a/history", "/approvals/a", "/approvals/dashboard/snapshot"])
def test_approval_routes_require_authentication(application, path):
    client, _, _ = application
    assert client.get("/api/v1" + path).status_code == 401


@pytest.mark.parametrize("path", ["/approvals/list", "/approvals/a/history", "/approvals/metrics/queue"])
def test_internal_admin_is_not_a_customer_workflow_role(application, path):
    client, headers, _ = application
    response = client.get("/api/v1" + path, headers=headers)
    assert response.status_code == 403


def test_account_tenant_cannot_be_overridden_by_approval_query(application):
    client, headers, _ = application
    for query in [f"org_id={OTHER}", "username=other", f"org_id={ORG}&org_id={OTHER}"]:
        assert client.get("/api/v1/approvals/list?" + query, headers=headers).status_code == 403


@pytest.mark.parametrize("action,field", [("approve", "approved_by"), ("reject", "rejected_by"), ("escalate", "escalated_by")])
def test_decision_actor_is_not_caller_authority(application, action, field):
    client, headers, _ = application
    uri = "/api/v1/approvals/a/" + action
    assert client.post(uri, json={field: "other"}, headers=headers).status_code == 403
    assert client.post(uri, json={field: "operator"}, headers=headers).status_code == 503


@pytest.mark.parametrize("action", ["admit", "revoke", "invalidate", "execute", "reconcile", "reconcile-status"])
def test_owner_lifecycle_is_authenticated_tenant_bound_and_closed(application, action):
    client, headers, _ = application
    uri = "/api/v1/auth/owner-operations/" + action
    payload = {"organization_id": ORG, "operation_id": "operation", "correlation_id": "correlation"}
    assert client.post(uri, json=payload).status_code == 401
    assert client.post(uri, json=payload, headers=headers).status_code == 503
    assert client.post(uri, json=payload | {"organization_id": OTHER}, headers=headers).status_code == 403
    assert client.post(uri, json=payload | {"verified": True}, headers=headers).status_code == 422


def test_existing_account_disable_and_tenant_change_take_effect(application):
    client, headers, store = application
    store["operator"]["status"] = "disabled"
    assert client.get("/api/v1/approvals/list", headers=headers).status_code == 401
    store["operator"]["status"] = "active"
    store["operator"]["tenant_id"] = OTHER
    assert client.get("/api/v1/approvals/list", headers=headers).status_code == 403


def test_invalid_signature_and_header_tenant_return_denial_not_middleware_crash(application):
    client, headers, _ = application
    assert client.get("/api/v1/approvals/list", headers={"Authorization": "Bearer invalid-signature"}).status_code == 401
    assert client.get("/api/v1/approvals/list", headers=headers | {"X-Tenant-Id": OTHER}).status_code == 403


def context():
    return AuthenticatedTenantContext(ORG, "Test", "uid", "user@example.invalid", "finance", frozenset(), ORG)


class Query:
    def __init__(self, rows):
        self.rows = rows
        self.filters = []
    def table(self, name): return self
    def select(self, value): return self
    def eq(self, key, value):
        self.filters.append((key, value))
        return self
    def order(self, *args, **kwargs): return self
    def limit(self, value): return self
    def execute(self): return SimpleNamespace(data=self.rows)


@pytest.mark.parametrize("method", ["get_request", "list_requests", "get_history"])
def test_approval_read_checks_response_tenancy_before_conversion(method):
    client = Query([{"organization_id": OTHER, "tenant_id": OTHER}])
    authority = SupabaseApprovalAuthority(client)
    with pytest.raises(PermissionError, match="crossed tenant"):
        getattr(authority, method)(context(), *([] if method == "list_requests" else ["a"]))
    assert ("organization_id", ORG) in client.filters and ("tenant_id", ORG) in client.filters


def test_empty_scoped_approval_read_is_valid_existing_read_contract():
    assert SupabaseApprovalAuthority(Query([])).list_requests(context()) == ()


def test_scoped_approval_read_rejects_wrong_request_within_tenant():
    authority = SupabaseApprovalAuthority(Query([{"organization_id": ORG, "tenant_id": ORG, "request_id": "other"}]))
    with pytest.raises(PermissionError, match="request boundary"):
        authority.get_request(context(), "expected")


def test_decision_denies_before_any_remote_read_or_update():
    class ForbiddenClient:
        def table(self, name): pytest.fail("no remote requests permitted")
    authority = SupabaseApprovalAuthority(ForbiddenClient())
    repository = V1ApprovalRepository(authority)
    with pytest.raises(ProtectedWorkflowUnavailable):
        repository.transition(context(), "1", target="APPROVED", actor="uid", reason="reason")
    with pytest.raises(PermissionError):
        authority.transition_request(context(), "a", to_state="APPROVED", actor="forged", reason="reason")
    with pytest.raises(ProtectedWorkflowUnavailable):
        authority.create_request(context(), subject_id="x", requested_action="grant", requesting_actor="uid", reason="reason")


def test_live_provisioning_stops_before_client_construction(monkeypatch, capsys):
    monkeypatch.setenv("SUPABASE_URL", "https://example.invalid")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "synthetic-not-output")
    code = provisioning.main(["--execute", "--approved-request", "--request-id", "r1",
                              "--organization-id", ORG, "--organization-name", "Test Organization",
                              "--admin-email", "admin@example.invalid"])
    text = capsys.readouterr().out
    assert code == 7 and "synthetic-not-output" not in text
    assert json.loads(text)["final_classification"] == "AUTHORITY_UNAVAILABLE"


def test_invalid_session_scope_never_becomes_owner_assurance():
    from auth.authenticated_tenant import require_protected_workflow
    with pytest.raises(PermissionError):
        require_protected_workflow("owner_execute", {"authenticated": True, "verified": True})
    with pytest.raises(ProtectedWorkflowUnavailable):
        require_protected_workflow("owner_execute", context())
