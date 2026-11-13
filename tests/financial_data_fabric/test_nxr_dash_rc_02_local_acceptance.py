"""RC-02 local synthetic acceptance; no hosted authentication/authority claims.

Reuses the NXR-DASH-10 fresh-cluster fixture, never an existing URL or service.
Synthetic authority mocks are confined to that disposable fixture database.
"""

import ast
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest

from components.aws_financial_publication import render_aws_financial_publication
from repositories.aws_financial_evidence_repository import FinancialOperation
from repositories.aws_financial_evidence_repository import PostgresFinancialRpcClient as RpcClient
from services.aws_financial_ingestion_composition import (
    AwsFinancialReadBackend,
    AwsFinancialReadSelection,
    configure_aws_financial_read_backend,
)
from tests.financial_data_fabric.test_nxr_dash_10_postgres import (
    QUERY,
    Verifier,
    grants,
    ingest_pair,
    tenant,
)
from tests.financial_data_fabric.test_nxr_dash_10_postgres import cluster as cluster
from tests.financial_data_fabric.test_nxr_dash_10_postgres import db as db
from tests.financial_data_fabric.test_nxr_dash_rc_01_composition import UI


@pytest.fixture(autouse=True)
def reset_backend():
    configure_aws_financial_read_backend(None)
    yield
    configure_aws_financial_read_backend(None)


def active_route(context, ui):
    """Execute actual route function with local identity/UI and unrelated-service doubles.

    AWS panel, backend composition, adapter, verifier, repository and RPC are real.
    No Streamlit application service or unrelated Supabase client is initialized.
    """
    ui.session_state = {
        "authenticated": True,
        "role": "cio",
        "organization_id": str(uuid4()),
        "authorization_grant_id": "UNTRUSTED_BROWSER_HINT",
    }
    path = Path(__file__).resolve().parents[2] / "shared/executive_page.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    function = next(
        n
        for n in tree.body
        if isinstance(n, ast.FunctionDef) and n.name == "run_executive_workspace"
    )
    statuses = []

    def panel(*args, **kwargs):
        status = render_aws_financial_publication(*args, **kwargs)
        statuses.append(status)
        return status

    namespace = {
        "st": ui,
        "configure_page": lambda *a, **kw: None,
        "init_session": lambda: None,
        "resolve_active_evidence_context": lambda session: SimpleNamespace(
            is_prospect=False, organization_id=context.organization_id
        ),
        "authenticated_tenant_context": lambda session: context,
        "render_sidebar_navigation": lambda *a: None,
        "enterprise_spend_service": lambda: object(),
        "CanonicalOptimizationService": lambda: object(),
        "EnterpriseIntelligenceQueryService": lambda **kw: object(),
        "ExecutiveWorkspaceCompositionService": SimpleNamespace(
            get_snapshot=lambda *a, **kw: object()
        ),
        "PAGE_PATHS": {},
        "ROLE_PAGES": {},
        "render_workspace": lambda *a, **kw: None,
        "render_aws_financial_publication": panel,
    }
    exec(compile(ast.Module(body=[function], type_ignores=[]), str(path), "exec"), namespace)
    namespace["run_executive_workspace"]("command", "Executive Command Center")
    return statuses[0]


def test_database_backed_active_executive_route_is_read_only_and_fails_closed(request):
    conn, factory = request.getfixturevalue("db")
    context, store, repository, adapter, ids = ingest_pair(conn, factory)
    # Existing test-only read capability is obtained BEFORE rendering. It is not a trusted grant.
    read_grant = grants(conn)(FinancialOperation(context, ids, QUERY, "read"))
    calls = []

    class ReadClient:
        def rpc(self, name, params):
            assert name == "read_aws_financial_contribution_evidence_v1"
            calls.append((name, dict(params)))
            return RpcClient(factory).rpc(name, params)

    def canonical_coverage(verified):
        assert verified == context
        with conn.cursor() as cur:
            cur.execute(
                "select import_id::text from public.cloud_cost_import where organization_id=%s "
                "and tenant_id=%s order by created_at,import_id",
                (verified.organization_id, verified.tenant_id),
            )
            coverage = tuple(row[0] for row in cur.fetchall())
        return AwsFinancialReadSelection(
            context.organization_id, context.tenant_id, context.user_id, coverage, QUERY
        )

    def existing_grant(operation):
        assert operation.permission == "read" and operation.context == context
        return read_grant

    configure_aws_financial_read_backend(
        AwsFinancialReadBackend(ReadClient(), Verifier(context), canonical_coverage, existing_grant)
    )

    def counts():
        with conn.cursor() as cur:
            cur.execute(
                "select (select count(*) from financial_evidence.projection_generation),"
                "(select count(*) from financial_evidence.source_attestation),"
                "(select count(*) from financial_evidence.operation_authorization_grant),"
                "(select count(*) from public.cloud_cost_fact)"
            )
            return cur.fetchone()

    before = counts()
    ui = UI()
    status = active_route(context, ui)
    assert status.readiness == "READY"
    assert ("AWS total spend", "20,000.00 USD") in ui.values
    assert status.posture.import_count == 2 and status.posture.persisted_facts == 2
    assert (
        status.posture.period_start == QUERY.period_start
        and status.posture.period_end == QUERY.period_end
    )
    assert status.published_at == datetime.fromisoformat(adapter.receipt["published_at"])
    assert counts() == before
    assert len(calls) == 1 and calls[0][1]["organization_id"] == context.organization_id
    other = tenant(conn)
    other_ui = UI()
    assert active_route(other, other_ui).readiness == "NOT_READY"
    assert other_ui.values == [("AWS total spend", "UNKNOWN")]
    assert len(calls) == 1
    # Same-total canonical mutation must invalidate proof on the next page render.
    with conn.cursor() as cur:
        cur.execute(
            "update public.cloud_cost_fact set source_row_hash=repeat('f',64) where import_id=%s",
            (ids[0],),
        )
    stale_ui = UI()
    assert active_route(context, stale_ui).readiness == "NOT_READY"
    assert stale_ui.values == [("AWS total spend", "UNKNOWN")]
    assert counts() == before
    configure_aws_financial_read_backend(None)
    assert active_route(context, UI()).readiness == "NOT_READY"
    print(
        "LOCAL ACTIVE ROUTE PASS: USD 12000+8000=20000; canonical DB read only; "
        "B denied; stale/absent -> UNKNOWN"
    )
