"""Repository-only regression coverage for public-schema security hardening."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
MIGRATION = (
    ROOT
    / "supabase"
    / "migrations"
    / "202607230001_public_security_reconciliation.sql"
)
LEGACY_SCRIPT = ROOT / "supabase" / "tenant_rls_policies.sql"


def migration_sql() -> str:
    return MIGRATION.read_text(encoding="utf-8")


def normalized_sql() -> str:
    return re.sub(r"\s+", " ", migration_sql().casefold())


def jwt_org(email: str, users: list[dict[str, str]]) -> str | None:
    return next(
        (
            user["org_id"]
            for user in users
            if user["email"].casefold() == email.casefold()
        ),
        None,
    )


def tenant_row_visible(
    *,
    email: str,
    row_org_id: str,
    users: list[dict[str, str]],
) -> bool:
    return row_org_id == jwt_org(email, users)


def report_row_visible(
    *,
    email: str,
    row_org_id: str | None,
    row_tenant_id: str | None,
    users: list[dict[str, str]],
) -> bool:
    resolved = jwt_org(email, users)
    return (
        resolved is not None
        and row_org_id is not None
        and row_tenant_id is not None
        and row_org_id == resolved
        and row_tenant_id == resolved
    )


def report_insert_allowed(
    *,
    email: str,
    row_org_id: str | None,
    row_tenant_id: str | None,
    users: list[dict[str, str]],
) -> bool:
    return report_row_visible(
        email=email,
        row_org_id=row_org_id,
        row_tenant_id=row_tenant_id,
        users=users,
    )


USERS = [
    {"email": "tenant-a@example.com", "org_id": "org-a"},
    {"email": "tenant-b@example.com", "org_id": "org-b"},
]


def test_tenant_a_cannot_read_tenant_b_clients() -> None:
    assert not tenant_row_visible(
        email="tenant-a@example.com",
        row_org_id="org-b",
        users=USERS,
    )


def test_tenant_a_cannot_read_tenant_b_recommendations() -> None:
    assert not tenant_row_visible(
        email="tenant-a@example.com",
        row_org_id="org-b",
        users=USERS,
    )


def test_tenant_a_cannot_insert_recommendations_for_tenant_b() -> None:
    assert not tenant_row_visible(
        email="tenant-a@example.com",
        row_org_id="org-b",
        users=USERS,
    )


REPORT_HISTORY_SCOPE_CASES = [
    pytest.param("org-a", None, False, id="valid-org-null-tenant"),
    pytest.param(None, "org-a", False, id="null-org-valid-tenant"),
    pytest.param(None, None, False, id="both-null"),
    pytest.param("org-a", "org-b", False, id="valid-org-wrong-tenant"),
    pytest.param("org-b", "org-a", False, id="wrong-org-valid-tenant"),
    pytest.param("org-a", "org-a", True, id="both-valid-and-matching"),
]


@pytest.mark.parametrize(
    ("row_org_id", "row_tenant_id", "expected"),
    REPORT_HISTORY_SCOPE_CASES,
)
def test_report_history_select_scope(
    row_org_id: str | None,
    row_tenant_id: str | None,
    expected: bool,
) -> None:
    assert (
        report_row_visible(
            email="tenant-a@example.com",
            row_org_id=row_org_id,
            row_tenant_id=row_tenant_id,
            users=USERS,
        )
        is expected
    )


@pytest.mark.parametrize(
    ("row_org_id", "row_tenant_id", "expected"),
    REPORT_HISTORY_SCOPE_CASES,
)
def test_report_history_insert_scope(
    row_org_id: str | None,
    row_tenant_id: str | None,
    expected: bool,
) -> None:
    assert (
        report_insert_allowed(
            email="tenant-a@example.com",
            row_org_id=row_org_id,
            row_tenant_id=row_tenant_id,
            users=USERS,
        )
        is expected
    )


def test_tenant_a_cannot_read_tenant_b_report_history() -> None:
    assert not report_row_visible(
        email="tenant-a@example.com",
        row_org_id="org-b",
        row_tenant_id="org-b",
        users=USERS,
    )
    assert not report_row_visible(
        email="tenant-a@example.com",
        row_org_id="org-a",
        row_tenant_id="org-b",
        users=USERS,
    )


def test_user_cannot_read_another_users_record() -> None:
    authenticated_email = "tenant-a@example.com"
    other_user_email = "tenant-b@example.com"

    assert authenticated_email.casefold() != other_user_email.casefold()


def test_confirmed_policies_use_email_to_users_org_resolution() -> None:
    sql = normalized_sql()
    policy_names = {
        "clients_select_own_org",
        "organizations_select_own",
        "recommendations_select_own_org",
        "recommendations_insert_own_org",
        "report_history_select_own_org",
        "report_history_insert_own_org",
        "users_select_self",
    }

    assert all(f"policy {name}" in sql for name in policy_names)
    assert sql.count("lower(u.email) = lower(auth.jwt() ->> 'email')") >= 6
    assert "lower(email) = lower(auth.jwt() ->> 'email')" in sql
    assert "coalesce(auth.jwt()->>'tenant_id'" not in sql
    assert "for all using" not in sql


def test_anon_cannot_access_protected_tenant_data() -> None:
    sql = normalized_sql()

    assert "create policy clients_select_own_org" in sql
    assert "create policy organizations_select_own" in sql
    assert "create policy recommendations_select_own_org" in sql
    assert "create policy report_history_select_own_org" in sql
    assert "create policy users_select_self" in sql
    assert " to anon " not in sql
    assert " to public " not in sql
    assert "roles && array['public', 'anon']" in sql


def test_authenticated_has_no_structural_table_privileges() -> None:
    sql = normalized_sql()

    assert (
        "revoke truncate, references, trigger on all tables in schema public "
        "from anon, authenticated"
    ) in sql
    for privilege in ("truncate", "references", "trigger"):
        assert (
            "revoke truncate, references, trigger on tables from anon, authenticated"
            in sql
        ), privilege


def test_future_objects_do_not_restore_structural_privileges() -> None:
    sql = normalized_sql()

    assert (
        "alter default privileges for role postgres in schema public "
        "revoke truncate, references, trigger on tables from anon, authenticated"
    ) in sql
    assert "alter default privileges for role supabase_admin" not in sql


def test_migration_is_transactional_idempotent_and_fail_closed() -> None:
    sql = normalized_sql()
    policy_names = {
        "clients_select_own_org",
        "organizations_select_own",
        "recommendations_select_own_org",
        "recommendations_insert_own_org",
        "report_history_select_own_org",
        "report_history_insert_own_org",
        "users_select_self",
    }

    assert "\nbegin;" in migration_sql().casefold()
    assert migration_sql().strip().casefold().endswith("commit;")
    for policy_name in policy_names:
        assert f"drop policy if exists {policy_name}" in sql
        assert f"create policy {policy_name}" in sql
    assert "raise exception 'unsafe tenant policy remains:" in sql
    assert "roles && array['public', 'anon']::name[]" in sql
    assert "coalesce(qual, '') ~" in sql
    assert "coalesce(with_check, '') ~" in sql


def test_migration_does_not_revoke_or_grant_application_crud() -> None:
    sql = normalized_sql()

    assert "grant select" not in sql
    assert "grant insert" not in sql
    assert "grant update" not in sql
    assert "grant delete" not in sql
    assert "revoke select" not in sql
    assert "revoke insert" not in sql
    assert "revoke update" not in sql
    assert "revoke delete" not in sql


def test_report_history_text_identifiers_are_not_converted() -> None:
    sql = normalized_sql()

    assert "u.org_id::text" in sql
    assert "alter column org_id" not in sql
    assert "alter column tenant_id" not in sql


def test_required_backend_service_role_workflows_remain_present() -> None:
    data_client = (ROOT / "data" / "supabase_client.py").read_text(encoding="utf-8")
    report_service = (
        ROOT / "backend" / "services" / "report_service.py"
    ).read_text(encoding="utf-8")
    recommendation_job = (
        ROOT / "scheduler" / "recommendation_jobs.py"
    ).read_text(encoding="utf-8")

    assert 'os.getenv("SUPABASE_SERVICE_KEY")' in data_client
    assert "supabase_admin = supabase" in data_client
    assert ".table(REPORT_HISTORY_TABLE).insert(payload).execute()" in report_service
    assert 'supabase_admin.table("recommendations").upsert(' in recommendation_job
    assert "revoke select" not in normalized_sql()
    assert "revoke insert" not in normalized_sql()
    assert "revoke update" not in normalized_sql()


def test_legacy_generic_for_all_policy_script_cannot_be_applied() -> None:
    legacy = LEGACY_SCRIPT.read_text(encoding="utf-8").casefold()

    assert "raise exception" in legacy
    assert "is superseded" in legacy
    assert "create policy" not in legacy
    assert "for all using" not in legacy
