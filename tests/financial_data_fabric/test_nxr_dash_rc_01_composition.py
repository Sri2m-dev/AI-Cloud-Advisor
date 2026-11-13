"""Synthetic offline wire responses, never hosted data or approval evidence."""

import ast
from copy import deepcopy
from dataclasses import asdict, replace
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest

from components.aws_financial_publication import render_aws_financial_publication
from services.aws_financial_ingestion_composition import (
    AwsFinancialReadBackend,
    AwsFinancialReadSelection,
    _ReadOnlyFinancialClient,
    aws_financial_dashboard_status,
    configure_aws_financial_read_backend,
)
from tests.cur_ingestion.test_aws_financial_import_contribution_verifier import (
    OBSERVED,
    QUERY,
    REFRESHED,
    EvidenceReaders,
    context,
)


@pytest.fixture(autouse=True)
def reset_backend():
    configure_aws_financial_read_backend(None)
    yield
    configure_aws_financial_read_backend(None)


class UI:
    def __init__(self):
        self.values = []
        self.captions = []
        self.warnings = []

    def metric(self, *args):
        self.values.append(args)

    def caption(self, value):
        self.captions.append(value)

    def warning(self, value):
        self.warnings.append(value)

    def __getattr__(self, name):
        return lambda *args, **kwargs: None


def wire_fixture():
    ctx = context()
    r = EvidenceReaders()
    ids = tuple(str(uuid4()) for _ in range(2))
    replacements = {
        "import-1": ids[0],
        "import-2": ids[1],
        "fact-1": str(uuid4()),
        "fact-2": str(uuid4()),
    }
    generation = str(uuid4())

    def wire(x):
        if isinstance(x, dict):
            return {k: wire(v) for k, v in x.items()}
        if isinstance(x, (list, tuple)):
            return [wire(v) for v in x]
        if isinstance(x, (date, datetime)):
            return x.isoformat()
        if isinstance(x, Decimal):
            return str(x)
        return replacements.get(x, x) if isinstance(x, str) else x

    sources = [
        dict(
            row,
            attestation_id=str(uuid4()),
            attestation_status="verified",
            retained_evidence_ref="synthetic-fixture-version",
            retained_evidence_sha256="a" * 64,
            parser_contract="synthetic-only",
            attester_id="TEST_ONLY",
            attested_at=REFRESHED,
        )
        for row in r.sources.values()
    ]
    posture = replace(r.projection.posture, generated_at=REFRESHED)
    env = wire(
        {
            "contract_version": "nxr-dash-08-v1",
            "organization_id": ctx.organization_id,
            "tenant_id": ctx.tenant_id,
            "requested_import_ids": ids,
            "query": asdict(QUERY),
            "snapshot_id": "SYNTHETIC_OFFLINE_SNAPSHOT",
            "observed_at": OBSERVED,
            "completeness": "COMPLETE",
            "reasons": [],
            "missing_import_ids": [],
            "unexpected_import_ids": [],
            "sources": sources,
            "canonical": {
                "imports": r.canonical.imports,
                "facts": r.canonical.facts,
                "reconciliations": r.canonical.reconciliations,
            },
            "authorization": {"actor_auth_uid": ctx.user_id, "permission": "read"},
            "publication": {
                "generation_id": generation,
                "is_current": True,
                "published_at": REFRESHED,
                "posture": asdict(posture),
                "total": "20000",
                "published_imports": r.projection.contributions,
                "included_fact_ids": r.projection.included_fact_ids,
                "published_facts": [
                    dict(f, generation_id=generation, included_in_resolved=True)
                    for f in r.canonical.facts
                ],
            },
        }
    )
    # Backend identities are fixed; browser data never supplies scope or coverage.
    calls = []

    class Client:
        def rpc(self, name, params):
            assert name == "read_aws_financial_contribution_evidence_v1"
            calls.append((name, deepcopy(params)))
            return SimpleNamespace(execute=lambda: SimpleNamespace(data=deepcopy(env)))

    verifier = SimpleNamespace(verify=lambda supplied: supplied == ctx)
    selection = AwsFinancialReadSelection(
        ctx.organization_id, ctx.tenant_id, ctx.user_id, ids, QUERY
    )
    grant = str(uuid4())
    lookups = []

    def existing_grant(op):
        assert op.permission == "read"
        lookups.append(op)
        return grant

    backend = AwsFinancialReadBackend(
        Client(), verifier, lambda supplied: selection, existing_grant
    )
    return ctx, env, calls, lookups, backend


def test_ready_panel_uses_backend_read_only_and_persisted_publication():
    ctx, env, calls, lookups, backend = wire_fixture()
    configure_aws_financial_read_backend(backend)
    ui = UI()
    status = render_aws_financial_publication(ctx, ui=ui)
    assert status.readiness == "READY"
    assert ("AWS total spend", "20,000.00 USD") in ui.values
    assert "Source: AWS canonical financial evidence" in ui.captions
    assert any("2026-07-01 to 2026-07-31" in c for c in ui.captions)
    assert any("import coverage: 2" in c for c in ui.captions)
    assert any(REFRESHED.isoformat() in c for c in ui.captions)
    assert calls[0][1]["organization_id"] == ctx.organization_id
    assert all(op.permission == "read" and op.request_id is None for op in lookups)
    assert len(calls) == 1


@pytest.mark.parametrize(
    "failure",
    [
        "absent_backend",
        "unverified_identity",
        "foreign_selection",
        "foreign_actor",
        "missing_grant",
        "stale",
        "revoked_source",
        "missing_fact",
        "wrong_posture",
        "rpc_failure",
    ],
)
def test_failures_remain_not_ready(failure):
    ctx, env, calls, lookups, backend = wire_fixture()
    if failure == "absent_backend":
        backend = None
    elif failure == "unverified_identity":
        backend = replace(backend, tenant_verifier=SimpleNamespace(verify=lambda c: False))
    elif failure in {"foreign_selection", "foreign_actor"}:
        selection = backend.selection_reader(ctx)
        selection = replace(
            selection,
            **(
                {"organization_id": str(uuid4())}
                if failure == "foreign_selection"
                else {"actor_auth_uid": str(uuid4())}
            ),
        )
        backend = replace(backend, selection_reader=lambda c: selection)
    elif failure == "missing_grant":
        backend = replace(backend, existing_read_grant_lookup=lambda op: None)
    elif failure == "stale":
        env["completeness"] = "INCOMPLETE"
    elif failure == "revoked_source":
        env["sources"][0]["attestation_status"] = "revoked"
    elif failure == "missing_fact":
        env["publication"]["published_facts"] = []
    elif failure == "wrong_posture":
        env["publication"]["posture"]["generated_at"] = OBSERVED.isoformat()
    elif failure == "rpc_failure":

        def fail(*args):
            raise RuntimeError("secret connection details must not reach UI")

        backend = replace(backend, client=SimpleNamespace(rpc=fail))
    configure_aws_financial_read_backend(backend)
    ui = UI()
    status = render_aws_financial_publication(ctx, ui=ui)
    assert status.readiness == "NOT_READY"
    assert status.posture is None and status.published_at is None
    assert ui.values == [("AWS total spend", "UNKNOWN")]
    assert "secret" not in " ".join(ui.warnings)
    if failure in {
        "absent_backend",
        "unverified_identity",
        "foreign_selection",
        "foreign_actor",
        "missing_grant",
    }:
        assert calls == []


def test_scope_is_reverified_and_no_shared_capture_is_reused():
    ctx, env, calls, lookups, backend = wire_fixture()
    configure_aws_financial_read_backend(backend)
    assert aws_financial_dashboard_status(ctx).readiness == "READY"
    env["completeness"] = "INCOMPLETE"
    assert aws_financial_dashboard_status(ctx).readiness == "NOT_READY"
    other = context(str(uuid4()))
    assert aws_financial_dashboard_status(other).readiness == "NOT_READY"
    assert len(calls) == 2


def test_page_client_rejects_refresh_before_transport():
    client = _ReadOnlyFinancialClient(
        SimpleNamespace(rpc=lambda *args: pytest.fail("transport called"))
    )
    with pytest.raises(PermissionError):
        client.rpc("refresh_tenant_cloud_financial_projections_v2", {})


def test_actual_active_workspace_function_routes_verified_context_to_backend():
    ctx, env, calls, lookups, backend = wire_fixture()
    configure_aws_financial_read_backend(backend)
    ui = UI()
    # Malicious browser hints are ignored by AWS backend composition.
    ui.session_state = {
        "authenticated": True,
        "role": "cio",
        "organization_id": str(uuid4()),
        "aws_financial_adapter": "FORGED",
        "authorization_grant_id": str(uuid4()),
    }
    path = Path(__file__).resolve().parents[2] / "shared/executive_page.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    function = next(
        n
        for n in tree.body
        if isinstance(n, ast.FunctionDef) and n.name == "run_executive_workspace"
    )
    rendered = []
    namespace = {
        "st": ui,
        "configure_page": lambda *a, **kw: None,
        "init_session": lambda: None,
        "resolve_active_evidence_context": lambda session: SimpleNamespace(
            is_prospect=False, organization_id=ctx.organization_id
        ),
        "authenticated_tenant_context": lambda session: ctx,
        "render_sidebar_navigation": lambda *a: None,
        "enterprise_spend_service": lambda *args, **kwargs: object(),
        "CanonicalOptimizationService": lambda: object(),
        "EnterpriseIntelligenceQueryService": lambda **kw: object(),
        "ExecutiveWorkspaceCompositionService": SimpleNamespace(
            get_snapshot=lambda *a, **kw: object()
        ),
        "PAGE_PATHS": {},
        "ROLE_PAGES": {},
        "render_workspace": lambda *a, **kw: rendered.append(kw),
        "render_aws_financial_publication": render_aws_financial_publication,
    }
    exec(compile(ast.Module(body=[function], type_ignores=[]), str(path), "exec"), namespace)
    namespace["run_executive_workspace"]("command", "Executive")
    assert ("AWS total spend", "20,000.00 USD") in ui.values
    assert calls[0][1]["organization_id"] == ctx.organization_id
    assert rendered


def test_versioned_rpc_parameter_contracts_match_unchanged_sql():
    import re

    from repositories.aws_financial_evidence_repository import PostgresFinancialRpcClient

    root = Path(__file__).resolve().parents[2]
    text = (root / "database/contracts/nxr_dash_10_financial_evidence.sql").read_text()
    client = PostgresFinancialRpcClient(lambda: pytest.fail("contract check must not connect"))
    for name in (
        "read_aws_financial_contribution_evidence_v1",
        "refresh_tenant_cloud_financial_projections_v2",
    ):
        match = re.search(
            r"create function public\." + name + r"\((.*?)\) returns jsonb", text, re.S
        )
        assert match
        params = {part.strip().split()[0]: None for part in match.group(1).split(",")}
        assert len(params) == (8 if name.startswith("read") else 11)
        # The actual transport checks its exact allowlist before any connection exists.
        assert callable(client.rpc(name, params).execute)
    assert "BLOCKED_D1_D3_D4_D7" in text
    executable = re.sub(r"--[^\n]*", "", text)
    assert re.search(r"\bsecurity\s+definer\b", executable, re.I) is None
