from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import pytest

from scripts import provision_production_tenant as cli
from services.production_tenant_provisioning_service import (
    AUTH_PAGE_SIZE,
    DEFAULT_ORGANIZATION_ID,
    DEMO_ORGANIZATION_ID,
    INITIAL_ADMIN_ROLE,
    ProductionTenantProvisioningService,
    ProvisioningInputError,
    find_auth_user_by_email,
    validate_request,
)

ORG_ID = "12345678-1234-4234-8234-123456789abc"
REQUEST_ID = "CHANGE-PO2-001"
ORG_NAME = "Northwind Retail"
EMAIL = "admin@example.com"
AUTH_USER_ID = "11111111-1111-4111-8111-111111111111"
ROOT = Path(__file__).resolve().parents[2]
LEGACY_AUTH_TRIGGER_MIGRATION = (
    ROOT / "supabase/migrations/202610090001_retire_legacy_auth_user_trigger.sql"
)
AUTH_UID_MIGRATION = (
    ROOT / "supabase/migrations/202610110001_bind_user_profiles_to_auth_uid.sql"
)


@dataclass
class FakeUser:
    email: str
    id: str = AUTH_USER_ID


class FakeAuthAdmin:
    def __init__(self, pages=None, events=None, invite_error=None, invite_email=None):
        self.pages = pages or {}
        self.events = events if events is not None else []
        self.invite_error = invite_error
        self.invite_email = invite_email or EMAIL

    def list_users(self, *, page, per_page):
        self.events.append(("auth_list", page, per_page))
        return self.pages.get(page, [])

    def invite_user_by_email(self, email):
        self.events.append(("auth_invite", email))
        if self.invite_error:
            raise self.invite_error
        user = FakeUser(self.invite_email)
        self.pages.setdefault(1, []).append(user)
        return type("InviteResponse", (), {"user": user})()


class FakeOrganizations:
    def __init__(self, rows=None, events=None, create_error=None):
        self.rows = dict(rows or {})
        self.events = events if events is not None else []
        self.create_error = create_error

    def get_by_id(self, organization_id):
        self.events.append(("organization_get", organization_id))
        return self.rows.get(organization_id)

    def create(self, payload):
        self.events.append(("organization_create", dict(payload)))
        if self.create_error:
            raise self.create_error
        self.rows[payload["id"]] = dict(payload)


class FakeProfiles:
    def __init__(self, rows=None, events=None, create_error=None):
        self.rows = dict(rows or {})
        self.events = events if events is not None else []
        self.create_error = create_error

    def get_by_email(self, email):
        self.events.append(("profile_get", email))
        return self.rows.get(email)

    def create(self, payload):
        self.events.append(("profile_create", dict(payload)))
        if self.create_error:
            raise self.create_error
        self.rows[payload["email"]] = {"id": "profile-generated-id", **payload}

    def bind_auth_user(self, email, auth_user_id):
        self.events.append(("profile_bind", email, auth_user_id))
        self.rows[email]["auth_user_id"] = auth_user_id


def request(**overrides):
    return validate_request(
        overrides.get("request_id", REQUEST_ID),
        overrides.get("organization_id", ORG_ID),
        overrides.get("organization_name", ORG_NAME),
        overrides.get("admin_email", EMAIL),
    )


def service(*, organizations=None, profiles=None, auth=None, events=None):
    events = events if events is not None else []
    return ProductionTenantProvisioningService(
        organizations or FakeOrganizations(events=events),
        profiles or FakeProfiles(events=events),
        auth or FakeAuthAdmin(events=events),
        clock=lambda: datetime(2026, 10, 3, tzinfo=timezone.utc),
    )


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("request_id", "", "request_id"),
        ("request_id", "bad id", "request_id"),
        ("organization_id", "default-org", "default organization"),
        ("organization_id", "not-a-uuid", "must be a UUID"),
        ("organization_id", DEMO_ORGANIZATION_ID, "synthetic demo"),
        ("organization_id", DEFAULT_ORGANIZATION_ID, "default organization"),
        ("organization_name", " ", "organization_name"),
        ("organization_name", "x", "organization_name"),
        ("admin_email", "not-email", "admin_email"),
    ],
)
def test_validation_rejects_invalid_inputs(field, value, message):
    with pytest.raises(ProvisioningInputError, match=message):
        request(**{field: value})


def test_valid_request_canonicalizes_identity_and_fixes_role():
    result = request(organization_id=ORG_ID.upper(), admin_email=" Admin@Example.com ")

    assert result.organization_id == ORG_ID
    assert result.admin_email == EMAIL
    assert result.role == INITIAL_ADMIN_ROLE


def test_service_rejects_a_manually_overridden_admin_role():
    invalid_request = request()
    invalid_request = type(invalid_request)(
        invalid_request.request_id,
        invalid_request.organization_id,
        invalid_request.organization_name,
        invalid_request.admin_email,
        role="super_admin",
    )

    with pytest.raises(ProvisioningInputError, match="role is fixed"):
        service().provision(invalid_request)


def test_auth_lookup_stops_on_first_page_match_and_uses_bounded_pages():
    user = FakeUser(EMAIL)
    auth = FakeAuthAdmin({1: [FakeUser("other@example.com"), user]})

    assert find_auth_user_by_email(auth, EMAIL) is user
    assert len(auth.events) == 1
    assert auth.events[0] == ("auth_list", 1, AUTH_PAGE_SIZE)


def test_auth_lookup_scans_later_page_and_compares_canonical_email():
    first_page = [FakeUser(f"user{index}@example.com") for index in range(AUTH_PAGE_SIZE)]
    target = FakeUser("ADMIN@EXAMPLE.COM")
    auth = FakeAuthAdmin({1: first_page, 2: [target]})

    assert find_auth_user_by_email(auth, EMAIL) is target
    assert [call[1] for call in auth.events] == [1, 2]


def test_auth_lookup_returns_none_when_pagination_ends():
    auth = FakeAuthAdmin({1: [FakeUser("other@example.com")]})

    assert find_auth_user_by_email(auth, EMAIL) is None
    assert len(auth.events) == 1


def test_auth_lookup_rejects_duplicate_target_identities():
    auth = FakeAuthAdmin({1: [FakeUser(EMAIL), FakeUser(EMAIL)]})

    with pytest.raises(RuntimeError, match="AUTH_EMAIL_AMBIGUOUS"):
        find_auth_user_by_email(auth, EMAIL)


def test_auth_lookup_stops_at_maximum_page_count():
    auth = FakeAuthAdmin({page: [FakeUser(f"u{page}@example.com") for _ in range(AUTH_PAGE_SIZE)] for page in range(1, 1001)})

    with pytest.raises(RuntimeError, match="AUTH_DIRECTORY_SCAN_LIMIT"):
        find_auth_user_by_email(auth, EMAIL)
    assert len(auth.events) == 1000


def test_success_binds_profile_to_auth_identity_after_invitation():
    events = []
    organizations = FakeOrganizations(events=events)
    profiles = FakeProfiles(events=events)
    auth = FakeAuthAdmin(events=events)

    result = service(organizations=organizations, profiles=profiles, auth=auth, events=events).provision(request())

    assert result.classification == "COMPLETE"
    mutations = [
        event[0]
        for event in events
        if event[0].endswith(("create", "invite", "bind"))
    ]
    assert mutations == [
        "organization_create",
        "profile_create",
        "auth_invite",
        "profile_bind",
    ]
    profile_payload = next(event[1] for event in events if event[0] == "profile_create")
    assert profile_payload == {"email": EMAIL, "org_id": ORG_ID, "role": "client_admin"}
    assert "id" not in profile_payload
    assert profiles.rows[EMAIL]["id"] != auth.pages[1][0].id
    assert profiles.rows[EMAIL]["auth_user_id"] == auth.pages[1][0].id


def test_legacy_auth_trigger_migration_only_drops_the_trigger_transactionally():
    import re

    sql = LEGACY_AUTH_TRIGGER_MIGRATION.read_text(encoding="utf-8")
    executable_sql = re.sub(r"--.*?$", "", sql, flags=re.MULTILINE)
    normalized_sql = " ".join(executable_sql.lower().split())

    assert normalized_sql == (
        "begin; drop trigger if exists on_auth_user_created on auth.users; commit;"
    )
    assert not re.search(r"\bdrop\s+function\b", normalized_sql)
    assert not re.search(
        r"\b(?:insert\s+into|update|delete\s+from)\s+"
        r"(?:public\.(?:users|organizations)|auth\.users)\b",
        normalized_sql,
    )
    assert "71cf875a-2103-47a0-8886-41a97c5750ec" not in normalized_sql


def test_auth_uid_migration_fails_closed_for_unmapped_profiles():
    sql = AUTH_UID_MIGRATION.read_text(encoding="utf-8").lower()
    assert "auth_user_id uuid" in sql
    assert "where auth_user_id is not null" in sql
    assert "using (auth_user_id = (select auth.uid()))" in " ".join(sql.split())
    assert "where u.auth_user_id = (select auth.uid())" in " ".join(sql.split())
    assert "update public.users" not in sql
    assert "auth.jwt()" not in sql
    for policy in (
        "cloud_cost_import_select_own_org",
        "cloud_cost_import_part_select_own_org",
        "cloud_account_mapping_select_own_org",
        "cloud_cost_reconciliation_select_own_org",
    ):
        assert f"create policy {policy}" in sql
    assert "create or replace function public.pvt003c1_can_read_organization" in sql
    assert "create or replace function public.fg002_resolve_cloud_account(" in sql
    assert "create or replace function public.fg002_bulk_resolve_cloud_accounts(" in sql
    assert sql.count("where u.auth_user_id = (select auth.uid())") >= 3
    assert "and u.org_id = requested_organization_id" in sql
    assert "lower(u.email) = actor_email" not in sql
    assert "actor_role text" in sql
    assert "account resolution permission required" in sql
    assert "revoke all on function public.fg002_resolve_cloud_account" in sql
    assert "grant execute on function public.fg002_resolve_cloud_account" in sql


def test_complete_state_is_already_complete_without_mutations():
    events = []
    orgs = FakeOrganizations({ORG_ID: {"id": ORG_ID, "name": ORG_NAME, "status": "active"}}, events)
    profiles = FakeProfiles(
        {
            EMAIL: {
                "id": "profile-id",
                "email": EMAIL,
                "org_id": ORG_ID,
                "role": "client_admin",
                "auth_user_id": AUTH_USER_ID,
            }
        },
        events,
    )
    auth = FakeAuthAdmin({1: [FakeUser(EMAIL)]}, events)

    result = service(organizations=orgs, profiles=profiles, auth=auth, events=events).provision(request())

    assert result.classification == "ALREADY_COMPLETE"
    assert not any(event[0].endswith(("create", "invite")) for event in events)


def test_organization_id_with_different_name_is_hard_conflict():
    orgs = FakeOrganizations({ORG_ID: {"id": ORG_ID, "name": "Different Name", "status": "active"}})

    result = service(organizations=orgs).provision(request())

    assert result.classification == "HARD_CONFLICT"
    assert result.reason_code == "ORGANIZATION_ID_NAME_MISMATCH"


def test_same_display_name_at_other_id_does_not_define_tenant_identity():
    events = []
    orgs = FakeOrganizations({"aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa": {"id": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa", "name": ORG_NAME, "status": "active"}}, events)
    auth = FakeAuthAdmin(events=events)

    result = service(organizations=orgs, auth=auth, events=events).provision(request())

    assert result.classification == "COMPLETE"
    assert orgs.rows[ORG_ID]["id"] == ORG_ID


@pytest.mark.parametrize(
    "profile",
    [
        {"id": "p1", "email": EMAIL, "org_id": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa", "role": "client_admin"},
        {"id": "p1", "email": EMAIL, "org_id": ORG_ID, "role": "finance"},
    ],
)
def test_profile_tenant_or_role_mismatch_is_hard_conflict(profile):
    profiles = FakeProfiles({EMAIL: profile})

    result = service(profiles=profiles).provision(request())

    assert result.classification == "HARD_CONFLICT"


def test_auth_identity_without_expected_profile_is_hard_conflict():
    auth = FakeAuthAdmin({1: [FakeUser(EMAIL)]})

    result = service(auth=auth).provision(request())

    assert result.classification == "HARD_CONFLICT"
    assert result.reason_code == "AUTH_PROFILE_IDENTITY_MISMATCH"


def test_profile_linked_to_different_auth_identity_is_hard_conflict():
    profiles = FakeProfiles(
        {
            EMAIL: {
                "id": "profile-id",
                "auth_user_id": "22222222-2222-4222-8222-222222222222",
                "email": EMAIL,
                "org_id": ORG_ID,
                "role": "client_admin",
            }
        }
    )
    auth = FakeAuthAdmin({1: [FakeUser(EMAIL)]})

    result = service(profiles=profiles, auth=auth).provision(request())

    assert result.classification == "HARD_CONFLICT"
    assert result.reason_code == "AUTH_PROFILE_IDENTITY_MISMATCH"


def test_profile_without_auth_identity_is_partial_and_not_auto_resumed():
    events = []
    profile = {"id": "p1", "email": EMAIL, "org_id": ORG_ID, "role": "client_admin"}
    profiles = FakeProfiles({EMAIL: profile}, events)
    orgs = FakeOrganizations({ORG_ID: {"id": ORG_ID, "name": ORG_NAME, "status": "active"}}, events)
    auth = FakeAuthAdmin(events=events)

    result = service(organizations=orgs, profiles=profiles, auth=auth, events=events).provision(request())

    assert result.classification == "PARTIAL_RECONCILIATION_REQUIRED"
    assert not any(event[0].endswith(("create", "invite")) for event in events)


def test_existing_organization_without_profile_or_auth_is_partial():
    orgs = FakeOrganizations({ORG_ID: {"id": ORG_ID, "name": ORG_NAME, "status": "active"}})

    result = service(organizations=orgs).provision(request())

    assert result.classification == "PARTIAL_RECONCILIATION_REQUIRED"


def test_organization_write_failure_is_partial_without_rollback():
    orgs = FakeOrganizations(create_error=RuntimeError("secret-shaped-provider-payload"))

    result = service(organizations=orgs).provision(request())

    assert result.classification == "PARTIAL_RECONCILIATION_REQUIRED"
    assert result.reason_code == "ORGANIZATION_WRITE_UNCERTAIN"
    assert orgs.rows == {}


def test_profile_write_failure_keeps_organization_and_requires_reconciliation():
    orgs = FakeOrganizations()
    profiles = FakeProfiles(create_error=RuntimeError("provider detail"))

    result = service(organizations=orgs, profiles=profiles).provision(request())

    assert result.classification == "PARTIAL_RECONCILIATION_REQUIRED"
    assert ORG_ID in orgs.rows
    assert profiles.rows == {}


def test_invitation_failure_keeps_org_and_profile_and_requires_reconciliation():
    orgs = FakeOrganizations()
    profiles = FakeProfiles()
    auth = FakeAuthAdmin(invite_error=RuntimeError("provider detail"))

    result = service(organizations=orgs, profiles=profiles, auth=auth).provision(request())

    assert result.classification == "PARTIAL_RECONCILIATION_REQUIRED"
    assert ORG_ID in orgs.rows
    assert EMAIL in profiles.rows
    assert result.reason_code == "AUTH_INVITATION_OUTCOME_UNCERTAIN"


def test_invitation_email_mismatch_is_partial_and_not_success():
    auth = FakeAuthAdmin(invite_email="other@example.com")

    result = service(auth=auth).provision(request())

    assert result.classification == "PARTIAL_RECONCILIATION_REQUIRED"
    assert result.reason_code == "AUTH_INVITATION_IDENTITY_MISMATCH"


def test_operator_evidence_contains_only_allowlisted_fields():
    result = service().provision(request())

    assert set(result.operator_evidence()) == {
        "request_id",
        "organization_id",
        "organization_name",
        "admin_email",
        "role",
        "timestamp",
        "per_step_status",
        "final_classification",
    }


def test_cli_dry_run_uses_no_client_reads_or_writes(monkeypatch, capsys):
    monkeypatch.setenv("SUPABASE_URL", "https://example.invalid")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "do-not-print-this-secret")
    monkeypatch.setattr(cli, "_build_live_service", lambda: pytest.fail("client must not be built"))

    code = cli.main(
        [
            "--request-id", REQUEST_ID,
            "--organization-id", ORG_ID,
            "--organization-name", ORG_NAME,
            "--admin-email", EMAIL,
            "--dry-run",
        ]
    )

    output = capsys.readouterr().out
    payload = json.loads(output)
    assert code == 0
    assert payload["final_classification"] == "DRY_RUN"
    assert payload["per_step_status"]["remote_reads"] == "NOT_RUN"
    assert payload["per_step_status"]["remote_writes"] == "NOT_RUN"
    assert "do-not-print-this-secret" not in output


def test_cli_defaults_to_dry_run_without_credentials(monkeypatch, capsys):
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_KEY", raising=False)
    monkeypatch.setattr(cli, "_build_live_service", lambda: pytest.fail("client must not be built"))

    code = cli.main(["--request-id", REQUEST_ID, "--organization-id", ORG_ID, "--organization-name", ORG_NAME, "--admin-email", EMAIL])

    payload = json.loads(capsys.readouterr().out)
    assert code == 0
    assert payload["final_classification"] == "DRY_RUN"
    assert payload["per_step_status"]["backend_credential_configured"] == "NO"


def test_cli_execute_requires_operator_ack_before_client_construction(monkeypatch, capsys):
    monkeypatch.setattr(cli, "_build_live_service", lambda: pytest.fail("client must not be built"))

    code = cli.main(
        [
            "--execute",
            "--request-id", REQUEST_ID,
            "--organization-id", ORG_ID,
            "--organization-name", ORG_NAME,
            "--admin-email", EMAIL,
        ]
    )

    assert code == 3
    assert json.loads(capsys.readouterr().out)["reason_code"] == "APPROVED_REQUEST_REQUIRED"


def test_cli_execute_can_use_an_injected_fake(monkeypatch, capsys):
    fake = service()
    monkeypatch.setenv("SUPABASE_URL", "https://example.invalid")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "not-output")
    monkeypatch.setattr(cli, "_build_live_service", lambda: fake)

    code = cli.main(
        [
            "--execute", "--approved-request",
            "--request-id", REQUEST_ID,
            "--organization-id", ORG_ID,
            "--organization-name", ORG_NAME,
            "--admin-email", EMAIL,
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    assert code == 0
    assert payload["final_classification"] == "COMPLETE"
    assert "not-output" not in json.dumps(payload)