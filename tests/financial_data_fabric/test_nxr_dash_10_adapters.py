"""Offline disabled-boundary and actual dashboard renderer regressions."""

from datetime import date
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest

from auth.authenticated_tenant import AuthenticatedTenantContext
from components.aws_financial_publication import render_aws_financial_publication
from repositories.aws_financial_evidence_repository import AwsFinancialEvidenceRepository
from services.aws_financial_dashboard_adapter import dashboard_status
from services.aws_financial_import_contribution_verifier import DashboardQuery
from services.aws_financial_ingestion_composition import compose_aws_financial_ingestion


def context():
    org = str(uuid4())
    return AuthenticatedTenantContext(
        org, "Tenant", str(uuid4()), "user@example.test", "cio", frozenset(), org
    )


def test_missing_issuer_never_calls_database():
    class Client:
        def rpc(self, *args):
            raise AssertionError("database must not be reached")

    repo = AwsFinancialEvidenceRepository(Client())
    with pytest.raises(PermissionError):
        repo.read(
            context(), (str(uuid4()),), DashboardQuery("USD", date(2026, 7, 1), date(2026, 7, 31))
        )


def test_dashboard_no_demo_fallback():
    class UI:
        def __init__(self):
            self.values = []

        def metric(self, *args):
            self.values.append(args)

        def __getattr__(self, name):
            return lambda *args, **kwargs: None

    ui = UI()
    status = render_aws_financial_publication(context(), ui=ui)
    assert status.readiness == "NOT_READY"
    assert status.published_at is None
    assert ui.values == [("AWS total spend", "UNKNOWN")]


def test_real_backend_composition_and_tenant_invalidation():
    ctx = context()
    orchestrator, adapter = compose_aws_financial_ingestion(
        backend_client=object(),
        context=ctx,
        query=DashboardQuery("USD", date(2026, 7, 1), date(2026, 7, 31)),
        request_id=str(uuid4()),
        tenant_verifier=object(),
        independent_reconciler=object(),
    )
    assert orchestrator._evidence_provider is adapter
    marker = object()
    adapter._capture = marker
    adapter.invalidate(str(uuid4()))
    assert adapter._capture is marker
    adapter.invalidate(ctx.organization_id)
    assert adapter._capture is None
    assert dashboard_status(ctx).readiness == "NOT_READY"


@pytest.mark.parametrize("kind", ["scope", "incomplete", "missing"])
def test_repository_rejects_bad_envelopes(kind):
    ctx = context()
    value = {
        "organization_id": ctx.organization_id,
        "tenant_id": ctx.tenant_id,
        "completeness": "COMPLETE",
    }
    if kind == "scope":
        value["tenant_id"] = str(uuid4())
    if kind == "incomplete":
        value["completeness"] = "INCOMPLETE"
    if kind == "missing":
        value = None
    client = SimpleNamespace(
        rpc=lambda *args: SimpleNamespace(execute=lambda: SimpleNamespace(data=value))
    )
    repo = AwsFinancialEvidenceRepository(client, grant_provider=lambda op: str(uuid4()))
    with pytest.raises(ValueError):
        repo.read(ctx, (str(uuid4()),), DashboardQuery("USD", date(2026, 7, 1), date(2026, 7, 31)))


def test_active_route_contains_guarded_publication_panel():
    root = Path(__file__).resolve().parents[2]
    route = (root / "pages/executive_command_center.py").read_text()
    shared = (root / "shared/executive_page.py").read_text()
    assert 'run_executive_workspace("command"' in route
    assert 'if key == "command":' in shared
    assert "render_aws_financial_publication(authenticated, ui=st)" in shared


def test_dbapi_transport_rejects_arbitrary_functions_before_connecting():
    from repositories.aws_financial_evidence_repository import PostgresFinancialRpcClient

    def forbidden():
        raise AssertionError("no connection allowed")

    client = PostgresFinancialRpcClient(forbidden)
    with pytest.raises(ValueError):
        client.rpc("arbitrary_function", {})
    with pytest.raises(ValueError):
        client.rpc("read_aws_financial_contribution_evidence_v1", {})
