"""Apply the customer-workflow PostgreSQL contract and provision its runtime login."""

from __future__ import annotations

import os
from pathlib import Path

import psycopg2
from psycopg2 import sql

from services.customer_workflow_service import _configured_secret

MIGRATION = (
    Path(__file__).resolve().parents[1]
    / "database"
    / "contracts"
    / "v1_customer_workflow"
    / "001_customer_workflow_postgres.sql"
)


def main() -> None:
    admin_dsn = _configured_secret("NEXORA_CUSTOMER_WORKFLOW_MIGRATION_DSN")
    runtime_password = _configured_secret("NEXORA_CUSTOMER_WORKFLOW_DB_PASSWORD")
    jwt_secret = _configured_secret("NEXORA_CUSTOMER_WORKFLOW_JWT_SECRET")
    jwt_issuer = _configured_secret("NEXORA_CUSTOMER_WORKFLOW_JWT_ISSUER")
    environment = os.getenv("ENVIRONMENT", "").strip().lower()
    jwt_mode = os.getenv("NEXORA_CUSTOMER_WORKFLOW_JWT_MODE", "").strip()
    if jwt_mode != "synthetic_hs256" or environment not in {
        "local",
        "test",
        "qualification",
    }:
        raise RuntimeError(
            "production JWT verification is unqualified; only synthetic local/test "
            "provisioning is enabled"
        )
    if not admin_dsn:
        raise RuntimeError(
            "NEXORA_CUSTOMER_WORKFLOW_MIGRATION_DSN must be provisioned outside the repository"
        )
    if not runtime_password:
        raise RuntimeError(
            "NEXORA_CUSTOMER_WORKFLOW_DB_PASSWORD must be provisioned outside the repository"
        )
    if len(jwt_secret) < 32:
        raise RuntimeError(
            "synthetic JWT signing key must contain at least 32 characters"
        )
    if not jwt_issuer:
        raise RuntimeError(
            "NEXORA_CUSTOMER_WORKFLOW_JWT_ISSUER must be provisioned outside the repository"
        )

    connection = psycopg2.connect(admin_dsn, connect_timeout=5)
    try:
        with connection:
            with connection.cursor() as cursor:
                cursor.execute(MIGRATION.read_text(encoding="utf-8"))
                cursor.execute(
                    """
                    INSERT INTO nexora_customer_workflow.jwt_verification_settings
                        (singleton, signing_secret, issuer, verification_mode)
                    VALUES (true, %s, %s, %s)
                    ON CONFLICT (singleton) DO NOTHING
                    """,
                    (jwt_secret, jwt_issuer, jwt_mode),
                )
                cursor.execute(
                    """
                    SELECT signing_secret, issuer, verification_mode
                    FROM nexora_customer_workflow.jwt_verification_settings
                    WHERE singleton
                    """
                )
                if cursor.fetchone() != (jwt_secret, jwt_issuer, jwt_mode):
                    raise RuntimeError(
                        "existing JWT verification settings differ; refusing key rotation"
                    )
                cursor.execute(
                    """
                    SELECT rolname FROM pg_roles
                    WHERE rolname = 'nxr_customer_workflow_app'
                    """
                )
                exists = cursor.fetchone() is not None
                if exists:
                    cursor.execute(
                        sql.SQL(
                            """
                            ALTER ROLE {} WITH LOGIN NOSUPERUSER NOCREATEDB
                                NOCREATEROLE INHERIT NOBYPASSRLS PASSWORD {}
                            """
                        ).format(
                            sql.Identifier("nxr_customer_workflow_app"),
                            sql.Literal(runtime_password),
                        )
                    )
                else:
                    cursor.execute(
                        sql.SQL(
                            """
                            CREATE ROLE {} WITH LOGIN NOSUPERUSER NOCREATEDB
                                NOCREATEROLE INHERIT NOBYPASSRLS PASSWORD {}
                            """
                        ).format(
                            sql.Identifier("nxr_customer_workflow_app"),
                            sql.Literal(runtime_password),
                        )
                    )
                cursor.execute(
                    "GRANT nxr_customer_workflow_runtime TO nxr_customer_workflow_app"
                )
                cursor.execute(
                    """
                    SELECT rolcanlogin, rolsuper, rolcreatedb, rolcreaterole,
                           rolbypassrls
                    FROM pg_roles WHERE rolname = 'nxr_customer_workflow_app'
                    """
                )
                role_flags = cursor.fetchone()
                if role_flags != (True, False, False, False, False):
                    raise RuntimeError("customer workflow database role is not least-privilege")
                cursor.execute(
                    """
                    SELECT c.relname, c.relrowsecurity, c.relforcerowsecurity
                    FROM pg_class AS c
                    JOIN pg_namespace AS n ON n.oid = c.relnamespace
                    WHERE n.nspname = 'nexora_customer_workflow'
                      AND c.relname IN ('events', 'evidence_objects', 'approvals')
                    ORDER BY c.relname
                    """
                )
                rls = cursor.fetchall()
                if len(rls) != 3 or any(not row[1] or not row[2] for row in rls):
                    raise RuntimeError("customer workflow RLS is not enabled and forced")
                cursor.execute(
                    """
                    SELECT has_table_privilege(
                        'nxr_customer_workflow_app',
                        'nexora_customer_workflow.jwt_verification_settings',
                        'SELECT'
                    )
                    """
                )
                if cursor.fetchone() != (False,):
                    raise RuntimeError("runtime database role can read JWT verification settings")
                for table in (
                    "nexora_customer_workflow.events",
                    "nexora_customer_workflow.evidence_objects",
                    "nexora_customer_workflow.approvals",
                ):
                    cursor.execute(
                        "SELECT has_table_privilege(%s, %s, 'UPDATE')",
                        ("nxr_customer_workflow_app", table),
                    )
                    if cursor.fetchone() != (False,):
                        raise RuntimeError(
                            f"runtime database role can update protected table {table}"
                        )
                cursor.execute(
                    """
                    SELECT pg_has_role(
                        'nxr_customer_workflow_app',
                        'nxr_customer_workflow_owner',
                        'MEMBER'
                    )
                    """
                )
                if cursor.fetchone() != (False,):
                    raise RuntimeError("runtime database role can assume the workflow owner role")
                cursor.execute(
                    """
                    SELECT rolcanlogin, rolsuper, rolbypassrls
                    FROM pg_roles WHERE rolname = 'nxr_customer_workflow_owner'
                    """
                )
                if cursor.fetchone() != (False, False, False):
                    raise RuntimeError("workflow security-definer owner is over-privileged")
                cursor.execute(
                    """
                    SELECT procedure.proname, owner.rolname, procedure.prosecdef,
                           procedure.proconfig
                    FROM pg_proc AS procedure
                    JOIN pg_namespace AS namespace ON namespace.oid = procedure.pronamespace
                    JOIN pg_roles AS owner ON owner.oid = procedure.proowner
                    WHERE namespace.nspname = 'nexora_customer_workflow'
                      AND procedure.proname IN (
                          'verified_subject', 'verified_scope', 'enforce_event_contract'
                      )
                    ORDER BY procedure.proname
                    """
                )
                functions = cursor.fetchall()
                if len(functions) != 3 or any(
                    function[1] != "nxr_customer_workflow_owner"
                    or not function[2]
                    or "search_path=pg_catalog" not in (function[3] or ())
                    for function in functions
                ):
                    raise RuntimeError(
                        "customer workflow security-definer functions are not safely scoped"
                    )
                cursor.execute(
                    """
                    SELECT
                        has_function_privilege(
                            'anon',
                            'nexora_customer_workflow.verified_scope()', 'EXECUTE'
                        ),
                        has_function_privilege(
                            'authenticated',
                            'nexora_customer_workflow.verified_scope()', 'EXECUTE'
                        ),
                        has_function_privilege(
                            'service_role',
                            'nexora_customer_workflow.verified_scope()', 'EXECUTE'
                        ),
                        has_function_privilege(
                            'nxr_customer_workflow_app',
                            'nexora_customer_workflow.verified_scope()', 'EXECUTE'
                        )
                    """
                )
                if cursor.fetchone() != (False, False, False, True):
                    raise RuntimeError(
                        "customer workflow authorization function grants are not restricted"
                    )
    finally:
        connection.close()

    print("Customer-workflow PostgreSQL migration applied.")
    print("Runtime login provisioned as NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS.")


if __name__ == "__main__":
    main()
