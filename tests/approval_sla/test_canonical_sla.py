import ast
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from auth.authenticated_tenant import AuthenticatedTenantContext
from repositories.v1_approval_repository import V1ApprovalRepository
from services import approval_service as service
from services.approval_center_certification_service import ApprovalCenterCertificationService
from services.v1_approval_authority import ApprovalRequest, InMemoryApprovalAuthority

A = "11111111-1111-1111-1111-111111111111"
B = "22222222-2222-2222-2222-222222222222"


def context(org=A):
    return AuthenticatedTenantContext(
        org, "Tenant", "user", "user@test.com", "cio", frozenset(), org
    )


def request(state="PENDING", created=None, decision=None, org=A):
    return ApprovalRequest(
        "request",
        org,
        org,
        "subject",
        "action",
        state,
        "user",
        "reason",
        created,
        decision_at=decision,
    )


def configure(monkeypatch, rows):
    authority = SimpleNamespace(list_requests=lambda ctx: tuple(rows))
    monkeypatch.setattr(service, "_V1_APPROVAL_REPOSITORY", V1ApprovalRepository(authority))
    monkeypatch.setattr(service, "_approval_context", context)


@pytest.mark.parametrize(
    "state,created,decision",
    [
        ("COMPLETED", "2026-10-01T00:00:00+00:00", "2026-10-01T01:00:00+00:00"),
        ("COMPLETED", "2026-01-01T00:00:00+00:00", "2026-10-01T00:00:00+00:00"),
        ("PENDING", "2026-01-01T00:00:00+00:00", None),
        ("PENDING", "2026-10-15T00:00:00+00:00", None),
        ("COMPLETED", "2026-10-01T00:00:00+00:00", None),
        ("COMPLETED", None, None),
    ],
)
def test_no_deadline_policy_means_unknown_regardless_of_age(monkeypatch, state, created, decision):
    # Neither apparently fast nor slow decisions prove an SLA without a bound policy.
    def parse(value):
        return datetime.fromisoformat(value) if value else None

    configure(monkeypatch, [request(state, parse(created), parse(decision))])
    result = service.ApprovalService.get_sla_metrics()
    assert result["status"] == "UNKNOWN"
    assert result["total_requests"] == result["unknown_sla"] == 1
    assert result["measured_requests"] == 0
    for key in (
        "sla_compliance",
        "sla_compliance_percent",
        "completed_within_sla",
        "breached_sla",
        "pending_overdue",
        "pending_within_sla",
    ):
        assert result[key] is None
    assert "policy" in result["reason"]


def test_empty_not_perfect(monkeypatch):
    configure(monkeypatch, [])
    result = service.ApprovalService.get_sla_metrics()
    assert result["total_requests"] == result["unknown_sla"] == 0
    assert result["sla_compliance_percent"] is None
    assert result["measured_requests"] == 0


def test_unsupported_policy_not_accepted(monkeypatch):
    row = SimpleNamespace(
        organization_id=A, tenant_id=A, due_date="2099-01-01", sla_policy="invented"
    )
    configure(monkeypatch, [row])
    assert service.ApprovalService.get_sla_metrics()["status"] == "UNKNOWN"


def test_tenant_isolation(monkeypatch):
    authority = InMemoryApprovalAuthority()
    for org in (A, B):
        authority.create_request(
            context(org),
            subject_id="subject",
            requested_action="act",
            requesting_actor="actor",
            reason="reason",
        )
    monkeypatch.setattr(service, "_V1_APPROVAL_REPOSITORY", V1ApprovalRepository(authority))
    monkeypatch.setattr(service, "_approval_context", context)
    assert service.ApprovalService.get_sla_metrics()["total_requests"] == 1
    configure(monkeypatch, [request(org=B)])
    assert service.ApprovalService.get_sla_metrics()["status"] == "NOT_AVAILABLE"


def test_backend_failure_not_zero_breaches(monkeypatch):
    def fail(ctx):
        raise RuntimeError("offline")

    monkeypatch.setattr(service, "_V1_APPROVAL_REPOSITORY", SimpleNamespace(sla_requests=fail))
    monkeypatch.setattr(service, "_approval_context", context)
    result = service.ApprovalService.get_sla_metrics()
    assert result["status"] == "NOT_AVAILABLE"
    assert result["breached_sla"] is None
    assert result["unknown_sla"] is None
    assert result["total_requests"] is None


@pytest.mark.parametrize("status", ["UNKNOWN", "NOT_AVAILABLE"])
def test_active_approval_page_displays_unknown(monkeypatch, status):
    # Execute the actual page content function, substituting only I/O and UI boundaries.
    path = Path(__file__).parents[2] / "pages/approval_center.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    function = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "render_approval_content"
    )
    ui = MagicMock()
    ui.columns.side_effect = lambda count: [MagicMock() for _ in range(count)]
    ui.tabs.side_effect = lambda labels: [MagicMock() for _ in labels]
    cards = MagicMock()
    metrics = dict(pending=0, approved=0, rejected=0, escalated=0, total=0)
    stages = dict(finance=0, cio=0, ceo=0, pmo=0, completed=0)
    api = SimpleNamespace(
        get_dashboard_metrics=lambda: metrics,
        get_workflow_stage_metrics=lambda: stages,
        get_overdue_approvals=lambda: [],
        get_all_approvals=lambda: [],
        get_pending_approvals=lambda role: [],
        get_sla_metrics=lambda: dict(
            status=status, sla_compliance_percent=None, reason="Missing evidence"
        ),
    )
    namespace = {
        "st": ui,
        "ApprovalService": api,
        "ApprovalCenterCertificationService": ApprovalCenterCertificationService,
        "current_role": "cio",
        "is_ceo_view": False,
        "render_metric_card": cards,
    }
    import pandas as pd

    namespace["pd"] = pd
    for node in ast.walk(function):
        if isinstance(node, ast.Name) and node.id.startswith("render_"):
            namespace.setdefault(node.id, MagicMock())
    exec(compile(ast.Module(body=[function], type_ignores=[]), str(path), "exec"), namespace)
    namespace["render_approval_content"]()
    sla_card = next(call for call in cards.call_args_list if call.args[0] == "SLA %")
    assert sla_card.args[1] == status
    assert sla_card.kwargs["status"] != "healthy"
    overdue = next(call for call in cards.call_args_list if call.args[0] == "Overdue")
    assert overdue.args[1] == status
    ui.info.assert_called_with("Missing evidence")


def test_risk_consumer_keeps_unknown_in_metrics_and_summary():
    import pandas as pd

    from services.risk_governance_certification_service import (
        RiskGovernanceCertificationService as Risk,
    )

    empty = pd.DataFrame()
    metrics = Risk._metrics(empty, empty, empty, {}, {"sla_compliance": None}, [])
    assert metrics["sla_compliance"] is None
    assert metrics["governance_score"] is None
    assert "SLA compliance is UNKNOWN" in Risk._executive_summary(metrics, {}, {}, {})
    # Execute the actual page's SLA card expressions without loading its other dashboards.
    tree = ast.parse(
        (Path(__file__).parents[2] / "pages/risk_governance.py").read_text(encoding="utf-8")
    )
    card = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Dict)
        and any(
            isinstance(value, ast.Constant) and value.value == "SLA Compliance"
            for value in node.values
        )
    )
    result = eval(
        compile(ast.Expression(body=card), "risk-page", "eval"),
        {
            "sla_compliance": None,
            "RiskGovernanceCertificationService": Risk,
        },
    )
    assert result["value"] == "UNKNOWN"
    assert result["status"] == "warning"


def test_canonical_query_scopes_both_tenant_columns_and_never_writes():
    from services.v1_approval_authority import SupabaseApprovalAuthority

    query = MagicMock()
    for operation in ("select", "eq", "order"):
        getattr(query, operation).return_value = query
    query.execute.return_value = SimpleNamespace(data=[])
    client = SimpleNamespace(table=MagicMock(return_value=query))
    assert V1ApprovalRepository(SupabaseApprovalAuthority(client)).sla_requests(context()) == ()
    client.table.assert_called_once_with("nexora_v1_approval_requests")
    assert query.eq.call_args_list[0].args == ("organization_id", A)
    assert query.eq.call_args_list[1].args == ("tenant_id", A)
    query.insert.assert_not_called()
    query.update.assert_not_called()


def test_auth_failure_is_unavailable(monkeypatch):
    def denied():
        raise PermissionError("unauthenticated")

    monkeypatch.setattr(service, "_approval_context", denied)
    assert service.ApprovalService.get_sla_metrics()["status"] == "NOT_AVAILABLE"
