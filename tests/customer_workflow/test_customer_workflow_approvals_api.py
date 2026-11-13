from uuid import uuid4

import pytest
from cryptography.fernet import Fernet
from fastapi import FastAPI
from fastapi.testclient import TestClient

import api.v1.approvals as approval_api
from auth.authenticated_tenant import AuthenticatedTenantContext
from auth.jwt_utils import create_jwt
from backend import security
from backend.middleware import tenant_isolation
from services.customer_workflow_service import (
    CustomerWorkflowService,
    SQLiteCustomerWorkflowRepository,
)

ORG_A = "11111111-1111-4111-8111-111111111111"
ORG_B = "22222222-2222-4222-8222-222222222222"
CSV = b"Provider,Service,Cost,Currency\nAWS,EC2,12.50,USD\nAzure,Storage,7.50,USD\n"


def _context(organization_id, user_id, role):
    return AuthenticatedTenantContext(
        organization_id=organization_id,
        organization_name="Synthetic Customer",
        user_id=user_id,
        user_email=f"{user_id}@example.test",
        role=role,
        authorization_claims=frozenset(),
        tenant_id=organization_id,
    )


@pytest.fixture
def api_workflow(tmp_path, monkeypatch):
    key = Fernet.generate_key()
    workflow = CustomerWorkflowService(
        SQLiteCustomerWorkflowRepository(tmp_path / "workflow.db", key=key),
        evidence_root=tmp_path / "encrypted-evidence",
        evidence_key=key,
    )
    users = {}
    monkeypatch.setenv("JWT_SECRET", "synthetic-approval-api-jwt-key-" + "x" * 32)
    monkeypatch.setattr(security, "_load_api_users", lambda: users)
    monkeypatch.setattr(security, "is_token_revoked", lambda _: False)
    monkeypatch.setattr(tenant_isolation, "is_token_revoked", lambda _: False)
    app = FastAPI()
    app.add_middleware(tenant_isolation.TenantIsolationMiddleware)
    app.include_router(approval_api.router, prefix="/api/v1")
    monkeypatch.setattr(approval_api, "_workflow_service", lambda: workflow)
    return TestClient(app), workflow, users


def _authorize(users, *, organization_id=ORG_A, user_id, role):
    users[user_id] = {
        "tenant_id": organization_id,
        "role": role,
        "status": "active",
    }
    return {
        "Authorization": "Bearer "
        + create_jwt(user_id, role, organization_id)
    }


def _seed_decision(workflow):
    requester = _context(ORG_A, "requester", "finance")
    workspace = workflow.create_workspace(
        requester,
        name="Synthetic customer workspace",
        operation_id=str(uuid4()),
    )
    evidence = workflow.upload_evidence(
        requester,
        workspace.workspace_id,
        filename="customer-costs.csv",
        content=CSV,
        input_profile="Generic technology-cost Excel/CSV",
    )
    ask = workflow.ask(
        requester,
        workspace.workspace_id,
        evidence_id=evidence.event_id,
        question="How many evidence records are present?",
    )
    decision = workflow.create_decision(
        requester,
        workspace.workspace_id,
        ask_id=ask.event_id,
        decision="Review the observed cloud costs",
        rationale="The uploaded records contain two cost observations.",
    )
    return workspace, decision


def test_api_uses_canonical_append_only_approval_and_export_workflow(api_workflow):
    client, workflow, users = api_workflow
    workspace, decision = _seed_decision(workflow)

    assert client.get("/api/v1/approvals/list").status_code == 401
    requester_headers = _authorize(users, user_id="requester", role="finance")
    response = client.post(
        "/api/v1/approvals/create",
        json={
            "workspace_id": workspace.workspace_id,
            "decision_id": decision.payload["decision_id"],
            "reason": "Request the staged customer decision.",
        },
        headers=requester_headers,
    )
    assert response.status_code == 200
    approval_id = response.json()["payload"]["approval_id"]

    assert client.post(
        f"/api/v1/approvals/{approval_id}/approve",
        json={"reason": "Requester must not self-approve."},
        headers=requester_headers,
    ).status_code == 403
    assert client.post(
        f"/api/v1/approvals/{approval_id}/export",
        headers=requester_headers,
    ).status_code == 409

    cio_headers = _authorize(users, user_id="cio-approver", role="cio")
    assert client.post(
        f"/api/v1/approvals/{approval_id}/approve",
        json={"reason": "CIO cannot approve before Finance."},
        headers=cio_headers,
    ).status_code == 403

    finance_headers = _authorize(users, user_id="finance-approver", role="finance")
    assert client.post(
        f"/api/v1/approvals/{approval_id}/approve",
        json={"approved_by": "requester", "reason": "Spoofed actor."},
        headers=finance_headers,
    ).status_code == 403
    finance = client.post(
        f"/api/v1/approvals/{approval_id}/approve",
        json={"reason": "Finance approved the decision."},
        headers=finance_headers,
    )
    assert finance.status_code == 200

    cio = client.post(
        f"/api/v1/approvals/{approval_id}/approve",
        json={"reason": "CIO approved the decision."},
        headers=cio_headers,
    )
    assert cio.status_code == 200

    ceo_headers = _authorize(users, user_id="ceo-approver", role="executive")
    ceo = client.post(
        f"/api/v1/approvals/{approval_id}/approve",
        json={"reason": "CEO approved the decision."},
        headers=ceo_headers,
    )
    assert ceo.status_code == 200

    history = client.get(
        f"/api/v1/approvals/{approval_id}/history",
        headers=ceo_headers,
    )
    assert history.status_code == 200
    assert [row["actor_role"] for row in history.json()["history"]] == [
        "finance",
        "cio",
        "executive",
    ]

    exported = client.post(
        f"/api/v1/approvals/{approval_id}/export",
        headers=ceo_headers,
    )
    assert exported.status_code == 200
    package = exported.json()["payload"]["package"]
    assert package["approval"]["state"] == "APPROVED"
    assert len(package["approval"]["history"]) == 3
    assert package["evidence"]["sha256"]
    listing = client.get("/api/v1/approvals/list", headers=ceo_headers)
    assert listing.status_code == 200
    assert listing.json()["approvals"][0]["approval_id"] == approval_id


def test_api_restricts_tenant_selectors_and_hides_other_tenant_approvals(api_workflow):
    client, workflow, users = api_workflow
    workspace, decision = _seed_decision(workflow)
    headers = _authorize(users, user_id="requester", role="finance")
    created = client.post(
        "/api/v1/approvals/create",
        json={
            "workspace_id": workspace.workspace_id,
            "decision_id": decision.payload["decision_id"],
            "reason": "Request a tenant-scoped approval.",
        },
        headers=headers,
    )
    assert created.status_code == 200
    approval_id = created.json()["payload"]["approval_id"]

    assert client.get(
        f"/api/v1/approvals/{approval_id}?org_id={ORG_B}",
        headers=headers,
    ).status_code == 403
    assert client.post(
        "/api/v1/approvals/create",
        json={
            "workspace_id": workspace.workspace_id,
            "decision_id": decision.payload["decision_id"],
            "reason": "Attempt to override identity.",
            "org_id": ORG_B,
        },
        headers=headers,
    ).status_code == 422

    customer_b_headers = _authorize(
        users,
        organization_id=ORG_B,
        user_id="customer-b",
        role="finance",
    )
    assert client.get(
        f"/api/v1/approvals/{approval_id}",
        headers=customer_b_headers,
    ).status_code == 404
    assert client.post(
        f"/api/v1/approvals/{approval_id}/approve",
        json={"reason": "Cross-tenant attempt."},
        headers=customer_b_headers,
    ).status_code == 404
