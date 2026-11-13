import runpy
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest

from auth.authenticated_tenant import AuthenticatedTenantContext
from data_fabric.contracts import EnterpriseEntity
from repositories.application_portfolio_repository import (
    ApplicationPortfolioRepository as Repository,
)
from repositories.application_portfolio_repository import (
    PortfolioUnavailable,
)
from services.application_portfolio_service import ApplicationPortfolioService as Service

A = "11111111-1111-1111-1111-111111111111"
B = "22222222-2222-2222-2222-222222222222"


def context(org=A):
    return AuthenticatedTenantContext(
        org, "Tenant", "user", "user@example.com", "cio", frozenset(), org
    )


def entity(identity, org=A):
    return EnterpriseEntity(
        identity, identity, "application", "Same name", "registry", identity, org, org
    )


class Source:
    def __init__(self, rows):
        self.rows = rows

    def entities(self, scope):
        assert scope.organization_id == A
        assert scope.tenant_id == A
        return self.rows


def test_inventory_and_stable_identity():
    rows = Repository.get_applications(context(), source=Source([entity("app-2"), entity("app-1")]))
    assert [row["id"] for row in rows] == ["app-1", "app-2"]
    assert rows[0]["app_name"] == "Same name"
    assert rows == Repository.get_applications(
        context(), source=Source([entity("app-1"), entity("app-2")])
    )


def test_empty_and_missing_backend(monkeypatch):
    assert Service.get_portfolio(context(), source=Source([]))["applications"] == []
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    result = Service.get_portfolio(context())
    assert result["status"] == "NOT_AVAILABLE"
    assert result["applications"] is None


def test_cross_tenant_fails_closed():
    with pytest.raises(PortfolioUnavailable):
        Repository.get_applications(context(), source=Source([entity("foreign", B)]))
    assert (
        Service.get_portfolio(context(), source=Source([entity("foreign", B)]))["status"]
        == "NOT_AVAILABLE"
    )


def test_auth_required():
    with pytest.raises(PermissionError):
        Repository.get_applications(source=Source([]))
    with pytest.raises(PermissionError):
        Repository.get_application_spend()


def test_financial_attribution_unknown():
    result = Service.get_portfolio(context(), source=Source([entity("app")]))
    assert result["financial"]["status"] == "UNKNOWN"
    assert result["financial"]["rows"] == []
    assert "canonical_id" in result["financial"]["reason"]


@pytest.mark.parametrize(
    "rows, expected",
    [
        ([entity("one"), entity("two")], "Applications"),
        ([], "No canonical applications"),
        ([entity("foreign", B)], "NOT_AVAILABLE"),
        (None, "NOT_AVAILABLE"),
    ],
)
def test_actual_page_composition(monkeypatch, rows, expected):
    events = []

    def module(name, **values):
        obj = ModuleType(name)
        obj.__dict__.update(values)
        monkeypatch.setitem(sys.modules, name, obj)

    def emit(*args, **kwargs):
        events.append(args)

    def noop(*args, **kwargs):
        pass

    module(
        "streamlit", session_state={"role": "cio"}, error=emit, warning=emit, info=emit, metric=emit
    )
    module("components.layout", render_page=lambda **kw: kw["content"]())
    module("components.navigation", render_enterprise_sidebar=noop)
    module(
        "components.sidebar_navigation", PAGE_PATHS={"Application Portfolio": "page"}, ROLE_PAGES={}
    )
    module("shared.auth", require_role=noop)
    module("shared.session", init_session=noop)
    module("shared.styles", configure_page=noop)
    module("shared.streamlit_compat", dataframe=emit)
    module(
        "services.enterprise_spend_composition",
        authenticated_tenant_context=lambda session: context(),
    )
    if rows is None:
        monkeypatch.delenv("SUPABASE_URL", raising=False)
    else:
        monkeypatch.setattr(
            "repositories.application_portfolio_repository.CanonicalDataFabricRegistrySource.from_supabase",
            lambda *args: Source(rows),
        )
        monkeypatch.setenv("SUPABASE_URL", "https://example.invalid")
        monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "test-only")
    runpy.run_path(str(Path(__file__).parents[2] / "pages/application_inventory.py"))
    assert any(expected in str(event) for event in events)
    assert any("UNKNOWN" in str(event) for event in events)
    assert not any("$0" in str(event) for event in events)
    if rows and rows[0].organization_id == A:
        displayed = next(event[0] for event in events if isinstance(event[0], list))
        assert [row["id"] for row in displayed] == ["one", "two"]


def test_canonical_reader_filters_both_tenant_columns():
    from data_fabric.adapters.supabase.entity_repository import SupabaseEntityRepository
    from data_fabric.persistence.models import RepositoryQuery

    calls = []

    class Query:
        def __getattr__(self, name):
            def call(*args, **kwargs):
                calls.append((name, args))
                return SimpleNamespace(data=[]) if name == "execute" else self

            return call

    query = Query()
    client = SimpleNamespace(table=lambda name: query, execute=lambda operation: operation())
    SupabaseEntityRepository(client).search(RepositoryQuery(context().fabric_context))
    assert ("eq", ("organization_id", A)) in calls
    assert ("eq", ("tenant_id", A)) in calls
    assert all(name not in {"insert", "update", "rpc", "upsert"} for name, _ in calls)


def test_reader_failure_is_not_empty_success():
    class Broken:
        def entities(self, scope):
            raise RuntimeError("backend unavailable")

    result = Service.get_portfolio(context(), source=Broken())
    assert result["status"] == "NOT_AVAILABLE"
    assert result["applications"] is None


def test_uid_membership_mismatch_rejected():
    from auth.authenticated_tenant import AuthenticatedTenantError

    session = {
        "authenticated": True,
        "auth_backend": "supabase",
        "organization_id": A,
        "user_id": A,
        "user": SimpleNamespace(id=A, email="user@example.com"),
        "profile": {"auth_user_id": B, "org_id": A, "role": "cio"},
        "authorized_organization_ids": [A],
    }
    with pytest.raises(AuthenticatedTenantError):
        AuthenticatedTenantContext.from_session(session, organization_resolver=lambda org: "Tenant")


def test_active_page_does_not_import_financial_rendering_or_demo():
    import ast

    tree = ast.parse((Path(__file__).parents[2] / "pages/application_inventory.py").read_text())
    imports = [node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)]
    assert "services.application_inventory_certification_service" not in imports
    assert "services.enterprise_financial_model" not in imports
    assert not any("demo" in name for name in imports)
