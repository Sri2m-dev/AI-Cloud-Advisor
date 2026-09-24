"""ACT-013 import and Streamlit route smoke for the real production workflow."""

import importlib
from pathlib import Path
from types import SimpleNamespace

from streamlit.testing.v1 import AppTest

from auth.authenticated_tenant import AuthenticatedTenantContext
from services.demo_tenant_service import DEMO_ORGANIZATION_ID, DEMO_ORGANIZATION_NAME

from services.prospect_data_intake_service import ProspectTenant
from universal_evidence.pilot import admit_uploaded_evidence
from universal_evidence.pilot.production_render import render_reconciliation
from universal_evidence.pilot.production_views import (
    build_enterprise_context,
    build_reconciliation_view,
)
from universal_evidence.production_workflow import activate_production_workflow


def _demo_tenant_context():
    return AuthenticatedTenantContext(
        organization_id=DEMO_ORGANIZATION_ID,
        organization_name=DEMO_ORGANIZATION_NAME,
        user_id="ceo@company.com",
        user_email="ceo@company.com",
        role="executive",
        authorization_claims=frozenset(),
        tenant_id=DEMO_ORGANIZATION_ID,
    )


def test_production_view_and_render_dependency_graph_imports():
    for module in (
        "universal_evidence.pilot.production_views",
        "universal_evidence.pilot.production_render",
    ):
        assert importlib.import_module(module)


def test_analyze_environment_route_renders_without_import_exception(monkeypatch, tmp_path):
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setenv("NEXORA_DEMO_MODE", "true")
    monkeypatch.setenv("PUE_PILOT_DEV_MODE", "false")
    monkeypatch.setenv("NEXORA_PROSPECT_DATA_ROOT", str(tmp_path / "prospect"))
    app = AppTest.from_file("pages/analyze_environment.py", default_timeout=30)
    app.session_state["authenticated"] = True
    app.session_state["role"] = "executive"
    app.session_state["user"] = "ceo@company.com"
    app.session_state["email"] = "ceo@company.com"
    app.session_state["user_email"] = "ceo@company.com"
    app.session_state["user_id"] = "ceo@company.com"
    app.session_state["organization_id"] = DEMO_ORGANIZATION_ID
    app.session_state["organization_name"] = DEMO_ORGANIZATION_NAME
    app.session_state["auth_backend"] = "local"
    app.session_state["authorized_organization_ids"] = [DEMO_ORGANIZATION_ID]
    app.session_state["permissions"] = []
    app.run()
    assert not app.exception
    assert app.markdown or app.button or app.get("file_uploader")


def test_empty_reconciliation_state_renders_without_authority_or_controls():
    messages = []
    streamlit = SimpleNamespace(
        markdown=lambda value: messages.append(value),
        info=lambda value: messages.append(value),
    )
    render_reconciliation(streamlit, build_reconciliation_view())
    assert messages == [
        "### Source Reconciliation",
        "Reconciliation becomes available when multiple governed evidence sources "
        "describe the same enterprise environment.",
    ]


def test_synthetic_cur_zero_governance_route_renders_through_reconciliation(
    monkeypatch, tmp_path
):
    """DEF-003: exercise a complete valid synthetic post-admission empty state."""
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setenv("NEXORA_DEMO_MODE", "true")
    monkeypatch.setenv("PUE_PILOT_DEV_MODE", "false")
    monkeypatch.setenv("NEXORA_PROSPECT_DATA_ROOT", str(tmp_path / "prospect"))
    workbook = Path("tests/fixtures/cmp_p1/fixture_a_cloud_cost.xlsx")
    tenant = ProspectTenant(
        "prospect-act013-def003",
        "audit-act013-def003",
        "2026-08-31T00:00:00+00:00",
        "2026-09-30T00:00:00+00:00",
        30,
    )
    admission = admit_uploaded_evidence(
        tenant,
        filename=workbook.name,
        content=workbook.read_bytes(),
        tenant_context=_demo_tenant_context(),
    )
    activate_production_workflow(admission)
    app = AppTest.from_file("pages/analyze_environment.py", default_timeout=60)
    app.session_state["authenticated"] = True
    app.session_state["role"] = "executive"
    app.session_state["user"] = "ceo@company.com"
    app.session_state["email"] = "ceo@company.com"
    app.session_state["user_email"] = "ceo@company.com"
    app.session_state["user_id"] = "ceo@company.com"
    app.session_state["organization_id"] = DEMO_ORGANIZATION_ID
    app.session_state["organization_name"] = DEMO_ORGANIZATION_NAME
    app.session_state["auth_backend"] = "local"
    app.session_state["authorized_organization_ids"] = [DEMO_ORGANIZATION_ID]
    app.session_state["permissions"] = []
    app.session_state["analysis_start_path"] = "upload"
    app.session_state["pue_upload_admission"] = admission
    app.session_state["prospect_analysis_error"] = "Legacy parser compatibility notice"
    app.session_state["pue_enterprise_context_view"] = (
        admission.fingerprint,
        build_enterprise_context(()),
    )
    app.session_state["pue_reconciliation_view"] = (
        admission.fingerprint,
        build_reconciliation_view(),
    )
    app.run()

    assert not app.exception
    metrics = {(item.label, str(item.value)) for item in app.metric}
    assert ("Detail records", "3") in metrics
    assert ("Fields discovered", "7") in metrics
    rendered = str(app.main) + "\n" + "\n".join(
        str(item.value)
        for element_type in (
            "markdown",
            "subheader",
            "caption",
            "info",
            "warning",
            "error",
        )
        for item in app.get(element_type)
    )
    for expected in (
        "Evidence overview",
        "DISCOVER & UNDERSTAND",
        "REVIEW MAPPINGS",
        "Data Quality",
        "REVIEW AVAILABLE INSIGHTS",
        "Enterprise Context",
        "No governed enterprise entities",
        "Source Reconciliation",
        "Reconciliation becomes available",
    ):
        assert expected in rendered


def test_active_workspace_can_return_to_source_selection_without_mutation(monkeypatch, tmp_path):
    """DEF-005: navigation leaves durable/resumable authority untouched."""
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setenv("NEXORA_DEMO_MODE", "true")
    monkeypatch.setenv("PUE_PILOT_DEV_MODE", "false")
    monkeypatch.setenv("NEXORA_PROSPECT_DATA_ROOT", str(tmp_path / "prospect"))
    workbook = Path("tests/fixtures/cmp_p1/fixture_a_cloud_cost.xlsx")
    admission = admit_uploaded_evidence(
        ProspectTenant(
            "prospect-act013-def005",
            "audit-act013-def005",
            "2026-08-31T00:00:00+00:00",
            "2026-09-30T00:00:00+00:00",
            30,
        ),
        filename=workbook.name,
        content=workbook.read_bytes(),
    )
    app = AppTest.from_file("pages/analyze_environment.py", default_timeout=60)
    app.session_state["authenticated"] = True
    app.session_state["role"] = "executive"
    app.session_state["user"] = "ceo@company.com"
    app.session_state["email"] = "ceo@company.com"
    app.session_state["user_email"] = "ceo@company.com"
    app.session_state["user_id"] = "ceo@company.com"
    app.session_state["organization_id"] = DEMO_ORGANIZATION_ID
    app.session_state["organization_name"] = DEMO_ORGANIZATION_NAME
    app.session_state["auth_backend"] = "local"
    app.session_state["authorized_organization_ids"] = [DEMO_ORGANIZATION_ID]
    app.session_state["permissions"] = []
    app.session_state["analysis_start_path"] = "upload"
    app.session_state["pue_upload_admission"] = admission
    app.run()

    leave = next(button for button in app.button if button.label == "← Choose another source")
    leave.click().run()

    assert not app.exception
    labels = {button.label for button in app.button}
    assert {
        "Configure AWS →",
        "Configure Azure →",
        "Choose files →",
        "Launch Sample Enterprise →",
    }.issubset(labels)
    assert app.session_state["pue_upload_admission"].fingerprint == admission.fingerprint
    assert "analysis_start_path" not in app.session_state
