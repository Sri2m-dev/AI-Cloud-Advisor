from __future__ import annotations

import sqlite3
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pytest
from cryptography.fernet import Fernet

from auth.authenticated_tenant import AuthenticatedTenantContext
from services.customer_workflow_service import (
    CustomerWorkflowError,
    CustomerWorkflowService,
    SQLiteCustomerWorkflowRepository,
)

ORG_A = "11111111-1111-4111-8111-111111111111"
ORG_B = "22222222-2222-4222-8222-222222222222"
CSV = b"Provider,Service,Cost,Currency\nAWS,EC2,12.50,USD\nAzure,Storage,7.50,USD\n"


def _context(organization_id, *, user_id=None, role="executive"):
    return AuthenticatedTenantContext(
        organization_id=organization_id,
        organization_name="Synthetic Customer",
        user_id=user_id or str(uuid4()),
        user_email=f"{user_id or 'member'}@example.test",
        role=role,
        authorization_claims=frozenset(),
        tenant_id=organization_id,
    )


@pytest.fixture
def workflow_key():
    return Fernet.generate_key()


@pytest.fixture
def workflow(tmp_path, workflow_key):
    repository = SQLiteCustomerWorkflowRepository(
        tmp_path / "customer.db",
        key=workflow_key,
    )
    return CustomerWorkflowService(
        repository,
        evidence_root=tmp_path / "encrypted-evidence",
        evidence_key=workflow_key,
    )


def _create_evidence_and_ask(workflow, context, *, operation_id="workspace-1"):
    workspace = workflow.create_workspace(
        context,
        name="Synthetic customer workspace",
        operation_id=operation_id,
    )
    evidence = workflow.upload_evidence(
        context,
        workspace.workspace_id,
        filename="customer-costs.csv",
        content=CSV,
        input_profile="Generic technology-cost Excel/CSV",
    )
    ask = workflow.ask(
        context,
        workspace.workspace_id,
        evidence_id=evidence.event_id,
        question="How many evidence records are present?",
    )
    return workspace, evidence, ask


def test_authenticated_customer_completes_and_resumes_workflow(workflow, workflow_key):
    requester = _context(ORG_A, user_id="requester", role="finance")
    workspace, evidence, ask = _create_evidence_and_ask(workflow, requester)
    assert evidence.payload["validation_status"] == "PASS"
    assert evidence.payload["source_sha256"]
    assert ask.payload["state"] == "GROUNDED"
    assert "2 evidence rows" in ask.payload["answer"]
    assert ask.payload["evidence_references"][0]["record_id"] == evidence.event_id

    decision = workflow.create_decision(
        requester,
        workspace.workspace_id,
        ask_id=ask.event_id,
        decision="Review the observed cloud costs",
        rationale="The uploaded records contain two cost observations.",
    )
    request = workflow.request_approval(
        requester,
        workspace.workspace_id,
        decision_id=decision.payload["decision_id"],
        reason="Request customer governance approval for this review.",
    )
    with pytest.raises(PermissionError, match="cannot approve their own"):
        workflow.transition_approval(
            requester,
            workspace.workspace_id,
            approval_id=request.payload["approval_id"],
            target="APPROVED",
            reason="Requester cannot self-approve.",
        )

    approvals = (
        _context(ORG_A, user_id="finance-approver", role="finance"),
        _context(ORG_A, user_id="cio-approver", role="cio"),
        _context(ORG_A, user_id="executive-approver", role="executive"),
    )
    latest = None
    for actor in approvals:
        latest = workflow.transition_approval(
            actor,
            workspace.workspace_id,
            approval_id=request.payload["approval_id"],
            target="APPROVED",
            reason=f"{actor.role} approved the customer decision.",
        )
    assert latest is not None
    assert latest.payload["approval"]["state"] == "APPROVED"

    exported = workflow.export_evidence(
        approvals[-1],
        workspace.workspace_id,
        approval_id=request.payload["approval_id"],
    )
    assert workflow.export_evidence(
        approvals[-1],
        workspace.workspace_id,
        approval_id=request.payload["approval_id"],
    ).event_id == exported.event_id
    package = exported.payload["package"]
    assert package["evidence"]["record_id"] == evidence.event_id
    assert package["ask"]["record_id"] == ask.event_id
    assert package["decision"]["record_id"] == decision.event_id
    assert package["approval"]["state"] == "APPROVED"
    assert len(package["approval"]["history"]) == 3

    resumed_service = CustomerWorkflowService(
        SQLiteCustomerWorkflowRepository(
            workflow.repository.database,
            key=workflow_key,
        ),
        evidence_root=workflow.evidence_root,
        evidence_key=workflow_key,
    )
    resumed = resumed_service.resume_workspace(requester, workspace.workspace_id)
    assert [row["event_id"] for row in resumed["evidence"]] == [evidence.event_id]
    assert [row["event_id"] for row in resumed["asks"]] == [ask.event_id]
    assert [row["event_id"] for row in resumed["decisions"]] == [decision.event_id]
    assert len(resumed["approvals"]) == 4
    assert [row["event_id"] for row in resumed["exports"]] == [exported.event_id]
    assert resumed_service.load_evidence(
        requester, workspace.workspace_id, evidence.event_id
    ) == CSV


def test_tenant_scope_is_enforced_at_each_customer_boundary(workflow):
    customer_a = _context(ORG_A, user_id="customer-a")
    customer_b = _context(ORG_B, user_id="customer-b")
    workspace, evidence, ask = _create_evidence_and_ask(workflow, customer_a)
    decision = workflow.create_decision(
        customer_a,
        workspace.workspace_id,
        ask_id=ask.event_id,
        decision="Keep the evidence for review",
        rationale="The decision is explicitly based on the grounded answer.",
    )
    request = workflow.request_approval(
        customer_a,
        workspace.workspace_id,
        decision_id=decision.payload["decision_id"],
        reason="Review the customer decision.",
    )

    assert workflow.list_workspaces(customer_b) == ()
    for operation in (
        lambda: workflow.resume_workspace(customer_b, workspace.workspace_id),
        lambda: workflow.load_evidence(customer_b, workspace.workspace_id, evidence.event_id),
        lambda: workflow.ask(
            customer_b,
            workspace.workspace_id,
            evidence_id=evidence.event_id,
            question="How many records?",
        ),
        lambda: workflow.create_decision(
            customer_b,
            workspace.workspace_id,
            ask_id=ask.event_id,
            decision="Cross-tenant",
            rationale="Denied",
        ),
        lambda: workflow.request_approval(
            customer_b,
            workspace.workspace_id,
            decision_id=decision.payload["decision_id"],
            reason="Denied",
        ),
        lambda: workflow.transition_approval(
            customer_b,
            workspace.workspace_id,
            approval_id=request.payload["approval_id"],
            target="APPROVED",
            reason="Denied",
        ),
        lambda: workflow.export_evidence(
            customer_b,
            workspace.workspace_id,
            approval_id=request.payload["approval_id"],
        ),
    ):
        with pytest.raises(PermissionError):
            operation()


def test_retries_are_idempotent_and_invalid_or_unsupported_inputs_fail(workflow):
    customer = _context(ORG_A, user_id="customer")
    workspace = workflow.create_workspace(
        customer, name="Retry workspace", operation_id="stable-workspace-op"
    )
    assert workflow.create_workspace(
        customer, name="Retry workspace", operation_id="stable-workspace-op"
    ).event_id == workspace.event_id
    evidence = workflow.upload_evidence(
        customer,
        workspace.workspace_id,
        filename="customer-costs.csv",
        content=CSV,
        input_profile="Generic technology-cost Excel/CSV",
    )
    assert workflow.upload_evidence(
        customer,
        workspace.workspace_id,
        filename="customer-costs.csv",
        content=CSV,
        input_profile="Generic technology-cost Excel/CSV",
    ).event_id == evidence.event_id
    ask = workflow.ask(
        customer,
        workspace.workspace_id,
        evidence_id=evidence.event_id,
        question="How many evidence records are present?",
    )
    assert workflow.ask(
        customer,
        workspace.workspace_id,
        evidence_id=evidence.event_id,
        question="How many evidence records are present?",
    ).event_id == ask.event_id
    resumed = workflow.resume_workspace(customer, workspace.workspace_id)
    same_question = [
        item for item in resumed["asks"]
        if item["payload"]["question"].startswith("How many")
    ]
    assert len(same_question) == 1
    with pytest.raises(CustomerWorkflowError, match="grounded in evidence"):
        workflow.create_decision(
            customer,
            workspace.workspace_id,
            ask_id=workflow.ask(
                customer,
                workspace.workspace_id,
                evidence_id=evidence.event_id,
                question="What is the security risk?",
            ).event_id,
            decision="Unsupported",
            rationale="No evidence.",
        )
    with pytest.raises(CustomerWorkflowError, match="CSV or XLSX"):
        workflow.upload_evidence(
            customer,
            workspace.workspace_id,
            filename="invalid.pdf",
            content=b"%PDF-1.7",
            input_profile="Generic technology-cost Excel/CSV",
        )


def test_approval_stage_is_atomic_under_concurrent_duplicate_actions(workflow):
    requester = _context(ORG_A, user_id="requester")
    workspace, _evidence, ask = _create_evidence_and_ask(workflow, requester)
    decision = workflow.create_decision(
        requester,
        workspace.workspace_id,
        ask_id=ask.event_id,
        decision="Review",
        rationale="Grounded in evidence.",
    )
    request = workflow.request_approval(
        requester,
        workspace.workspace_id,
        decision_id=decision.payload["decision_id"],
        reason="Request approval.",
    )
    finance = _context(ORG_A, user_id="finance", role="finance")

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(
            pool.map(
                lambda _index: workflow.transition_approval(
                    finance,
                    workspace.workspace_id,
                    approval_id=request.payload["approval_id"],
                    target="APPROVED",
                    reason="Finance approval.",
                ),
                range(2),
            )
        )
    assert results[0].event_id == results[1].event_id
    resumed = workflow.resume_workspace(requester, workspace.workspace_id)
    assert len(
        [
            item for item in resumed["approvals"]
            if item["event_type"] == "APPROVAL_TRANSITIONED"
        ]
    ) == 1
    with pytest.raises(PermissionError, match="assigned to another role"):
        workflow.transition_approval(
            finance,
            workspace.workspace_id,
            approval_id=request.payload["approval_id"],
            target="APPROVED",
            reason="A second approval must not skip the CIO stage.",
        )


def test_workflow_records_are_encrypted_append_only_and_failure_does_not_duplicate(
    workflow, monkeypatch, tmp_path
):
    customer = _context(ORG_A, user_id="customer")
    workspace = workflow.create_workspace(customer, name="Protected records")
    content = b"Provider,Service,Cost,Currency\nAWS,EC2,123.45,USD\n"
    evidence = workflow.upload_evidence(
        customer,
        workspace.workspace_id,
        filename="private-costs.csv",
        content=content,
        input_profile="Generic technology-cost Excel/CSV",
    )
    connection = sqlite3.connect(workflow.repository.database)
    try:
        encrypted = connection.execute(
            "SELECT payload_ciphertext FROM customer_workflow_events WHERE event_id=?",
            (evidence.event_id,),
        ).fetchone()[0]
        assert "private-costs.csv" not in encrypted
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            connection.execute(
                "UPDATE customer_workflow_events SET event_type='WORKSPACE_CREATED' "
                "WHERE event_id=?",
                (evidence.event_id,),
            )
        connection.rollback()
    finally:
        connection.close()

    original_append = workflow.repository.append

    def fail_append(**kwargs):
        raise RuntimeError("injected persistence failure")

    monkeypatch.setattr(workflow.repository, "append", fail_append)
    with pytest.raises(RuntimeError, match="injected persistence failure"):
        workflow.upload_evidence(
            customer,
            workspace.workspace_id,
            filename="other-costs.csv",
            content=b"Provider,Service,Cost,Currency\nGCP,Compute,3,USD\n",
            input_profile="Generic technology-cost Excel/CSV",
        )
    monkeypatch.setattr(workflow.repository, "append", original_append)
    restored = workflow.resume_workspace(customer, workspace.workspace_id)
    assert len(restored["evidence"]) == 1
    assert len(list(tmp_path.joinpath("encrypted-evidence").rglob("*.tmp"))) == 0


def test_read_only_tenant_roles_cannot_create_or_approve_decisions(workflow):
    owner = _context(ORG_A, user_id="owner", role="executive")
    auditor = _context(ORG_A, user_id="auditor", role="auditor")
    workspace, _evidence, ask = _create_evidence_and_ask(workflow, owner)
    decision = workflow.create_decision(
        owner,
        workspace.workspace_id,
        ask_id=ask.event_id,
        decision="Retain the uploaded evidence for review",
        rationale="This decision is grounded in the saved Ask response.",
    )
    request = workflow.request_approval(
        owner,
        workspace.workspace_id,
        decision_id=decision.payload["decision_id"],
        reason="Request a staged customer approval.",
    )

    with pytest.raises(PermissionError, match="cannot create a customer workspace"):
        workflow.create_workspace(auditor, name="Unauthorized workspace")
    with pytest.raises(PermissionError, match="cannot create customer decisions"):
        workflow.create_decision(
            auditor,
            workspace.workspace_id,
            ask_id=ask.event_id,
            decision="Unauthorized",
            rationale="Denied",
        )
    with pytest.raises(PermissionError, match="cannot request customer approval"):
        workflow.request_approval(
            auditor,
            workspace.workspace_id,
            decision_id=decision.payload["decision_id"],
            reason="Denied",
        )
    assert workflow.request_approval(
        owner,
        workspace.workspace_id,
        decision_id=decision.payload["decision_id"],
        reason="Request a staged customer approval.",
    ).event_id == request.event_id
    with pytest.raises(CustomerWorkflowError, match="different request reason"):
        workflow.request_approval(
            owner,
            workspace.workspace_id,
            decision_id=decision.payload["decision_id"],
            reason="Change the approval record on retry.",
        )


def test_missing_evidence_key_fails_before_database_migration(monkeypatch, tmp_path):
    database = tmp_path / "customer-workflow.sqlite"
    monkeypatch.setenv("NEXORA_UNIVERSAL_EVIDENCE_DB", str(database))
    monkeypatch.setenv("NEXORA_CUSTOMER_WORKFLOW_KEY", Fernet.generate_key().decode("ascii"))
    monkeypatch.delenv("NEXORA_CUSTOMER_EVIDENCE_KEY", raising=False)

    with pytest.raises(CustomerWorkflowError, match="NEXORA_CUSTOMER_EVIDENCE_KEY"):
        CustomerWorkflowService.from_environment()
    assert not database.exists()
