import ast
from types import SimpleNamespace

import pytest

from utils import auth as streamlit_auth

AUTH_USER_A = "11111111-1111-4111-8111-111111111111"
AUTH_USER_B = "22222222-2222-4222-8222-222222222222"
ORG_A = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
ORG_B = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"


class FakeQuery:
    def __init__(self, client, table):
        self.client = client
        self.table_name = table
        self.filters = {}

    def select(self, _columns):
        return self

    def eq(self, column, value):
        self.filters[column] = value
        return self

    def limit(self, _count):
        return self

    def execute(self):
        if self.table_name == "users":
            assert self.filters == {"auth_user_id": self.client.user.id}
            profile = self.client.profiles.get(self.client.user.id)
            return SimpleNamespace(data=[profile] if profile else [])
        if self.table_name == "organizations":
            organization = self.client.organizations.get(self.filters.get("id"))
            return SimpleNamespace(data=[organization] if organization else [])
        raise AssertionError(f"Unexpected table lookup: {self.table_name}")


class FakeAuth:
    def __init__(self, user):
        self.user = user
        self.sign_out_calls = 0
        self.session = SimpleNamespace(access_token="synthetic-access-token")

    def sign_in_with_password(self, _credentials):
        return SimpleNamespace(user=self.user, session=self.session)

    def get_session(self):
        return self.session

    def sign_out(self):
        self.sign_out_calls += 1


class FakeClient:
    def __init__(self, user, profile, organization):
        self.user = user
        self.profiles = {profile["auth_user_id"]: profile} if profile else {}
        self.organizations = {organization["id"]: organization} if organization else {}
        self.auth = FakeAuth(user)

    def table(self, name):
        return FakeQuery(self, name)


def _user(user_id, email):
    return SimpleNamespace(id=user_id, email=email)


def _profile(user_id, organization_id, *, auth_user_id=None):
    return {
        "id": "independent-profile-row-id",
        "auth_user_id": auth_user_id or user_id,
        "email": {
            AUTH_USER_A: "a@example.com",
            AUTH_USER_B: "b@example.com",
        }.get(user_id, "user@example.com"),
        "org_id": organization_id,
        "role": "client_admin",
        "permissions": ["cost:read"],
    }


def _organization(organization_id):
    return {"id": organization_id, "name": "Authorized Org", "status": "active"}


def test_auth_client_factory_returns_isolated_anon_clients(monkeypatch):
    from services import supabase_client

    created = []
    monkeypatch.setattr(supabase_client, "SUPABASE_URL", "https://example.invalid")
    monkeypatch.setenv("SUPABASE_ANON_KEY", "test-anon-key")
    monkeypatch.setattr(
        supabase_client,
        "create_client",
        lambda url, key: created.append((url, key, object())) or created[-1][2],
    )

    first = supabase_client.create_user_auth_client()
    second = supabase_client.create_user_auth_client()

    assert first is not second
    assert [item[:2] for item in created] == [
        ("https://example.invalid", "test-anon-key"),
        ("https://example.invalid", "test-anon-key"),
    ]


def test_auth_client_factory_requires_explicit_anon_key(monkeypatch):
    from services import supabase_client

    monkeypatch.setattr(supabase_client, "SUPABASE_URL", "https://example.invalid")
    monkeypatch.delenv("SUPABASE_ANON_KEY", raising=False)
    monkeypatch.delenv("SUPABASE_ANON_KEY_FILE", raising=False)

    with pytest.raises(RuntimeError, match="SUPABASE_ANON_KEY"):
        supabase_client.create_user_auth_client()


def test_auth_client_factory_reads_mounted_anon_key_file(monkeypatch, tmp_path):
    from services import supabase_client

    key_file = tmp_path / "supabase-anon-key"
    key_file.write_text("test-anon-key\n", encoding="utf-8")
    created = []
    monkeypatch.setattr(supabase_client, "SUPABASE_URL", "https://example.invalid")
    monkeypatch.delenv("SUPABASE_ANON_KEY", raising=False)
    monkeypatch.setenv("SUPABASE_ANON_KEY_FILE", str(key_file))
    monkeypatch.setattr(
        supabase_client,
        "create_client",
        lambda url, key: created.append((url, key, object())) or created[-1][2],
    )

    supabase_client.create_user_auth_client()

    assert [item[:2] for item in created] == [
        ("https://example.invalid", "test-anon-key"),
    ]


def test_authentication_clients_and_state_are_isolated_between_users(monkeypatch):
    state_a = {}
    state_b = {}
    clients = iter(
        [
            FakeClient(
                _user(AUTH_USER_A, "a@example.com"),
                _profile(AUTH_USER_A, ORG_A),
                _organization(ORG_A),
            ),
            FakeClient(
                _user(AUTH_USER_B, "b@example.com"),
                _profile(AUTH_USER_B, ORG_B),
                _organization(ORG_B),
            ),
        ]
    )
    monkeypatch.setattr(streamlit_auth.st, "session_state", state_a)
    monkeypatch.setattr(streamlit_auth, "create_session_client", lambda: next(clients))

    streamlit_auth.login_user("a@example.com", "password")
    first_client = state_a["auth_client"]

    monkeypatch.setattr(streamlit_auth.st, "session_state", state_b)
    streamlit_auth.login_user("b@example.com", "password")

    assert state_a["user_id"] == AUTH_USER_A
    assert state_a["organization_id"] == ORG_A
    assert state_b["user_id"] == AUTH_USER_B
    assert state_b["organization_id"] == ORG_B
    assert first_client is not state_b["auth_client"]
    assert state_b["auth_client"].auth.sign_out_calls == 0


def test_login_clears_stale_tenant_before_establishing_new_identity(monkeypatch):
    state = {
        "authenticated": True,
        "user_id": AUTH_USER_A,
        "organization_id": ORG_A,
        "tenant_id": ORG_A,
        "authorized_organization_ids": [ORG_A],
        "role": "super_admin",
    }
    client = FakeClient(
        _user(AUTH_USER_B, "b@example.com"),
        _profile(AUTH_USER_B, ORG_B),
        _organization(ORG_B),
    )
    monkeypatch.setattr(streamlit_auth.st, "session_state", state)
    monkeypatch.setattr(streamlit_auth, "create_session_client", lambda: client)

    streamlit_auth.login_user("b@example.com", "password")

    assert state["user_id"] == AUTH_USER_B
    assert state["organization_id"] == ORG_B
    assert state["tenant_id"] == ORG_B
    assert state["authorized_organization_ids"] == [ORG_B]
    assert state["role"] == "client_admin"
    assert state["user"] == client.user


@pytest.mark.parametrize("user_id", [None, "", "not-a-uuid"])
def test_login_rejects_missing_or_invalid_supabase_identity(monkeypatch, user_id):
    client = FakeClient(
        _user(user_id, "a@example.com"),
        None,
        None,
    )
    state = {"organization_id": ORG_A, "authenticated": True}
    monkeypatch.setattr(streamlit_auth.st, "session_state", state)
    monkeypatch.setattr(streamlit_auth, "create_session_client", lambda: client)

    with pytest.raises(streamlit_auth.AuthenticationError):
        streamlit_auth.login_user("a@example.com", "password")

    assert state.get("authenticated") is not True
    assert "organization_id" not in state


def test_login_rejects_auth_response_without_established_session(monkeypatch):
    client = FakeClient(
        _user(AUTH_USER_A, "a@example.com"),
        _profile(AUTH_USER_A, ORG_A),
        _organization(ORG_A),
    )
    client.auth.sign_in_with_password = lambda _credentials: SimpleNamespace(
        user=client.user,
        session=None,
    )
    state = {"authenticated": True, "organization_id": ORG_A}
    monkeypatch.setattr(streamlit_auth.st, "session_state", state)
    monkeypatch.setattr(streamlit_auth, "create_session_client", lambda: client)

    with pytest.raises(streamlit_auth.AuthenticationError):
        streamlit_auth.login_user("a@example.com", "password")

    assert not set(state).intersection(streamlit_auth.AUTH_SESSION_KEYS)


@pytest.mark.parametrize(
    "profile",
    [
        None,
        {"auth_user_id": AUTH_USER_B, "org_id": ORG_A, "role": "viewer"},
    ],
    ids=["missing-membership", "membership-bound-to-another-user"],
)
def test_login_rejects_missing_or_foreign_membership(monkeypatch, profile):
    client = FakeClient(
        _user(AUTH_USER_A, "a@example.com"),
        profile,
        _organization(ORG_A),
    )
    monkeypatch.setattr(streamlit_auth.st, "session_state", {})
    monkeypatch.setattr(streamlit_auth, "create_session_client", lambda: client)

    with pytest.raises(streamlit_auth.AuthenticationError):
        streamlit_auth.login_user("a@example.com", "password")


def test_login_rejects_inactive_or_missing_organization(monkeypatch):
    profile = _profile(AUTH_USER_A, ORG_A)
    client = FakeClient(_user(AUTH_USER_A, "a@example.com"), profile, None)
    monkeypatch.setattr(streamlit_auth.st, "session_state", {})
    monkeypatch.setattr(streamlit_auth, "create_session_client", lambda: client)

    with pytest.raises(streamlit_auth.AuthenticationError):
        streamlit_auth.login_user("a@example.com", "password")

    client.organizations[ORG_A] = _organization(ORG_A) | {"status": "disabled"}
    with pytest.raises(streamlit_auth.AuthenticationError):
        streamlit_auth.login_user("a@example.com", "password")

    client.organizations[ORG_A] = _organization(ORG_A) | {"status": None}
    with pytest.raises(streamlit_auth.AuthenticationError):
        streamlit_auth.login_user("a@example.com", "password")


def test_tenant_selection_requires_trusted_membership(monkeypatch):
    state = {
        "authenticated": True,
        "auth_backend": "supabase",
        "user_id": AUTH_USER_A,
        "user": _user(AUTH_USER_A, "a@example.com"),
        "profile": _profile(AUTH_USER_A, ORG_A),
        "authorized_organization_ids": [ORG_A],
    }
    monkeypatch.setattr(streamlit_auth.st, "session_state", state)

    streamlit_auth.select_tenant(ORG_A)

    assert state["organization_id"] == ORG_A
    with pytest.raises(streamlit_auth.AuthenticationError):
        streamlit_auth.select_tenant(ORG_B)
    assert state["organization_id"] == ORG_A


def test_logout_signs_out_own_client_and_clears_auth_and_tenant_state(monkeypatch):
    client = FakeClient(
        _user(AUTH_USER_A, "a@example.com"),
        _profile(AUTH_USER_A, ORG_A),
        _organization(ORG_A),
    )
    state = {
        "authenticated": True,
        "auth_client": client,
        "session": object(),
        "user": client.user,
        "profile": _profile(AUTH_USER_A, ORG_A),
        "user_id": AUTH_USER_A,
        "email": "a@example.com",
        "role": "client_admin",
        "role_display": "client_admin",
        "permissions": ["cost:read"],
        "organization_id": ORG_A,
        "org_id": ORG_A,
        "tenant_id": ORG_A,
        "tenant": ORG_A,
        "organization_name": "Authorized Org",
        "authorized_organization_ids": [ORG_A],
        "auth_backend": "supabase",
    }
    monkeypatch.setattr(streamlit_auth.st, "session_state", state)

    streamlit_auth.logout_user()

    assert client.auth.sign_out_calls == 1
    assert not set(state).intersection(streamlit_auth.AUTH_SESSION_KEYS)


def test_logout_clears_local_state_even_when_remote_signout_fails(monkeypatch):
    class FailingAuth(FakeAuth):
        def sign_out(self):
            raise RuntimeError("remote signout failed")

    client = FakeClient(_user(AUTH_USER_A, "a@example.com"), None, None)
    client.auth = FailingAuth(client.user)
    state = {"authenticated": True, "auth_client": client, "organization_id": ORG_A}
    monkeypatch.setattr(streamlit_auth.st, "session_state", state)

    with pytest.raises(RuntimeError, match="remote signout failed"):
        streamlit_auth.logout_user()

    assert not set(state).intersection(streamlit_auth.AUTH_SESSION_KEYS)


def test_logout_clears_customer_workflow_state(monkeypatch):
    client = FakeClient(_user(AUTH_USER_A, "a@example.com"), None, None)
    state = {
        "authenticated": True,
        "auth_backend": "supabase",
        "auth_client": client,
        "customer_workflow_workspace_id": "workspace-a",
        "active_customer_export": {"export_id": "export-a"},
    }
    monkeypatch.setattr(streamlit_auth.st, "session_state", state)

    streamlit_auth.logout_user()

    assert client.auth.sign_out_calls == 1
    assert "customer_workflow_workspace_id" not in state
    assert "active_customer_export" not in state


def test_supabase_tenant_context_uses_its_authenticated_session_client(monkeypatch):
    from services import enterprise_spend_composition

    profile = _profile(AUTH_USER_A, ORG_A)
    client = FakeClient(
        _user(AUTH_USER_A, "a@example.com"),
        profile,
        _organization(ORG_A),
    )
    state = {
        "authenticated": True,
        "auth_backend": "supabase",
        "auth_client": client,
        "user": client.user,
        "user_id": AUTH_USER_A,
        "profile": profile,
        "email": "a@example.com",
        "role": "client_admin",
        "organization_id": ORG_A,
        "authorized_organization_ids": [ORG_A],
    }

    class ForbiddenAnonymousClient:
        def table(self, _name):
            pytest.fail("organization lookup must use the authenticated session client")

    monkeypatch.setattr(enterprise_spend_composition, "supabase", ForbiddenAnonymousClient())

    context = enterprise_spend_composition.authenticated_tenant_context(state)

    assert context.organization_id == ORG_A
    assert context.organization_name == "Authorized Org"
    assert state["organization_name"] == "Authorized Org"


def test_production_spend_service_uses_financial_client_from_auth_session(monkeypatch):
    from auth.authenticated_tenant import AuthenticatedTenantContext
    from services import enterprise_spend_composition

    context = AuthenticatedTenantContext(
        ORG_A,
        "Authorized Org",
        AUTH_USER_A,
        "a@example.com",
        "client_admin",
        frozenset({"cost:read"}),
        ORG_A,
        environment="production",
    )
    client = object()
    financial_client = object()
    monkeypatch.setattr(
        enterprise_spend_composition,
        "create_user_financial_data_client",
        lambda auth_client: financial_client if auth_client is client else None,
    )
    monkeypatch.setattr(
        enterprise_spend_composition,
        "EnterpriseSpendService",
        lambda repository: repository,
    )

    service = enterprise_spend_composition.enterprise_spend_service(
        context,
        auth_client=client,
    )

    assert service._client is financial_client


def test_production_spend_service_fails_closed_without_session_client():
    from auth.authenticated_tenant import (
        AuthenticatedTenantContext,
        AuthenticatedTenantError,
    )
    from services import enterprise_spend_composition

    context = AuthenticatedTenantContext(
        ORG_A,
        "Authorized Org",
        AUTH_USER_A,
        "a@example.com",
        "client_admin",
        frozenset({"cost:read"}),
        ORG_A,
        environment="production",
    )

    with pytest.raises(AuthenticatedTenantError, match="session client is required"):
        enterprise_spend_composition.enterprise_spend_service(context)


def test_supabase_tenant_resolver_fails_closed_without_session_client():
    from auth.authenticated_tenant import AuthenticatedTenantError
    from services.enterprise_spend_composition import _organization_resolver

    with pytest.raises(AuthenticatedTenantError, match="authenticated Supabase client"):
        _organization_resolver(
            {
                "auth_backend": "supabase",
                "organization_id": ORG_A,
                "authorized_organization_ids": [ORG_A],
            }
        )


def test_supabase_tenant_resolver_rejects_forged_organization():
    from auth.authenticated_tenant import AuthenticatedTenantError
    from services.enterprise_spend_composition import _organization_resolver

    profile = _profile(AUTH_USER_A, ORG_A)
    client = FakeClient(
        _user(AUTH_USER_A, "a@example.com"),
        profile,
        _organization(ORG_A),
    )
    client.organizations[ORG_B] = _organization(ORG_B)
    resolve = _organization_resolver(
        {
            "auth_backend": "supabase",
            "auth_client": client,
            "organization_id": ORG_A,
            "authorized_organization_ids": [ORG_A],
        }
    )

    with pytest.raises(AuthenticatedTenantError, match="tenant boundary"):
        resolve(ORG_B)


def test_tenant_context_requires_uid_binding_and_membership(monkeypatch):
    from auth.authenticated_tenant import AuthenticatedTenantContext, AuthenticatedTenantError

    session = {
        "authenticated": True,
        "auth_backend": "supabase",
        "user_id": AUTH_USER_A,
        "user": _user(AUTH_USER_A, "a@example.com"),
        "profile": _profile(AUTH_USER_A, ORG_A),
        "session": {"access_token": "synthetic-access-token"},
        "authorized_organization_ids": [ORG_A],
        "organization_id": ORG_A,
        "organization_name": "Authorized Org",
        "role": "super_admin",
    }

    context = AuthenticatedTenantContext.from_session(
        session,
        organization_resolver=lambda _organization_id: "Authorized Org",
    )
    assert context.user_id == AUTH_USER_A
    assert context.role == "client_admin"

    session["profile"] = _profile(AUTH_USER_B, ORG_A)
    with pytest.raises(AuthenticatedTenantError):
        AuthenticatedTenantContext.from_session(
            session,
            organization_resolver=lambda _organization_id: "Authorized Org",
        )

    session["profile"] = _profile(AUTH_USER_A, ORG_A) | {"org_id": None}
    with pytest.raises(AuthenticatedTenantError):
        AuthenticatedTenantContext.from_session(
            session,
            organization_resolver=lambda _organization_id: "Authorized Org",
        )

    session["profile"] = _profile(AUTH_USER_A, ORG_A)
    session.pop("authorized_organization_ids")
    with pytest.raises(AuthenticatedTenantError):
        AuthenticatedTenantContext.from_session(
            session,
            organization_resolver=lambda _organization_id: "Authorized Org",
        )

    session["authorized_organization_ids"] = [ORG_A]
    session["user"] = None
    with pytest.raises(AuthenticatedTenantError):
        AuthenticatedTenantContext.from_session(
            session,
            organization_resolver=lambda _organization_id: "Authorized Org",
        )


def test_legacy_login_entrypoint_has_no_unconditional_admin_bypass():
    from pathlib import Path

    source_path = Path(__file__).resolve().parents[2] / "Login.py"
    tree = ast.parse(source_path.read_text(encoding="utf-8-sig"))
    parents = {
        child: node
        for node in ast.walk(tree)
        for child in ast.iter_child_nodes(node)
    }

    def is_authenticated_success_assignment(node):
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            return False
        target = node.targets[0] if isinstance(node, ast.Assign) else node.target
        return (
            isinstance(target, ast.Subscript)
            and isinstance(target.value, ast.Attribute)
            and isinstance(target.value.value, ast.Name)
            and target.value.value.id == "st"
            and target.value.attr == "session_state"
            and isinstance(target.slice, ast.Constant)
            and target.slice.value == "authenticated"
            and isinstance(node.value, ast.Constant)
            and node.value.value is True
        )

    assignments = [
        node for node in ast.walk(tree) if is_authenticated_success_assignment(node)
    ]
    assert assignments
    for assignment in assignments:
        ancestor = parents.get(assignment)
        while ancestor is not None and not (
            isinstance(ancestor, ast.If)
            and isinstance(ancestor.test, ast.Name)
            and ancestor.test.id == "login_btn"
        ):
            ancestor = parents.get(ancestor)
        assert ancestor is not None
