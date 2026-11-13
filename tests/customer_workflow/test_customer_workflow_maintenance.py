import sqlite3
from uuid import uuid4

import pytest
from cryptography.fernet import Fernet

from auth.authenticated_tenant import AuthenticatedTenantContext
from services.customer_workflow_maintenance import (
    backup_customer_store,
    restore_customer_store,
    rotate_customer_store_keys,
    verify_customer_store,
)
from services.customer_workflow_service import (
    CustomerWorkflowError,
    CustomerWorkflowService,
    SQLiteCustomerWorkflowRepository,
)

CSV = b"Provider,Service,Cost,Currency\nAWS,EC2,12.50,USD\nAzure,Storage,7.50,USD\n"


def _context():
    return AuthenticatedTenantContext(
        organization_id="11111111-1111-4111-8111-111111111111",
        organization_name="Synthetic Customer",
        user_id=str(uuid4()),
        user_email="customer-a@example.test",
        role="client_admin",
        authorization_claims=frozenset(),
        tenant_id="11111111-1111-4111-8111-111111111111",
    )


def _store(directory, workflow_key, evidence_key):
    database = directory / "database.sqlite"
    evidence_root = directory / "evidence"
    service = CustomerWorkflowService(
        SQLiteCustomerWorkflowRepository(database, key=workflow_key),
        evidence_root=evidence_root,
        evidence_key=evidence_key,
    )
    context = _context()
    workspace = service.create_workspace(context, name="Maintenance qualification")
    evidence = service.upload_evidence(
        context,
        workspace.workspace_id,
        filename="customer-costs.csv",
        content=CSV,
        input_profile="Generic technology-cost Excel/CSV",
    )
    ask = service.ask(
        context,
        workspace.workspace_id,
        evidence_id=evidence.event_id,
        question="How many evidence records are present?",
    )
    return database, evidence_root, service, context, workspace, evidence, ask


def test_backup_restore_preserves_encrypted_events_and_detects_corruption(tmp_path):
    workflow_key = Fernet.generate_key()
    evidence_key = Fernet.generate_key()
    source = tmp_path / "source"
    source.mkdir()
    database, evidence_root, service, context, workspace, evidence, ask = _store(
        source, workflow_key, evidence_key
    )

    backup = tmp_path / "backup"
    backed_up = backup_customer_store(
        database,
        evidence_root,
        backup,
        workflow_key=workflow_key,
        evidence_key=evidence_key,
    )
    restored = tmp_path / "restored"
    restored_result = restore_customer_store(
        backup,
        restored,
        workflow_key=workflow_key,
        evidence_key=evidence_key,
    )

    resumed_service = CustomerWorkflowService(
        SQLiteCustomerWorkflowRepository(restored / "database.sqlite", key=workflow_key),
        evidence_root=restored / "evidence",
        evidence_key=evidence_key,
    )
    records = resumed_service.resume_workspace(context, workspace.workspace_id)
    assert backed_up == restored_result == {"events": 3, "evidence_files": 1}
    assert [row["event_id"] for row in records["evidence"]] == [evidence.event_id]
    assert [row["event_id"] for row in records["asks"]] == [ask.event_id]
    assert resumed_service.load_evidence(context, workspace.workspace_id, evidence.event_id) == CSV

    encrypted_source = next((restored / "evidence").rglob("*.enc"))
    encrypted_source.write_bytes(encrypted_source.read_bytes()[:-2] + b"xx")
    with pytest.raises(CustomerWorkflowError, match="manifest checks"):
        verify_customer_store(
            restored / "database.sqlite",
            restored / "evidence",
            workflow_key=workflow_key,
            evidence_key=evidence_key,
            manifest_directory=restored,
        )


def test_rotation_preserves_history_and_rejects_old_keys(tmp_path):
    workflow_key = Fernet.generate_key()
    evidence_key = Fernet.generate_key()
    new_workflow_key = Fernet.generate_key()
    new_evidence_key = Fernet.generate_key()
    source = tmp_path / "source"
    source.mkdir()
    database, evidence_root, _service, context, workspace, evidence, ask = _store(
        source, workflow_key, evidence_key
    )

    rotated = tmp_path / "rotated"
    result = rotate_customer_store_keys(
        database,
        evidence_root,
        rotated,
        workflow_key=workflow_key,
        evidence_key=evidence_key,
        new_workflow_key=new_workflow_key,
        new_evidence_key=new_evidence_key,
    )
    assert result == {"events": 3, "evidence_files": 1}
    rotated_service = CustomerWorkflowService(
        SQLiteCustomerWorkflowRepository(
            rotated / "database.sqlite",
            key=new_workflow_key,
        ),
        evidence_root=rotated / "evidence",
        evidence_key=new_evidence_key,
    )
    records = rotated_service.resume_workspace(context, workspace.workspace_id)
    assert [row["event_id"] for row in records["evidence"]] == [evidence.event_id]
    assert [row["event_id"] for row in records["asks"]] == [ask.event_id]
    assert rotated_service.load_evidence(context, workspace.workspace_id, evidence.event_id) == CSV
    with pytest.raises(CustomerWorkflowError, match="key does not match"):
        verify_customer_store(
            rotated / "database.sqlite",
            rotated / "evidence",
            workflow_key=workflow_key,
            evidence_key=evidence_key,
            manifest_directory=rotated,
        )
    assert database.is_file()
    assert evidence_root.is_dir()


def test_event_payload_fingerprint_detects_controlled_database_corruption(tmp_path):
    workflow_key = Fernet.generate_key()
    evidence_key = Fernet.generate_key()
    source = tmp_path / "source"
    source.mkdir()
    database, _evidence_root, _service, _context_value, _workspace, *_ = _store(
        source, workflow_key, evidence_key
    )

    connection = sqlite3.connect(database)
    try:
        connection.execute("DROP TRIGGER customer_workflow_events_no_update")
        connection.execute(
            "UPDATE customer_workflow_events SET payload_fingerprint=?",
            ("0" * 64,),
        )
        connection.commit()
    finally:
        connection.close()

    with pytest.raises(CustomerWorkflowError, match="integrity checks"):
        verify_customer_store(
            database,
            source / "evidence",
            workflow_key=workflow_key,
            evidence_key=evidence_key,
        )
