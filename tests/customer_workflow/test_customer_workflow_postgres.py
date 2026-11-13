from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import socket
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from threading import Barrier
from uuid import uuid4

import psycopg2
import pytest
from cryptography.fernet import Fernet
from psycopg2 import sql
from psycopg2.extensions import make_dsn

from auth.authenticated_tenant import AuthenticatedTenantContext
from backend import supabase_auth
from scripts import postgres_v1_workflow_recovery as v1_workflow_recovery
from scripts.postgres_recovery_package import (
    DatabaseConfig,
    RecoveryPackageError,
    create_backup_package,
    restore_backup_package,
    verify_backup_package,
)
from scripts.test_only_postgres_replay import (
    AUTH_FIXTURE,
    CATALOG_ASSERTIONS,
    SYNTHETIC_TENANT_ASSERTIONS,
    normalized_sql_sha256,
    validate_manifest,
)
from scripts.verify_customer_workflow_recovery import verify_recovered_workflow
from services.customer_workflow_service import (
    CustomerWorkflowError,
    CustomerWorkflowService,
)
from services.postgres_customer_workflow_repository import (
    PostgresCustomerWorkflowRepository,
)

ROOT = Path(__file__).resolve().parents[2]
PG_BIN = Path("C:/Program Files/PostgreSQL/18/bin")
POSTGRES_CONTRACT = (
    ROOT
    / "database"
    / "contracts"
    / "v1_customer_workflow"
    / "001_customer_workflow_postgres.sql"
)
CSV = b"Provider,Service,Cost,Currency\nAWS,EC2,12.50,USD\nAzure,Storage,7.50,USD\n"
ORG_A = "11111111-1111-4111-8111-111111111111"
ORG_B = "22222222-2222-4222-8222-222222222222"
JWT_SECRET = secrets.token_urlsafe(32)
JWT_ISSUER = "https://synthetic-auth.example.test"
IDENTITIES = {
    "customer-a": (ORG_A, "client_admin"),
    "finance-a": (ORG_A, "finance"),
    "finance-a-2": (ORG_A, "finance"),
    "cio-a": (ORG_A, "cio"),
    "executive-a": (ORG_A, "executive"),
    "auditor-a": (ORG_A, "auditor"),
    "customer-b": (ORG_B, "client_admin"),
}
IDENTITY_IDS = {name: str(uuid4()) for name in IDENTITIES}


def _run_pg(binary: str, *args: str | Path, capture_output: bool = True) -> None:
    result = subprocess.run(
        [str(PG_BIN / binary), *map(str, args)],
        capture_output=capture_output,
        stdout=None if capture_output else subprocess.DEVNULL,
        stderr=None if capture_output else subprocess.DEVNULL,
        text=True,
        timeout=60,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    if result.returncode:
        details = result.stderr[-3000:] if result.stderr else "no stderr captured"
        raise RuntimeError(f"{binary} failed: {details}")


def _run_psql(port: int, owner: str, *args: str | Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            str(PG_BIN / "psql.exe"),
            "--no-psqlrc",
            "--set",
            "ON_ERROR_STOP=1",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--username",
            owner,
            "--dbname",
            "postgres",
            *map(str, args),
        ],
        capture_output=True,
        text=True,
        timeout=60,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )


def _bootstrap_canonical_migrations(
    port: int, admin_dsn: str
) -> dict[str, int | bool]:
    migration_paths = validate_manifest(ROOT)
    if len(migration_paths) != 43:
        raise RuntimeError("expected the current 43-file PostgreSQL migration chain")

    with psycopg2.connect(admin_dsn) as connection:
        with connection.cursor() as cursor:
            cursor.execute("CREATE ROLE postgres SUPERUSER LOGIN")
            cursor.execute("CREATE SCHEMA nexora_test_migrations")
            cursor.execute(
                """
                CREATE TABLE nexora_test_migrations.applied (
                    path text PRIMARY KEY,
                    sha256 text NOT NULL
                )
                """
            )

    fixture = _run_psql(
        port, "postgres", "--single-transaction", "--file", AUTH_FIXTURE
    )
    if fixture.returncode:
        raise RuntimeError(f"test-only Auth fixture failed: {fixture.stderr[-3000:]}")

    failed_migration = _run_psql(
        port,
        "postgres",
        "--single-transaction",
        "--command",
        """
        CREATE TABLE nexora_test_migrations.rollback_probe (id integer);
        SELECT 1 / 0;
        """,
    )
    if failed_migration.returncode == 0:
        raise RuntimeError("intentional migration failure unexpectedly succeeded")
    with psycopg2.connect(admin_dsn) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT to_regclass(
                    'nexora_test_migrations.rollback_probe'
                ) IS NULL
                """
            )
            rollback_verified = cursor.fetchone() == (True,)
    if not rollback_verified:
        raise RuntimeError("failed migration left a partial schema change")

    applied_count = 0
    skipped_count = 0
    for relative_path in migration_paths:
        source = ROOT / relative_path
        expected_hash = normalized_sql_sha256(source)
        with psycopg2.connect(admin_dsn) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT sha256 FROM nexora_test_migrations.applied
                    WHERE path = %s
                    """,
                    (relative_path,),
                )
                existing = cursor.fetchone()
        if existing is not None:
            if existing[0] != expected_hash:
                raise RuntimeError(
                    f"applied migration hash changed: {Path(relative_path).name}"
                )
            skipped_count += 1
            continue

        result = _run_psql(
            port,
            "postgres",
            "--single-transaction",
            "--file",
            source,
        )
        if result.returncode:
            raise RuntimeError(
                f"migration failed: {Path(relative_path).name}: {result.stderr[-3000:]}"
            )
        with psycopg2.connect(admin_dsn) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO nexora_test_migrations.applied (path, sha256)
                    VALUES (%s, %s)
                    """,
                    (relative_path, expected_hash),
                )
        applied_count += 1

    for relative_path in migration_paths:
        expected_hash = normalized_sql_sha256(ROOT / relative_path)
        with psycopg2.connect(admin_dsn) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT sha256 FROM nexora_test_migrations.applied
                    WHERE path = %s
                    """,
                    (relative_path,),
                )
                if cursor.fetchone() != (expected_hash,):
                    raise RuntimeError(
                        f"migration replay ledger mismatch: {Path(relative_path).name}"
                    )

    if applied_count != 43 or skipped_count != 0:
        raise RuntimeError("first migration pass did not apply all 43 inputs")

    second_pass_skipped = 0
    for relative_path in migration_paths:
        expected_hash = normalized_sql_sha256(ROOT / relative_path)
        with psycopg2.connect(admin_dsn) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT sha256 FROM nexora_test_migrations.applied
                    WHERE path = %s
                    """,
                    (relative_path,),
                )
                existing = cursor.fetchone()
        if existing != (expected_hash,):
            raise RuntimeError(
                f"second migration pass did not safely skip {Path(relative_path).name}"
            )
        second_pass_skipped += 1

    for label, sql_text in (
        ("catalog assertions", CATALOG_ASSERTIONS),
        ("synthetic tenant assertions", SYNTHETIC_TENANT_ASSERTIONS),
    ):
        result = _run_psql(port, "postgres", "--command", sql_text)
        if result.returncode:
            raise RuntimeError(f"{label} failed: {result.stderr[-3000:]}")

    return {
        "migration_count": applied_count,
        "idempotent_skips": second_pass_skipped,
        "rollback_verified": rollback_verified,
    }


@pytest.fixture
def postgres_cluster(request):
    if os.getenv("NEXORA_CUSTOMER_WORKFLOW_LOCAL_PG") != "1":
        pytest.skip(
            "set NEXORA_CUSTOMER_WORKFLOW_LOCAL_PG=1 to create a fresh synthetic PostgreSQL cluster"
        )
    if not (PG_BIN / "initdb.exe").is_file():
        pytest.skip("PostgreSQL 18 local initdb binary unavailable")
    with tempfile.TemporaryDirectory(prefix="nexora-customer-pg-") as directory:
        root = Path(directory).resolve()
        data = root / "data"
        owner = "nexora_test_admin"

        _run_pg(
            "initdb.exe",
            "-D",
            data,
            "-U",
            owner,
            "-A",
            "trust",
            "--encoding=UTF8",
            "--no-locale",
        )
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        _run_pg(
            "pg_ctl.exe",
            "-D",
            data,
            "-l",
            root / "postgres.log",
            "-w",
            "start",
            "-o",
            f"-h 127.0.0.1 -p {port} -c max_connections=30",
            capture_output=False,
        )
        dsn = (
            f"host=127.0.0.1 port={port} dbname=postgres user={owner} "
            "connect_timeout=3 options='-c statement_timeout=60000'"
        )
        admin = None
        try:
            canonical_results = None
            if getattr(request, "param", False):
                canonical_results = _bootstrap_canonical_migrations(port, dsn)
            admin = psycopg2.connect(dsn)
            with admin:
                with admin.cursor() as cursor:
                    cursor.execute("SET statement_timeout = '60s'")
                    cursor.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto WITH SCHEMA public")
                    if not canonical_results:
                        for role in ("anon", "authenticated", "service_role"):
                            cursor.execute(
                                sql.SQL("CREATE ROLE {} NOLOGIN").format(
                                    sql.Identifier(role)
                                )
                            )
                        cursor.execute(
                            """
                            CREATE TABLE public.organizations (
                                id uuid PRIMARY KEY,
                                name text NOT NULL,
                                status text NOT NULL
                            )
                            """
                        )
                        cursor.execute(
                            "INSERT INTO public.organizations (id, name, status) "
                            "VALUES (%s, 'Synthetic A', 'active'), "
                            "(%s, 'Synthetic B', 'active')",
                            (ORG_A, ORG_B),
                        )
                    if canonical_results:
                        cursor.executemany(
                            "INSERT INTO auth.users (id) VALUES (%s)",
                            [(IDENTITY_IDS[name],) for name in IDENTITIES],
                        )
                    cursor.execute(POSTGRES_CONTRACT.read_text(encoding="utf-8"))
                    cursor.executemany(
                        """
                        INSERT INTO nexora_identity.memberships
                            (auth_user_id, org_id, tenant_id, organization_name,
                             workspace_id, role, status)
                        VALUES (%s, %s, %s, %s, NULL, %s, 'active')
                        """,
                        [
                            (
                                IDENTITY_IDS[name],
                                organization_id,
                                organization_id,
                                f"Synthetic {organization_id[-1]}",
                                role,
                            )
                            for name, (organization_id, role) in IDENTITIES.items()
                        ],
                    )
                    password = uuid4().hex
                    cursor.execute(
                        sql.SQL(
                            """
                            CREATE ROLE nxr_customer_workflow_app LOGIN
                                NOSUPERUSER NOCREATEDB NOCREATEROLE INHERIT NOBYPASSRLS
                                PASSWORD {}
                            """
                        ).format(sql.Literal(password))
                    )
                    cursor.execute(
                        """
                        GRANT nxr_customer_workflow_runtime
                        TO nxr_customer_workflow_app
                        """
                    )
                    cursor.execute(
                        "SELECT system_identifier::text FROM pg_control_system()"
                    )
                    system_identifier = cursor.fetchone()[0]
            provision_environment = {
                name: os.environ[name]
                for name in ("PATH", "SYSTEMROOT", "TEMP", "TMP")
                if name in os.environ
            }
            provision_environment.update(
                PYTHONPATH=str(ROOT),
                NEXORA_CUSTOMER_WORKFLOW_MIGRATION_DSN=dsn,
                NEXORA_CUSTOMER_WORKFLOW_DB_PASSWORD=password,
                NEXORA_CUSTOMER_WORKFLOW_JWT_SECRET=JWT_SECRET,
                NEXORA_CUSTOMER_WORKFLOW_JWT_ISSUER=JWT_ISSUER,
                NEXORA_CUSTOMER_WORKFLOW_JWT_MODE="synthetic_hs256",
                ENVIRONMENT="test",
            )
            provisioned = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "scripts.provision_customer_workflow_postgres",
                ],
                cwd=ROOT,
                env=provision_environment,
                capture_output=True,
                text=True,
                timeout=60,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            if provisioned.returncode:
                raise RuntimeError(
                    "PostgreSQL customer workflow provisioning failed: "
                    f"{provisioned.stderr[-3000:]}"
                )
            yield {
                "dsn": (
                    f"host=127.0.0.1 port={port} dbname=postgres "
                    f"user=nxr_customer_workflow_app password={password} connect_timeout=2"
                ),
                "admin_dsn": dsn,
                "admin_user": owner,
                "port": port,
                "data_directory": str(data),
                "system_identifier": system_identifier,
                "pg_ctl": PG_BIN / "pg_ctl.exe",
                "canonical_bootstrap": canonical_results,
            }
        finally:
            if admin is not None:
                admin.close()
            _run_pg("pg_ctl.exe", "-D", data, "-w", "stop", "-m", "fast")


def context(name: str) -> AuthenticatedTenantContext:
    organization_id, role = IDENTITIES[name]
    return AuthenticatedTenantContext(
        organization_id=organization_id,
        organization_name=f"Synthetic {organization_id[-1]}",
        user_id=IDENTITY_IDS[name],
        user_email=f"{name}@example.test",
        role=role,
        authorization_claims=frozenset(),
        tenant_id=organization_id,
        auth_access_token=_access_token(IDENTITY_IDS[name]),
    )


def _b64url(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _access_token(
    subject: str,
    *,
    token_role: str = "authenticated",
    secret: str | None = None,
    issuer: str | None = None,
) -> str:
    signing_secret = secret or JWT_SECRET
    token_issuer = issuer or JWT_ISSUER
    header = _b64url(b'{"alg":"HS256","typ":"JWT"}')
    claims = _b64url(
        json.dumps(
            {
                "aud": "authenticated",
                "exp": int(time.time()) + 3600,
                "iss": token_issuer,
                "role": token_role,
                "sub": subject,
            },
            separators=(",", ":"),
        ).encode("utf-8")
    )
    signing_input = f"{header}.{claims}".encode("ascii")
    signature = hmac.new(signing_secret.encode("utf-8"), signing_input, hashlib.sha256).digest()
    return f"{header}.{claims}.{_b64url(signature)}"


def _tamper_access_token(token: str) -> str:
    header, claims, signature = token.split(".")
    replacement = "A" if signature[0] != "A" else "B"
    return f"{header}.{claims}.{replacement}{signature[1:]}"


@pytest.fixture
def workflow(postgres_cluster, tmp_path):
    workflow_key = Fernet.generate_key()
    evidence_key = Fernet.generate_key()
    repository = PostgresCustomerWorkflowRepository(
        postgres_cluster["dsn"],
        key=workflow_key,
        connection_factory=lambda: psycopg2.connect(
            postgres_cluster["dsn"],
            connect_timeout=2,
            options="-c statement_timeout=60000",
        ),
    )
    return (
        CustomerWorkflowService(
            repository,
            evidence_root=tmp_path / "unused-postgres-evidence-root",
            evidence_key=evidence_key,
        ),
        repository,
        workflow_key,
        evidence_key,
    )


def _journey(workflow):
    service, repository, _, _ = workflow
    requester = context("customer-a")
    workspace = service.create_workspace(requester, name="Synthetic PG workspace")
    evidence = service.upload_evidence(
        requester,
        workspace.workspace_id,
        filename="customer-costs.csv",
        content=CSV,
        input_profile="Generic technology-cost Excel/CSV",
    )
    ask = service.ask(
        requester,
        workspace.workspace_id,
        evidence_id=evidence.event_id,
        question="How many evidence records are present?",
    )
    decision = service.create_decision(
        requester,
        workspace.workspace_id,
        ask_id=ask.event_id,
        decision="Review observed synthetic cloud costs",
        rationale="The uploaded records contain two cost observations.",
    )
    approval = service.request_approval(
        requester,
        workspace.workspace_id,
        decision_id=decision.payload["decision_id"],
        reason="Request staged synthetic customer approval.",
    )
    return requester, workspace, evidence, ask, decision, approval


def test_real_postgres_customer_journey_rls_recovery_and_least_privilege(
    workflow, postgres_cluster
):
    service, repository, workflow_key, evidence_key = workflow
    requester, workspace, evidence, ask, decision, approval = _journey(workflow)

    assert evidence.payload["validation_status"] == "PASS"
    assert ask.payload["state"] == "GROUNDED"
    assert ask.payload["evidence_references"][0]["record_id"] == evidence.event_id
    assert service.upload_evidence(
        requester,
        workspace.workspace_id,
        filename="customer-costs.csv",
        content=CSV,
        input_profile="Generic technology-cost Excel/CSV",
    ).event_id == evidence.event_id

    with pytest.raises(PermissionError):
        service.export_evidence(
            context("auditor-a"),
            workspace.workspace_id,
            approval_id=approval.payload["approval_id"],
        )

    forged_finance = context("finance-a")
    for forged_context in (
        replace(forged_finance, user_id=IDENTITY_IDS["customer-a"]),
        replace(forged_finance, role="executive"),
    ):
        with pytest.raises(PermissionError):
            service.transition_approval(
                forged_context,
                workspace.workspace_id,
                approval_id=approval.payload["approval_id"],
                target="APPROVED",
                reason="Forged actor or role must not authorize this transition.",
            )

    for approver in ("finance-a", "cio-a", "executive-a"):
        latest = service.transition_approval(
            context(approver),
            workspace.workspace_id,
            approval_id=approval.payload["approval_id"],
            target="APPROVED",
            reason=f"{approver} approved the synthetic customer decision.",
        )
    assert latest.payload["approval"]["state"] == "APPROVED"
    export = service.export_evidence(
        context("executive-a"),
        workspace.workspace_id,
        approval_id=approval.payload["approval_id"],
    )
    assert service.export_evidence(
        context("executive-a"),
        workspace.workspace_id,
        approval_id=approval.payload["approval_id"],
    ).event_id == export.event_id

    customer_b = context("customer-b")
    assert service.list_workspaces(customer_b) == ()
    with pytest.raises(PermissionError, match="verified authenticated tenant context is required"):
        repository.list_workspaces(None)
    tenant_b_workspace = service.create_workspace(
        customer_b, name="Synthetic Customer B workflow"
    )
    tenant_b_evidence = service.upload_evidence(
        customer_b,
        tenant_b_workspace.workspace_id,
        filename="customer-b-costs.csv",
        content=CSV,
        input_profile="Generic technology-cost Excel/CSV",
    )
    tenant_b_ask = service.ask(
        customer_b,
        tenant_b_workspace.workspace_id,
        evidence_id=tenant_b_evidence.event_id,
        question="How many evidence records are present?",
    )
    assert tenant_b_ask.payload["state"] == "GROUNDED"
    assert [row.workspace_id for row in service.list_workspaces(customer_b)] == [
        tenant_b_workspace.workspace_id
    ]
    for operation in (
        lambda: service.resume_workspace(customer_b, workspace.workspace_id),
        lambda: service.load_evidence(customer_b, workspace.workspace_id, evidence.event_id),
        lambda: service.create_decision(
            customer_b,
            workspace.workspace_id,
            ask_id=ask.event_id,
            decision="Unauthorized cross-tenant decision",
            rationale="Customer B must not access Customer A's Ask.",
        ),
        lambda: service.transition_approval(
            customer_b,
            workspace.workspace_id,
            approval_id=approval.payload["approval_id"],
            target="APPROVED",
            reason="Unauthorized cross-tenant approval.",
        ),
        lambda: service.export_evidence(
            customer_b, workspace.workspace_id, approval_id=approval.payload["approval_id"]
        ),
    ):
        with pytest.raises(PermissionError):
            operation()

    invalid_signature = _tamper_access_token(requester.auth_access_token)
    with pytest.raises(PermissionError, match="identity is not authorized"):
        service.list_workspaces(
            replace(requester, auth_access_token=invalid_signature)
        )
    forged_jwt_role = _access_token(
        requester.user_id,
        token_role="service_role",
    )
    with pytest.raises(PermissionError, match="identity is not authorized"):
        service.list_workspaces(
            replace(requester, auth_access_token=forged_jwt_role)
        )

    with pytest.raises(PermissionError):
        repository.append(
            context=replace(
                customer_b,
                organization_id=ORG_A,
                organization_name="Synthetic A",
                tenant_id=ORG_A,
            ),
            workspace_id=workspace.workspace_id,
            event_type="WORKSPACE_CREATED",
            idempotency_key="forged-tenant-workspace",
            payload={"name": "forged"},
        )

    with pytest.raises(PermissionError, match="authorization denied"):
        with repository._connection(requester) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT set_config('nexora.tenant_id', %s, true)",
                    (ORG_B,),
                )
                cursor.execute(
                    """
                    INSERT INTO nexora_customer_workflow.events (
                        event_id, event_type, organization_id, tenant_id,
                        workspace_id, actor_id, idempotency_key,
                        payload_fingerprint, payload_ciphertext
                    ) VALUES (%s, 'WORKSPACE_CREATED', %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        str(uuid4()),
                        ORG_A,
                        ORG_B,
                        workspace.workspace_id,
                        requester.user_id,
                        "forged-database-tenant",
                        "0" * 64,
                        "not-a-customer-payload",
                    ),
                )

    with repository._connection(customer_b) as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT count(*) FROM nexora_identity.memberships")
            assert cursor.fetchone() == (1,)
            cursor.execute(
                "SELECT count(*) FROM nexora_customer_workflow.events "
                "WHERE organization_id = %s",
                (ORG_A,),
            )
            assert cursor.fetchone() == (0,)
            cursor.execute(
                """
                SELECT count(*) FROM nexora_customer_workflow.events
                WHERE organization_id = %s AND tenant_id = %s
                """,
                (ORG_A, ORG_A),
            )
            assert cursor.fetchone() == (0,)
            cursor.execute(
                """
                SELECT count(*) FROM nexora_customer_workflow.events
                WHERE organization_id = %s AND tenant_id = %s
                """,
                (ORG_B, ORG_B),
            )
            assert cursor.fetchone() == (3,)

    forged_runtime = repository.connection_factory()
    try:
        with forged_runtime:
            with forged_runtime.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT
                        set_config('nexora.organization_id', %s, true),
                        set_config('nexora.tenant_id', %s, true),
                        set_config('nexora.actor_id', %s, true),
                        set_config('nexora.role', %s, true)
                    """,
                    (
                        requester.organization_id,
                        requester.tenant_id,
                        requester.user_id,
                        requester.role,
                    ),
                )
                cursor.execute(
                    "SELECT count(*) FROM nexora_customer_workflow.events "
                    "WHERE organization_id = %s",
                    (ORG_A,),
                )
                assert cursor.fetchone() == (0,)
                cursor.execute(
                    "SELECT nexora_customer_workflow.verified_subject()"
                )
                assert cursor.fetchone() == (None,)
                cursor.execute(
                    "SELECT set_config('nexora.access_token', %s, true)",
                    (_tamper_access_token(requester.auth_access_token),),
                )
                cursor.execute(
                    "SELECT count(*) FROM nexora_customer_workflow.events "
                    "WHERE organization_id = %s",
                    (ORG_A,),
                )
                assert cursor.fetchone() == (0,)
                cursor.execute(
                    "SELECT nexora_customer_workflow.verified_subject()"
                )
                assert cursor.fetchone() == (None,)
                with pytest.raises(psycopg2.errors.InsufficientPrivilege):
                    cursor.execute(
                        """
                        INSERT INTO nexora_customer_workflow.events (
                            event_id, event_type, organization_id, tenant_id,
                            workspace_id, actor_id, idempotency_key,
                            payload_fingerprint, payload_ciphertext
                        ) VALUES (%s, 'WORKSPACE_CREATED', %s, %s, %s, %s, %s, %s, %s)
                        """,
                        (
                            str(uuid4()),
                            ORG_A,
                            ORG_A,
                            workspace.workspace_id,
                            requester.user_id,
                            "direct-sql-guc-spoof",
                            "1" * 64,
                            "forged-without-token",
                        ),
                    )
    finally:
        forged_runtime.close()


    forged_other_tenant = repository.connection_factory()
    try:
        with forged_other_tenant:
            with forged_other_tenant.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT
                        set_config('nexora.organization_id', %s, true),
                        set_config('nexora.tenant_id', %s, true),
                        set_config('nexora.actor_id', %s, true),
                        set_config('nexora.role', %s, true),
                        set_config('nexora.access_token', %s, true)
                    """,
                    (
                        ORG_A,
                        ORG_A,
                        requester.user_id,
                        requester.role,
                        customer_b.auth_access_token,
                    ),
                )
                cursor.execute(
                    "SELECT count(*) FROM nexora_customer_workflow.events "
                    "WHERE organization_id = %s",
                    (ORG_A,),
                )
                assert cursor.fetchone() == (0,)
    finally:
        forged_other_tenant.close()

    with pytest.raises(PermissionError, match="database authorization denied"):
        repository.append(
            context=context("auditor-a"),
            workspace_id=workspace.workspace_id,
            event_type="APPROVAL_TRANSITIONED",
            idempotency_key="direct-unauthorized-approval",
            payload={
                "approval_id": approval.payload["approval_id"],
                "approval": {
                    "request_id": approval.payload["approval_id"],
                    "organization_id": ORG_A,
                    "tenant_id": ORG_A,
                    "subject_id": decision.payload["decision_id"],
                    "requested_action": decision.payload["decision"],
                    "state": "PENDING",
                    "requesting_actor": requester.user_id,
                    "reason": "forged test transition",
                    "decision_actor": IDENTITY_IDS["auditor-a"],
                    "decision_at": None,
                    "workflow_stage": "CIO",
                    "current_approver_role": "cio",
                    "compatibility_id": None,
                    "escalated_to": None,
                },
                "history": {},
            },
        )
    with pytest.raises(PermissionError, match="cannot act as a customer approver"):
        service.transition_approval(
            context("auditor-a"),
            workspace.workspace_id,
            approval_id=approval.payload["approval_id"],
            target="APPROVED",
            reason="Unauthorized synthetic approval attempt.",
        )

    resumed_service = CustomerWorkflowService(
        PostgresCustomerWorkflowRepository(
            postgres_cluster["dsn"],
            key=workflow_key,
            connection_factory=lambda: psycopg2.connect(
                postgres_cluster["dsn"],
                connect_timeout=2,
                options="-c statement_timeout=60000",
            ),
        ),
        evidence_root="unused",
        evidence_key=evidence_key,
    )
    resumed = resumed_service.resume_workspace(requester, workspace.workspace_id)
    assert [row["event_id"] for row in resumed["evidence"]] == [evidence.event_id]
    assert [row["event_id"] for row in resumed["asks"]] == [ask.event_id]
    assert [row["event_id"] for row in resumed["decisions"]] == [decision.event_id]
    assert len(resumed["approvals"]) == 4
    assert [row["event_id"] for row in resumed["exports"]] == [export.event_id]
    assert (
        resumed_service.load_evidence(requester, workspace.workspace_id, evidence.event_id)
        == CSV
    )

    admin = psycopg2.connect(postgres_cluster["admin_dsn"])
    try:
        with admin.cursor() as cursor:
            cursor.execute(POSTGRES_CONTRACT.read_text(encoding="utf-8"))
            cursor.execute(
                """
                SELECT relname, relrowsecurity, relforcerowsecurity
                FROM pg_class AS relation
                JOIN pg_namespace AS namespace ON namespace.oid = relation.relnamespace
                WHERE namespace.nspname = 'nexora_customer_workflow'
                  AND relation.relname IN ('events', 'evidence_objects', 'approvals')
                ORDER BY relname
                """
            )
            assert cursor.fetchall() == [
                ("approvals", True, True),
                ("events", True, True),
                ("evidence_objects", True, True),
            ]
            cursor.execute(
                """
                SELECT r.rolcanlogin, r.rolsuper, r.rolcreatedb, r.rolcreaterole,
                       r.rolbypassrls,
                       c.relrowsecurity, c.relforcerowsecurity
                FROM pg_roles AS r
                CROSS JOIN pg_class AS c
                JOIN pg_namespace AS n ON n.oid = c.relnamespace
                WHERE r.rolname = 'nxr_customer_workflow_app'
                  AND n.nspname = 'nexora_customer_workflow'
                  AND c.relname = 'events'
                """
            )
            assert cursor.fetchone() == (True, False, False, False, False, True, True)
            cursor.execute(
                """
                SELECT has_table_privilege(
                    'nxr_customer_workflow_app',
                    'nexora_customer_workflow.events', 'UPDATE'
                )
                """
            )
            assert cursor.fetchone() == (False,)
            cursor.execute(
                """
                SELECT has_table_privilege(
                    'nxr_customer_workflow_app',
                    'nexora_customer_workflow.approvals', 'UPDATE'
                )
                """
            )
            assert cursor.fetchone() == (False,)
            cursor.execute(
                """
                SELECT has_table_privilege(
                    'nxr_customer_workflow_app',
                    'nexora_customer_workflow.jwt_verification_settings', 'SELECT'
                )
                """
            )
            assert cursor.fetchone() == (False,)
            cursor.execute(
                "SELECT count(*) FROM nexora_customer_workflow.events"
            )
            assert cursor.fetchone() == (12,)
            cursor.execute(
                "SELECT count(*) FROM nexora_customer_workflow.evidence_objects"
            )
            assert cursor.fetchone() == (2,)
    finally:
        admin.close()


@pytest.mark.parametrize("postgres_cluster", [True], indirect=True)
def test_private_identity_mapping_revocation_ambiguity_and_workspace_scope(
    workflow, postgres_cluster, monkeypatch
):
    service, repository, _, _ = workflow
    member = context("customer-a")
    monkeypatch.setenv(
        "NEXORA_CUSTOMER_WORKFLOW_IDENTITY_DSN", postgres_cluster["dsn"]
    )
    assert supabase_auth._identity_membership(
        member.auth_access_token, member.user_id
    )["org_id"] == ORG_A

    first = service.create_workspace(member, name="Mapped workspace")
    second = service.create_workspace(member, name="Unmapped workspace")
    admin = psycopg2.connect(postgres_cluster["admin_dsn"])
    try:
        with admin:
            with admin.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE nexora_identity.memberships
                    SET workspace_id = %s
                    WHERE auth_user_id = %s::uuid AND org_id = %s::uuid
                    """,
                    (first.workspace_id, member.user_id, ORG_A),
                )
        assert [row.workspace_id for row in service.list_workspaces(member)] == [
            first.workspace_id
        ]
        with pytest.raises(PermissionError):
            service.resume_workspace(member, second.workspace_id)

        with admin:
            with admin.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO nexora_identity.memberships
                        (auth_user_id, org_id, tenant_id, organization_name,
                         workspace_id, role, status)
                    VALUES (%s, %s, %s, 'Synthetic B', NULL, 'viewer', 'active')
                    """,
                    (member.user_id, ORG_B, ORG_B),
                )
        with pytest.raises(supabase_auth.SupabaseMembershipRejected):
            supabase_auth._identity_membership(member.auth_access_token, member.user_id)

        with admin:
            with admin.cursor() as cursor:
                cursor.execute(
                    """
                    DELETE FROM nexora_identity.memberships
                    WHERE auth_user_id = %s::uuid AND org_id = %s::uuid
                    """,
                    (member.user_id, ORG_B),
                )
                cursor.execute(
                    """
                    UPDATE nexora_identity.memberships
                    SET status = 'revoked'
                    WHERE auth_user_id = %s::uuid AND org_id = %s::uuid
                    """,
                    (member.user_id, ORG_A),
                )
        with pytest.raises(supabase_auth.SupabaseMembershipRejected):
            supabase_auth._identity_membership(member.auth_access_token, member.user_id)
        with pytest.raises(PermissionError):
            repository.list_workspaces(member)
        with admin:
            with admin.cursor() as cursor:
                cursor.execute(
                    """
                    DELETE FROM nexora_identity.memberships
                    WHERE auth_user_id = %s::uuid AND org_id = %s::uuid
                    """,
                    (member.user_id, ORG_A),
                )
        with pytest.raises(supabase_auth.SupabaseMembershipRejected):
            supabase_auth._identity_membership(member.auth_access_token, member.user_id)
    finally:
        admin.close()


@pytest.mark.parametrize("postgres_cluster", [True], indirect=True)
def test_v1_customer_workflow_bootstraps_against_current_migration_chain(
    workflow, postgres_cluster, monkeypatch, tmp_path
):
    _, _, workflow_key, evidence_key = workflow
    monkeypatch.setenv("NEXORA_CUSTOMER_WORKFLOW_BACKEND", "postgres")
    monkeypatch.setenv("ENVIRONMENT", "test")
    monkeypatch.setenv("NEXORA_CUSTOMER_WORKFLOW_DSN", postgres_cluster["dsn"])
    monkeypatch.setenv("NEXORA_CUSTOMER_WORKFLOW_KEY", workflow_key.decode("ascii"))
    monkeypatch.setenv("NEXORA_CUSTOMER_EVIDENCE_KEY", evidence_key.decode("ascii"))
    monkeypatch.setenv("NEXORA_CUSTOMER_EVIDENCE_ROOT", str(tmp_path))

    service = CustomerWorkflowService.from_environment()
    requester = context("customer-a")
    workspace = service.create_workspace(requester, name="Canonical synthetic workspace")
    evidence = service.upload_evidence(
        requester,
        workspace.workspace_id,
        filename="canonical-costs.csv",
        content=CSV,
        input_profile="Generic technology-cost Excel/CSV",
    )
    ask = service.ask(
        requester,
        workspace.workspace_id,
        evidence_id=evidence.event_id,
        question="How many evidence records are present?",
    )
    decision = service.create_decision(
        requester,
        workspace.workspace_id,
        ask_id=ask.event_id,
        decision="Approve the synthetic cost review.",
        rationale="The bounded answer is linked to the uploaded evidence.",
    )
    approval = service.request_approval(
        requester,
        workspace.workspace_id,
        decision_id=decision.payload["decision_id"],
        reason="Request the staged synthetic approvals.",
    )
    for approver in ("finance-a", "cio-a", "executive-a"):
        service.transition_approval(
            context(approver),
            workspace.workspace_id,
            approval_id=approval.payload["approval_id"],
            target="APPROVED",
            reason=f"{approver} approved the synthetic decision.",
        )
    exported = service.export_evidence(
        context("executive-a"),
        workspace.workspace_id,
        approval_id=approval.payload["approval_id"],
    )

    resumed = service.resume_workspace(requester, workspace.workspace_id)
    assert [row["event_id"] for row in resumed["evidence"]] == [evidence.event_id]
    assert [row["event_id"] for row in resumed["asks"]] == [ask.event_id]
    assert [row["event_id"] for row in resumed["decisions"]] == [decision.event_id]
    assert len(resumed["approvals"]) == 4
    assert [row["event_id"] for row in resumed["exports"]] == [exported.event_id]
    assert service.list_workspaces(context("customer-b")) == ()
    with pytest.raises(PermissionError):
        service.resume_workspace(context("customer-b"), workspace.workspace_id)

    with psycopg2.connect(postgres_cluster["admin_dsn"]) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT encrypted_content
                FROM nexora_customer_workflow.evidence_objects
                WHERE event_id = %s
                """,
                (evidence.event_id,),
            )
            stored_ciphertext = bytes(cursor.fetchone()[0])
    assert CSV not in stored_ciphertext
    assert workflow_key not in stored_ciphertext
    assert evidence_key not in stored_ciphertext
    assert postgres_cluster["canonical_bootstrap"] == {
        "migration_count": 43,
        "idempotent_skips": 43,
        "rollback_verified": True,
    }


def test_postgres_retries_concurrent_approval_sequence_and_database_loss(
    workflow, postgres_cluster
):
    service, _, _, _ = workflow
    requester = context("customer-a")
    workspace = service.create_workspace(requester, name="Concurrent PG workspace")
    evidence = service.upload_evidence(
        requester,
        workspace.workspace_id,
        filename="concurrent.csv",
        content=CSV,
        input_profile="Generic technology-cost Excel/CSV",
    )
    ask = service.ask(
        requester,
        workspace.workspace_id,
        evidence_id=evidence.event_id,
        question="How many evidence records are present?",
    )
    decision = service.create_decision(
        requester,
        workspace.workspace_id,
        ask_id=ask.event_id,
        decision="Review synthetic costs",
        rationale="The evidence supports this review.",
    )
    approval = service.request_approval(
        requester,
        workspace.workspace_id,
        decision_id=decision.payload["decision_id"],
        reason="Start the synthetic approval sequence.",
    )
    assert service.request_approval(
        requester,
        workspace.workspace_id,
        decision_id=decision.payload["decision_id"],
        reason="Start the synthetic approval sequence.",
    ).event_id == approval.event_id

    barrier = Barrier(2)

    def approve_as(name):
        barrier.wait(timeout=10)
        return service.transition_approval(
            context(name),
            workspace.workspace_id,
            approval_id=approval.payload["approval_id"],
            target="APPROVED",
            reason=f"{name} attempts the current Finance stage.",
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        pending = [
            pool.submit(approve_as, "finance-a"),
            pool.submit(approve_as, "finance-a-2"),
        ]
    accepted = []
    denied = 0
    for future in pending:
        try:
            accepted.append(future.result())
        except PermissionError:
            denied += 1
    assert len(accepted) == 1
    assert denied == 1
    assert accepted[0].payload["approval"]["workflow_stage"] == "CIO"
    accepted_name = next(
        name
        for name in ("finance-a", "finance-a-2")
        if IDENTITY_IDS[name] == accepted[0].actor_id
    )
    assert service.transition_approval(
        context(accepted_name),
        workspace.workspace_id,
        approval_id=approval.payload["approval_id"],
        target="APPROVED",
        reason=f"{accepted_name} attempts the current Finance stage.",
    ).event_id == accepted[0].event_id

    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        unavailable_port = sock.getsockname()[1]
    unavailable = PostgresCustomerWorkflowRepository(
        (
            f"host=127.0.0.1 port={unavailable_port} dbname=postgres "
            f"user={postgres_cluster['admin_user']} connect_timeout=1 "
            "options='-c statement_timeout=5000'"
        ),
        key=Fernet.generate_key(),
    )
    with pytest.raises(CustomerWorkflowError, match="storage is unavailable"):
        unavailable.list_workspaces(requester)


def test_postgres_complete_encrypted_package_restores_workflow_and_globals(
    workflow, postgres_cluster, tmp_path, monkeypatch
):
    service, _, workflow_key, evidence_key = workflow
    requester, workspace, evidence, ask, decision, approval = _journey(workflow)
    for approver in ("finance-a", "cio-a", "executive-a"):
        service.transition_approval(
            context(approver),
            workspace.workspace_id,
            approval_id=approval.payload["approval_id"],
            target="APPROVED",
            reason=f"{approver} approved before local recovery testing.",
        )
    export = service.export_evidence(
        context("executive-a"),
        workspace.workspace_id,
        approval_id=approval.payload["approval_id"],
    )
    backup_password = uuid4().hex
    backup_user = "nexora_qualification_backup"
    admin = psycopg2.connect(postgres_cluster["admin_dsn"])
    try:
        with admin:
            with admin.cursor() as cursor:
                cursor.execute(
                    sql.SQL(
                        "CREATE ROLE {} LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE "
                        "BYPASSRLS PASSWORD {}"
                    ).format(sql.Identifier(backup_user), sql.Literal(backup_password))
                )
                cursor.execute(
                    sql.SQL("GRANT pg_read_all_data TO {}").format(
                        sql.Identifier(backup_user)
                    )
                )
    finally:
        admin.close()

    backup_connection = psycopg2.connect(
        host="127.0.0.1",
        port=postgres_cluster["port"],
        dbname="postgres",
        user=backup_user,
        password=backup_password,
    )
    try:
        with backup_connection.cursor() as cursor:
            with pytest.raises(psycopg2.errors.InsufficientPrivilege):
                cursor.execute(
                    "INSERT INTO public.organizations (id, name, status) "
                    "VALUES (%s, 'must not write', 'active')",
                    (str(uuid4()),),
                )
        backup_connection.rollback()
    finally:
        backup_connection.close()

    storage_root = tmp_path / "capture"
    for name in ("application", "evidence", "prospect"):
        (storage_root / name).mkdir(parents=True)
    encrypted_storage_evidence = Fernet(evidence_key).encrypt(CSV)
    (storage_root / "evidence" / "synthetic-evidence.enc").write_bytes(
        encrypted_storage_evidence
    )
    backup_key = Fernet.generate_key()
    backup_key_id = "synthetic-backup-key-v1"
    checkpoint = {
        "mode": "OPERATOR_QUIESCED_CAPTURE",
        "snapshot_id": "synthetic-complete-postgres-package",
        "database_snapshot_id": "synthetic-live-pg-dump",
        "file_snapshot_id": "synthetic-durable-storage-capture",
        "operator_ref": "synthetic-test-owner",
        "captured_at": datetime.now(timezone.utc).isoformat(),
    }
    migration_files = (POSTGRES_CONTRACT,)
    artifact = tmp_path / "complete-postgres-backup.fernet"
    monkeypatch.setenv("NEXORA_PG_DUMP_PATH", str(PG_BIN / "pg_dump.exe"))
    monkeypatch.setenv("NEXORA_PG_DUMPALL_PATH", str(PG_BIN / "pg_dumpall.exe"))
    monkeypatch.setenv("NEXORA_PG_RESTORE_PATH", str(PG_BIN / "pg_restore.exe"))
    monkeypatch.setenv("NEXORA_PSQL_PATH", str(PG_BIN / "psql.exe"))
    package_result = create_backup_package(
        DatabaseConfig(
            "127.0.0.1",
            str(postgres_cluster["port"]),
            "postgres",
            backup_user,
            backup_password,
        ),
        artifact,
        storage_root=storage_root,
        key=backup_key,
        key_id=backup_key_id,
        checkpoint=checkpoint,
        migration_files=migration_files,
        workflow_key_id="synthetic-workflow-key-v1",
        evidence_key_id="synthetic-evidence-key-v1",
    )
    manifest, package_files = verify_backup_package(
        artifact,
        key=backup_key,
        key_id=backup_key_id,
        migration_files=migration_files,
    )
    assert package_result["artifact_sha256"]
    assert manifest["database"]["role_passwords_included"] is False
    assert manifest["database"]["roles"]
    assert "database_globals.sql" in package_files
    assert package_files["evidence/synthetic-evidence.enc"] == encrypted_storage_evidence

    with tempfile.TemporaryDirectory(prefix="nexora-customer-pg-recovery-") as directory:
        root = Path(directory).resolve()
        data = root / "data"
        restored_storage = root / "storage"
        recovery_started = False
        recovery_admin_password = uuid4().hex
        recovery_app_password = uuid4().hex
        admin_password_file = root / "recovery-admin-password"
        admin_password_file.write_text(
            f"{recovery_admin_password}\n", encoding="utf-8"
        )
        try:
            _run_pg(
                "initdb.exe",
                "-D",
                data,
                "-U",
                "nexora_recovery_admin",
                "--auth-host=scram-sha-256",
                "--auth-local=scram-sha-256",
                "--pwfile",
                root / "recovery-admin-password",
                "--encoding=UTF8",
                "--no-locale",
            )
            admin_password_file.unlink()
            with socket.socket() as sock:
                sock.bind(("127.0.0.1", 0))
                recovery_port = sock.getsockname()[1]
            _run_pg(
                "pg_ctl.exe",
                "-D",
                data,
                "-l",
                root / "postgres.log",
                "-w",
                "start",
                "-o",
                f"-h 127.0.0.1 -p {recovery_port} -c max_connections=30",
                capture_output=False,
            )
            recovery_started = True
            recovery_dsn = make_dsn(
                host="127.0.0.1",
                port=recovery_port,
                dbname="postgres",
                user="nexora_recovery_admin",
                password=recovery_admin_password,
                connect_timeout=3,
                options="-c statement_timeout=60000",
            )
            with pytest.raises(psycopg2.OperationalError):
                psycopg2.connect(
                    make_dsn(
                        host="127.0.0.1",
                        port=recovery_port,
                        dbname="postgres",
                        user="nexora_recovery_admin",
                        password="invalid-synthetic-credential",
                        connect_timeout=3,
                    )
                )
            with pytest.raises(
                RecoveryPackageError, match="password authentication failed"
            ):
                restore_backup_package(
                    artifact,
                    DatabaseConfig(
                        "127.0.0.1",
                        str(recovery_port),
                        "postgres",
                        "nexora_recovery_admin",
                        "incorrect-synthetic-credential",
                    ),
                    target_database="recovered_customer_workflow",
                    storage_destination=root / "invalid-credential-storage",
                    key=backup_key,
                    key_id=backup_key_id,
                    migration_files=migration_files,
                )
            restore_result = restore_backup_package(
                artifact,
                DatabaseConfig(
                    "127.0.0.1",
                    str(recovery_port),
                    "postgres",
                    "nexora_recovery_admin",
                    recovery_admin_password,
                ),
                target_database="recovered_customer_workflow",
                storage_destination=restored_storage,
                key=backup_key,
                key_id=backup_key_id,
                migration_files=migration_files,
            )
            assert restore_result["status"] == "RESTORE_VERIFIED"
            with pytest.raises(
                RecoveryPackageError, match="restore target database already exists"
            ):
                restore_backup_package(
                    artifact,
                    DatabaseConfig(
                        "127.0.0.1",
                        str(recovery_port),
                        "postgres",
                        "nexora_recovery_admin",
                        recovery_admin_password,
                    ),
                    target_database="recovered_customer_workflow",
                    storage_destination=root / "duplicate-storage",
                    key=backup_key,
                    key_id=backup_key_id,
                    migration_files=migration_files,
                )
            with pytest.raises(psycopg2.OperationalError):
                psycopg2.connect(
                    make_dsn(
                        host="127.0.0.1",
                        port=recovery_port,
                        dbname="recovered_customer_workflow",
                        user="nxr_customer_workflow_app",
                        password="incorrect-synthetic-runtime-credential",
                        connect_timeout=3,
                    )
                )
            assert Fernet(evidence_key).decrypt(
                (restored_storage / "evidence" / "synthetic-evidence.enc").read_bytes()
            ) == CSV
            admin = psycopg2.connect(recovery_dsn)
            try:
                with admin:
                    with admin.cursor() as cursor:
                        cursor.execute(
                            sql.SQL("ALTER ROLE {} PASSWORD %s").format(
                                sql.Identifier("nxr_customer_workflow_app")
                            ),
                            (recovery_app_password,),
                        )
                        cursor.execute(
                            "SELECT system_identifier::text FROM pg_control_system()"
                        )
                        recovery_system_identifier = cursor.fetchone()[0]
            finally:
                admin.close()

            repository = PostgresCustomerWorkflowRepository(
                make_dsn(
                    host="127.0.0.1",
                    port=recovery_port,
                    dbname="recovered_customer_workflow",
                    user="nxr_customer_workflow_app",
                    password=recovery_app_password,
                    connect_timeout=2,
                ),
                key=workflow_key,
            )
            workflow_key_file = tmp_path / "recovery-workflow.key"
            evidence_key_file = tmp_path / "recovery-evidence.key"
            workflow_key_file.write_bytes(workflow_key)
            evidence_key_file.write_bytes(evidence_key)
            monkeypatch.setenv("NEXORA_RECOVERY_APP_DSN", repository.database)
            monkeypatch.setenv("NEXORA_RECOVERY_WORKFLOW_KEY_FILE", str(workflow_key_file))
            monkeypatch.setenv("NEXORA_RECOVERY_EVIDENCE_KEY_FILE", str(evidence_key_file))
            monkeypatch.setenv(
                "NEXORA_RECOVERY_EVIDENCE_ROOT", str(tmp_path / "unused-recovery-evidence-root")
            )
            monkeypatch.setenv("NEXORA_CUSTOMER_WORKFLOW_JWT_SECRET", JWT_SECRET)
            monkeypatch.setenv("NEXORA_CUSTOMER_WORKFLOW_JWT_ISSUER", JWT_ISSUER)
            for prefix, identity in (
                ("CUSTOMER_A", "customer-a"),
                ("CUSTOMER_B", "customer-b"),
            ):
                organization_id, _ = IDENTITIES[identity]
                monkeypatch.setenv(
                    f"NEXORA_RECOVERY_{prefix}_USER_ID", IDENTITY_IDS[identity]
                )
                monkeypatch.setenv(
                    f"NEXORA_RECOVERY_{prefix}_ORG_ID", organization_id
                )
                monkeypatch.setenv(
                    f"NEXORA_RECOVERY_{prefix}_EMAIL", f"{identity}@example.test"
                )
            post_restore = verify_recovered_workflow(
                workspace.workspace_id, evidence.event_id
            )
            assert post_restore["status"] == "CUSTOMER_WORKFLOW_RECOVERY_VERIFIED"
            assert post_restore["tenant_isolation_verified"] is True
            recovered = CustomerWorkflowService(
                repository,
                evidence_root=tmp_path / "unused-recovery-evidence-root",
                evidence_key=evidence_key,
            ).resume_workspace(requester, workspace.workspace_id)
            assert postgres_cluster["system_identifier"] != recovery_system_identifier
            assert [row["event_id"] for row in recovered["evidence"]] == [
                evidence.event_id
            ]
            assert [row["event_id"] for row in recovered["asks"]] == [ask.event_id]
            assert [row["event_id"] for row in recovered["decisions"]] == [
                decision.event_id
            ]
            assert len(recovered["approvals"]) == 4
            approval_history = [
                row["payload"]["history"]
                for row in recovered["approvals"]
                if row["event_type"] == "APPROVAL_TRANSITIONED"
            ]
            assert {entry["actor_role"] for entry in approval_history} == {
                "finance",
                "cio",
                "executive",
            }
            assert [row["event_id"] for row in recovered["exports"]] == [
                export.event_id
            ]
            assert (
                CustomerWorkflowService(
                    repository,
                    evidence_root=tmp_path / "unused-recovery-evidence-root",
                    evidence_key=evidence_key,
                ).load_evidence(requester, workspace.workspace_id, evidence.event_id)
                == CSV
            )
            wrong_workflow_repository = PostgresCustomerWorkflowRepository(
                make_dsn(
                    host="127.0.0.1",
                    port=recovery_port,
                    dbname="recovered_customer_workflow",
                    user="nxr_customer_workflow_app",
                    password=recovery_app_password,
                    connect_timeout=2,
                ),
                key=Fernet.generate_key(),
            )
            with pytest.raises(
                CustomerWorkflowError, match="customer workflow record failed integrity checks"
            ):
                CustomerWorkflowService(
                    wrong_workflow_repository,
                    evidence_root=tmp_path / "unused-recovery-evidence-root",
                    evidence_key=evidence_key,
                ).resume_workspace(requester, workspace.workspace_id)
            with pytest.raises(
                CustomerWorkflowError, match="encrypted customer evidence failed integrity checks"
            ):
                CustomerWorkflowService(
                    repository,
                    evidence_root=tmp_path / "unused-recovery-evidence-root",
                    evidence_key=Fernet.generate_key(),
                ).load_evidence(requester, workspace.workspace_id, evidence.event_id)
            assert CustomerWorkflowService(
                repository,
                evidence_root=tmp_path / "unused-recovery-evidence-root",
                evidence_key=evidence_key,
            ).list_workspaces(context("customer-b")) == ()
            with pytest.raises(PermissionError, match="not available in this tenant"):
                CustomerWorkflowService(
                    repository,
                    evidence_root=tmp_path / "unused-recovery-evidence-root",
                    evidence_key=evidence_key,
                ).resume_workspace(context("customer-b"), workspace.workspace_id)
        finally:
            if recovery_started:
                _run_pg(
                    "pg_ctl.exe", "-D", data, "-w", "stop", "-m", "fast"
                )

@pytest.fixture
def postgres17_target():
    image = os.getenv("NEXORA_V1_LOGICAL_PG17_IMAGE", "").strip()
    if not image:
        pytest.skip("set NEXORA_V1_LOGICAL_PG17_IMAGE to the local PostgreSQL 17 image")
    name = f"nexora-v1-pg17-logical-{uuid4().hex[:12]}"
    password = uuid4().hex
    started = subprocess.run(
        [
            "docker",
            "run",
            "--detach",
            "--rm",
            "--name",
            name,
            "--label",
            "nexora.qualification=v1-logical-pg17",
            "--env",
            f"POSTGRES_PASSWORD={password}",
            "--publish",
            "127.0.0.1::5432",
            image,
        ],
        capture_output=True,
        text=True,
        timeout=120,
    )
    if started.returncode:
        pytest.fail(f"isolated PostgreSQL 17 container did not start: {started.stderr[-2000:]}")
    container_id = started.stdout.strip()
    try:
        published = subprocess.run(
            ["docker", "port", container_id, "5432/tcp"],
            capture_output=True,
            text=True,
            timeout=15,
        )
        if published.returncode:
            pytest.fail(f"isolated PostgreSQL 17 port lookup failed: {published.stderr}")
        port = int(published.stdout.strip().rsplit(":", 1)[1])
        admin_dsn = (
            f"host=127.0.0.1 port={port} dbname=postgres user=postgres "
            f"password={password} connect_timeout=3"
        )
        connection = None
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            try:
                connection = psycopg2.connect(admin_dsn)
                break
            except psycopg2.OperationalError:
                time.sleep(1)
        if connection is None:
            pytest.fail("isolated PostgreSQL 17 did not become ready within 60 seconds")
        connection.close()
        yield {
            "admin_dsn": admin_dsn,
            "port": port,
            "container_id": container_id,
        }
    finally:
        stopped = subprocess.run(
            ["docker", "stop", "--time", "10", container_id],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if stopped.returncode and "No such container" not in stopped.stderr:
            pytest.fail(f"isolated PostgreSQL 17 container cleanup failed: {stopped.stderr}")


def _bootstrap_pg17_supabase_collision_target(
    postgres17_target, *, jwt_secret: str, jwt_issuer: str
) -> dict[str, str]:
    admin_dsn = postgres17_target["admin_dsn"]
    app_password = uuid4().hex
    preflight_password = uuid4().hex
    connection = psycopg2.connect(admin_dsn)
    with connection:
        with connection.cursor() as cursor:
            for role in (
                "anon",
                "authenticated",
                "authenticator",
                "supabase_admin",
                "supabase_auth_admin",
                "supabase_storage_admin",
            ):
                cursor.execute(
                    sql.SQL("CREATE ROLE {} NOLOGIN NOSUPERUSER NOBYPASSRLS").format(
                        sql.Identifier(role)
                    )
                )
            cursor.execute(
                "CREATE ROLE service_role NOLOGIN NOSUPERUSER BYPASSRLS"
            )
            cursor.execute(
                sql.SQL(
                    """
                    CREATE ROLE nxr_customer_workflow_app LOGIN
                        NOSUPERUSER NOCREATEDB NOCREATEROLE INHERIT NOBYPASSRLS
                        PASSWORD {}
                    """
                ).format(sql.Literal(app_password))
            )
            cursor.execute(
                sql.SQL(
                    """
                    CREATE ROLE nexora_test_preflight LOGIN
                        NOSUPERUSER NOCREATEDB NOCREATEROLE INHERIT BYPASSRLS
                        PASSWORD {}
                    """
                ).format(sql.Literal(preflight_password))
            )
            cursor.execute(
                """
                CREATE SCHEMA auth AUTHORIZATION supabase_auth_admin;
                CREATE TABLE auth.users (
                    id uuid PRIMARY KEY,
                    historical_marker text NOT NULL
                );
                ALTER TABLE auth.users OWNER TO supabase_auth_admin;
                INSERT INTO auth.users VALUES (
                    'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa', 'historical-auth-preserve'
                );
                CREATE SCHEMA data_fabric AUTHORIZATION supabase_admin;
                CREATE TABLE data_fabric.relationship_history (
                    relationship_id text PRIMARY KEY,
                    historical_marker text NOT NULL
                );
                ALTER TABLE data_fabric.relationship_history OWNER TO supabase_admin;
                INSERT INTO data_fabric.relationship_history
                    VALUES ('g07-sentinel', 'historical-g07-preserve');
                CREATE SCHEMA supabase_migrations;
                CREATE TABLE supabase_migrations.schema_migrations (
                    version text PRIMARY KEY
                );
                INSERT INTO supabase_migrations.schema_migrations
                    VALUES ('20260904042847');
                """
            )
            cursor.execute("CREATE SCHEMA extensions")
            cursor.execute("CREATE EXTENSION pgcrypto WITH SCHEMA extensions")
            cursor.execute(POSTGRES_CONTRACT.read_text(encoding="utf-8"))
            cursor.executemany(
                """
                INSERT INTO nexora_identity.memberships
                    (auth_user_id, org_id, tenant_id, organization_name,
                     workspace_id, role, status)
                VALUES (%s, %s, %s, %s, NULL, %s, 'active')
                """,
                [
                    (
                        IDENTITY_IDS[identity],
                        organization_id,
                        organization_id,
                        f"Synthetic {organization_id[-1]}",
                        role,
                    )
                    for identity, (organization_id, role) in IDENTITIES.items()
                ],
            )
            cursor.execute(
                """
                INSERT INTO nexora_customer_workflow.jwt_verification_settings
                    (singleton, signing_secret, issuer, verification_mode)
                VALUES (true, %s, %s, 'synthetic_hs256')
                """,
                (jwt_secret, jwt_issuer),
            )
            cursor.execute(
                "GRANT nxr_customer_workflow_runtime TO nxr_customer_workflow_app"
            )
            cursor.execute(
                """
                GRANT CONNECT ON DATABASE postgres
                    TO nxr_customer_workflow_app, nexora_test_preflight;
                GRANT USAGE ON SCHEMA public, nexora_customer_workflow,
                    nexora_identity
                    TO nexora_test_preflight;
                GRANT SELECT ON
                    nexora_customer_workflow.events,
                    nexora_customer_workflow.evidence_objects,
                    nexora_customer_workflow.approvals
                    TO nexora_test_preflight;
                GRANT SELECT ON nexora_identity.memberships
                    TO nexora_test_preflight;
                GRANT SELECT (singleton, issuer, verification_mode)
                    ON nexora_customer_workflow.jwt_verification_settings
                    TO nexora_test_preflight;
                """
            )
    connection.close()
    return {
        "runtime_dsn": (
            f"host=127.0.0.1 port={postgres17_target['port']} dbname=postgres "
            f"user=nxr_customer_workflow_app password={app_password} connect_timeout=3"
        ),
        "preflight_dsn": (
            f"host=127.0.0.1 port={postgres17_target['port']} dbname=postgres "
            f"user=nexora_test_preflight password={preflight_password} connect_timeout=3"
        ),
    }


def _pg17_protected_snapshot(admin_dsn: str) -> dict[str, object]:
    connection = psycopg2.connect(admin_dsn)
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT rolname, rolsuper, rolcreatedb, rolcreaterole, rolcanlogin,
                       rolinherit, rolbypassrls
                FROM pg_roles
                WHERE rolname NOT LIKE 'pg\\_%' ESCAPE '\\'
                ORDER BY rolname
                """
            )
            roles = cursor.fetchall()
            cursor.execute(
                """
                SELECT member.rolname, granted.rolname, membership.admin_option
                FROM pg_auth_members AS membership
                JOIN pg_roles AS member ON member.oid = membership.member
                JOIN pg_roles AS granted ON granted.oid = membership.roleid
                WHERE member.rolname NOT LIKE 'pg\\_%' ESCAPE '\\'
                ORDER BY member.rolname, granted.rolname
                """
            )
            memberships = cursor.fetchall()
            cursor.execute(
                """
                SELECT namespace.nspname, relation.relname,
                       pg_get_userbyid(relation.relowner), relation.relacl::text
                FROM pg_class AS relation
                JOIN pg_namespace AS namespace ON namespace.oid = relation.relnamespace
                WHERE namespace.nspname IN ('auth', 'data_fabric', 'supabase_migrations', 'public')
                  AND relation.relkind IN ('r', 'p', 'v', 'm', 'S')
                ORDER BY namespace.nspname, relation.relname
                """
            )
            objects = cursor.fetchall()
            cursor.execute("SELECT id::text, historical_marker FROM auth.users ORDER BY id")
            auth_rows = cursor.fetchall()
            cursor.execute(
                "SELECT relationship_id, historical_marker "
                "FROM data_fabric.relationship_history ORDER BY relationship_id"
            )
            g07_rows = cursor.fetchall()
            cursor.execute(
                "SELECT version FROM supabase_migrations.schema_migrations ORDER BY version"
            )
            migrations = cursor.fetchall()
            cursor.execute(
                """
                SELECT namespace.nspname, pg_get_userbyid(namespace.nspowner),
                       namespace.nspacl::text
                FROM pg_namespace AS namespace
                WHERE namespace.nspname IN (
                    'auth', 'data_fabric', 'supabase_migrations', 'public',
                    'extensions'
                )
                ORDER BY namespace.nspname
                """
            )
            schemas = cursor.fetchall()
            cursor.execute(
                """
                SELECT extension.extname, extension.extversion,
                       namespace.nspname, pg_get_userbyid(extension.extowner),
                       extension.extrelocatable
                FROM pg_extension AS extension
                JOIN pg_namespace AS namespace
                  ON namespace.oid = extension.extnamespace
                ORDER BY extension.extname
                """
            )
            extensions = cursor.fetchall()
            cursor.execute(
                """
                SELECT namespace.nspname,
                       pg_get_function_identity_arguments(procedure.oid),
                       pg_get_userbyid(procedure.proowner), procedure.proacl::text,
                       pg_get_functiondef(procedure.oid)
                FROM pg_extension AS extension
                JOIN pg_namespace AS namespace
                  ON namespace.oid = extension.extnamespace
                JOIN pg_proc AS procedure
                  ON procedure.pronamespace = namespace.oid
                JOIN pg_depend AS dependency
                  ON dependency.classid = 'pg_proc'::regclass
                 AND dependency.objid = procedure.oid
                 AND dependency.refclassid = 'pg_extension'::regclass
                 AND dependency.refobjid = extension.oid
                 AND dependency.deptype = 'e'
                WHERE extension.extname = 'pgcrypto'
                  AND procedure.proname = 'hmac'
                  AND procedure.proargtypes = '17 17 25'::oidvector
                """
            )
            extension_functions = [
                (
                    schema,
                    arguments,
                    owner,
                    acl,
                    hashlib.sha256(definition.encode("utf-8")).hexdigest(),
                )
                for schema, arguments, owner, acl, definition in cursor.fetchall()
            ]
            cursor.execute(
                """
                SELECT auth_user_id::text, org_id::text, tenant_id::text,
                       organization_name, workspace_id, role, status
                FROM nexora_identity.memberships
                ORDER BY auth_user_id, org_id
                """
            )
            identity_mappings = cursor.fetchall()
            cursor.execute("SELECT to_regclass('public.users') IS NOT NULL")
            public_users_exists = cursor.fetchone()[0]
        return {
            "roles": roles,
            "memberships": memberships,
            "objects": objects,
            "auth": auth_rows,
            "g07": g07_rows,
            "migrations": migrations,
            "schemas": schemas,
            "extensions": extensions,
            "extension_functions": extension_functions,
            "identity_mappings": identity_mappings,
            "public_users_exists": public_users_exists,
        }
    finally:
        connection.close()


def test_pg17_logical_recovery_isolated_from_supabase_objects(
    workflow, postgres_cluster, postgres17_target, tmp_path, monkeypatch
):
    service, _, workflow_key, evidence_key = workflow
    requester, workspace, evidence, ask, decision, approval = _journey(workflow)
    service.create_workspace(requester, name="Second synthetic recovery workspace")
    for approver in ("finance-a", "cio-a", "executive-a"):
        service.transition_approval(
            context(approver),
            workspace.workspace_id,
            approval_id=approval.payload["approval_id"],
            target="APPROVED",
            reason=f"{approver} approved the synthetic customer decision.",
        )
    export = service.export_evidence(
        context("executive-a"),
        workspace.workspace_id,
        approval_id=approval.payload["approval_id"],
    )

    backup_key = Fernet.generate_key()
    package = tmp_path / "synthetic-v1-workflow.nxr"
    key_ids = {
        "backup_key_id": "synthetic-backup-key-v1",
        "workflow_key_id": "synthetic-workflow-key-v1",
        "evidence_key_id": "synthetic-evidence-key-v1",
    }
    package_result = v1_workflow_recovery.create_package(
        source_dsn=postgres_cluster["admin_dsn"],
        destination=package,
        backup_key=backup_key,
        migration_file=POSTGRES_CONTRACT,
        **key_ids,
    )
    encrypted_package = package.read_bytes()
    assert CSV not in encrypted_package
    assert b"customer-costs.csv" not in encrypted_package
    assert package_result["event_count"] > 0
    assert package_result["evidence_count"] == 1
    assert package_result["approval_count"] == 1

    jwt_secret = secrets.token_urlsafe(32)
    jwt_issuer = "https://synthetic-restored-auth.example.test"
    target_credentials = _bootstrap_pg17_supabase_collision_target(
        postgres17_target, jwt_secret=jwt_secret, jwt_issuer=jwt_issuer
    )
    before = _pg17_protected_snapshot(postgres17_target["admin_dsn"])

    wrong_key = Fernet.generate_key()
    with pytest.raises(
        v1_workflow_recovery.WorkflowRecoveryError, match="backup key is wrong"
    ):
        v1_workflow_recovery.restore_package(
            package=package,
            backup_key=wrong_key,
            preflight_dsn=target_credentials["preflight_dsn"],
            runtime_dsn=target_credentials["runtime_dsn"],
            jwt_signing_secret=jwt_secret,
            jwt_issuer=jwt_issuer,
            target_jwt_key_id="synthetic-target-jwt-v1",
            migration_file=POSTGRES_CONTRACT,
            **key_ids,
        )

    mismatched_key_ids = dict(key_ids)
    mismatched_key_ids["evidence_key_id"] = "unavailable-evidence-key-v2"
    with pytest.raises(
        v1_workflow_recovery.WorkflowRecoveryError,
        match="encryption-key IDs do not match",
    ):
        v1_workflow_recovery.restore_package(
            package=package,
            backup_key=backup_key,
            preflight_dsn=target_credentials["preflight_dsn"],
            runtime_dsn=target_credentials["runtime_dsn"],
            jwt_signing_secret=jwt_secret,
            jwt_issuer=jwt_issuer,
            target_jwt_key_id="synthetic-target-jwt-v1",
            migration_file=POSTGRES_CONTRACT,
            **mismatched_key_ids,
        )

    incomplete = tmp_path / "interrupted-backup.nxr"
    incomplete.write_bytes(encrypted_package[: len(encrypted_package) // 2])
    with pytest.raises(
        v1_workflow_recovery.WorkflowRecoveryError,
        match="backup key is wrong or encrypted package integrity failed",
    ):
        v1_workflow_recovery.restore_package(
            package=incomplete,
            backup_key=backup_key,
            preflight_dsn=target_credentials["preflight_dsn"],
            runtime_dsn=target_credentials["runtime_dsn"],
            jwt_signing_secret=jwt_secret,
            jwt_issuer=jwt_issuer,
            target_jwt_key_id="synthetic-target-jwt-v1",
            migration_file=POSTGRES_CONTRACT,
            **key_ids,
        )

    changed_migration = tmp_path / "incompatible-workflow.sql"
    changed_migration.write_bytes(POSTGRES_CONTRACT.read_bytes() + b"\n-- incompatible\n")
    with pytest.raises(
        v1_workflow_recovery.WorkflowRecoveryError,
        match="incompatible workflow migration",
    ):
        v1_workflow_recovery.restore_package(
            package=package,
            backup_key=backup_key,
            preflight_dsn=target_credentials["preflight_dsn"],
            runtime_dsn=target_credentials["runtime_dsn"],
            jwt_signing_secret=jwt_secret,
            jwt_issuer=jwt_issuer,
            target_jwt_key_id="synthetic-target-jwt-v1",
            migration_file=changed_migration,
            **key_ids,
        )

    admin = psycopg2.connect(postgres17_target["admin_dsn"])
    with admin:
        with admin.cursor() as cursor:
            cursor.execute(
                "DROP POLICY events_owner_scope "
                "ON nexora_customer_workflow.events"
            )
    admin.close()
    with pytest.raises(
        v1_workflow_recovery.WorkflowRecoveryError,
        match="required tenant RLS policies are missing",
    ):
        v1_workflow_recovery.restore_package(
            package=package,
            backup_key=backup_key,
            preflight_dsn=target_credentials["preflight_dsn"],
            runtime_dsn=target_credentials["runtime_dsn"],
            jwt_signing_secret=jwt_secret,
            jwt_issuer=jwt_issuer,
            target_jwt_key_id="synthetic-target-jwt-v1",
            migration_file=POSTGRES_CONTRACT,
            **key_ids,
        )
    admin = psycopg2.connect(postgres17_target["admin_dsn"])
    with admin:
        with admin.cursor() as cursor:
            cursor.execute(POSTGRES_CONTRACT.read_text(encoding="utf-8"))
    admin.close()

    with pytest.raises(
        v1_workflow_recovery.WorkflowRecoveryError,
        match="target preflight or transactional restore failed",
    ):
        v1_workflow_recovery.restore_package(
            package=package,
            backup_key=backup_key,
            preflight_dsn=target_credentials["preflight_dsn"],
            runtime_dsn="host=127.0.0.1 port=1 dbname=missing connect_timeout=1",
            jwt_signing_secret=jwt_secret,
            jwt_issuer=jwt_issuer,
            target_jwt_key_id="synthetic-target-jwt-v1",
            migration_file=POSTGRES_CONTRACT,
            **key_ids,
        )

    wrong_target_jwt = secrets.token_urlsafe(32)
    with pytest.raises(
        v1_workflow_recovery.WorkflowRecoveryError,
        match="target JWT or actor profile failed authorization",
    ):
        v1_workflow_recovery.restore_package(
            package=package,
            backup_key=backup_key,
            preflight_dsn=target_credentials["preflight_dsn"],
            runtime_dsn=target_credentials["runtime_dsn"],
            jwt_signing_secret=wrong_target_jwt,
            jwt_issuer=jwt_issuer,
            target_jwt_key_id="synthetic-target-jwt-v1",
            migration_file=POSTGRES_CONTRACT,
            **key_ids,
        )

    original_insert_event = v1_workflow_recovery._insert_event
    inserted = 0

    def interrupt_after_one(cursor, event):
        nonlocal inserted
        original_insert_event(cursor, event)
        inserted += 1
        if inserted == 1:
            raise psycopg2.OperationalError("simulated interrupted restore")

    with monkeypatch.context() as patch:
        patch.setattr(v1_workflow_recovery, "_insert_event", interrupt_after_one)
        with pytest.raises(
            v1_workflow_recovery.WorkflowRecoveryError,
            match="no partial commit",
        ):
            v1_workflow_recovery.restore_package(
                package=package,
                backup_key=backup_key,
                preflight_dsn=target_credentials["preflight_dsn"],
                runtime_dsn=target_credentials["runtime_dsn"],
                jwt_signing_secret=jwt_secret,
                jwt_issuer=jwt_issuer,
                target_jwt_key_id="synthetic-target-jwt-v1",
                migration_file=POSTGRES_CONTRACT,
                **key_ids,
            )
    assert _pg17_protected_snapshot(postgres17_target["admin_dsn"]) == before
    with psycopg2.connect(target_credentials["preflight_dsn"]) as check:
        with check.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    (SELECT count(*) FROM nexora_customer_workflow.events),
                    (SELECT count(*) FROM nexora_customer_workflow.evidence_objects),
                    (SELECT count(*) FROM nexora_customer_workflow.approvals)
                """
            )
            assert cursor.fetchone() == (0, 0, 0)

    restored = v1_workflow_recovery.restore_package(
        package=package,
        backup_key=backup_key,
        preflight_dsn=target_credentials["preflight_dsn"],
        runtime_dsn=target_credentials["runtime_dsn"],
        jwt_signing_secret=jwt_secret,
        jwt_issuer=jwt_issuer,
        target_jwt_key_id="synthetic-target-jwt-v1",
        migration_file=POSTGRES_CONTRACT,
        **key_ids,
    )
    assert restored["target_postgres_major"] == 17
    assert restored["event_count"] == package_result["event_count"]
    assert restored["evidence_count"] == 1
    assert restored["approval_count"] == 1

    with pytest.raises(
        v1_workflow_recovery.WorkflowRecoveryError,
        match="not empty; refusing overwrite",
    ):
        v1_workflow_recovery.restore_package(
            package=package,
            backup_key=backup_key,
            preflight_dsn=target_credentials["preflight_dsn"],
            runtime_dsn=target_credentials["runtime_dsn"],
            jwt_signing_secret=jwt_secret,
            jwt_issuer=jwt_issuer,
            target_jwt_key_id="synthetic-target-jwt-v1",
            migration_file=POSTGRES_CONTRACT,
            **key_ids,
        )

    target_repository = PostgresCustomerWorkflowRepository(
        target_credentials["runtime_dsn"],
        key=workflow_key,
    )
    target_service = CustomerWorkflowService(
        target_repository,
        evidence_root=tmp_path / "unused-restored-evidence",
        evidence_key=evidence_key,
    )

    def restored_context(name: str) -> AuthenticatedTenantContext:
        original = context(name)
        return replace(
            original,
            auth_access_token=_access_token(
                original.user_id,
                secret=jwt_secret,
                issuer=jwt_issuer,
            ),
        )

    customer_a = restored_context("customer-a")
    resumed = target_service.resume_workspace(customer_a, workspace.workspace_id)
    assert resumed["workspace"]["event_id"] == workspace.event_id
    assert resumed["evidence"][0]["event_id"] == evidence.event_id
    assert resumed["evidence"][0]["payload"]["validation_status"] == "PASS"
    assert resumed["asks"][0]["event_id"] == ask.event_id
    assert resumed["asks"][0]["payload"]["state"] == "GROUNDED"
    assert resumed["decisions"][0]["event_id"] == decision.event_id
    assert resumed["approvals"][0]["event_id"] == approval.event_id
    assert len(resumed["approvals"]) == 4
    assert resumed["approvals"][-1]["payload"]["approval"]["state"] == "APPROVED"
    assert resumed["exports"][0]["event_id"] == export.event_id
    assert resumed["exports"][0]["payload"] == export.payload
    export_package = resumed["exports"][0]["payload"]["package"]
    assert export_package["schema"] == "nexora.customer-evidence-export.v1"
    assert export_package["evidence"]["record_id"] == evidence.event_id
    assert export_package["decision"]["record_id"] == decision.event_id
    assert export_package["approval"]["state"] == "APPROVED"
    assert len(export_package["approval"]["history"]) == 3
    assert target_service.load_evidence(
        customer_a, workspace.workspace_id, evidence.event_id
    ) == CSV
    wrong_workflow_repository = PostgresCustomerWorkflowRepository(
        target_credentials["runtime_dsn"],
        key=Fernet.generate_key(),
    )
    wrong_workflow_service = CustomerWorkflowService(
        wrong_workflow_repository,
        evidence_root=tmp_path / "unused-wrong-workflow-key",
        evidence_key=evidence_key,
    )
    with pytest.raises(
        CustomerWorkflowError, match="customer workflow record failed integrity checks"
    ):
        wrong_workflow_service.resume_workspace(customer_a, workspace.workspace_id)
    wrong_evidence_service = CustomerWorkflowService(
        target_repository,
        evidence_root=tmp_path / "unused-wrong-evidence-key",
        evidence_key=Fernet.generate_key(),
    )
    with pytest.raises(
        CustomerWorkflowError, match="encrypted customer evidence failed integrity checks"
    ):
        wrong_evidence_service.load_evidence(
            customer_a, workspace.workspace_id, evidence.event_id
        )

    customer_b = restored_context("customer-b")
    assert target_service.list_workspaces(customer_b) == ()
    with pytest.raises(PermissionError):
        target_service.resume_workspace(customer_b, workspace.workspace_id)
    after = _pg17_protected_snapshot(postgres17_target["admin_dsn"])
    assert after == before

