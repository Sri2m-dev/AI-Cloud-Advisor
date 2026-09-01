"""ACT013-DEF-006 explicit workspace routing across production navigation."""

from pathlib import Path
from types import SimpleNamespace

import pytest
from streamlit.testing.v1 import AppTest

from services.demo_tenant_service import DEMO_ORGANIZATION_ID
from shared.evidence_context import EvidenceContextKind


def _app(path: str, monkeypatch) -> AppTest:
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setenv("NEXORA_DEMO_MODE", "true")
    app = AppTest.from_file(path, default_timeout=60)
    app.session_state["authenticated"] = True
    app.session_state["role"] = "executive"
    app.session_state["user"] = "ceo@company.com"
    app.session_state["email"] = "ceo@company.com"
    app.session_state["user_email"] = "ceo@company.com"
    app.session_state["user_id"] = "ceo@company.com"
    app.session_state["organization_id"] = DEMO_ORGANIZATION_ID
    app.session_state["organization_name"] = "Nexora Global Retail (Synthetic Demo)"
    app.session_state["auth_backend"] = "local"
    app.session_state["authorized_organization_ids"] = [DEMO_ORGANIZATION_ID]
    app.session_state["permissions"] = []
    app.session_state["active_workspace_context"] = EvidenceContextKind.DEMO.value
    # Retained authority deliberately remains present while demo presentation is active.
    app.session_state["pue_upload_admission"] = SimpleNamespace(
        fingerprint="retained-cur-fingerprint",
        original_filename="CUR Jan 2026.xlsx",
        scope=SimpleNamespace(prospect_id="prospect-retained"),
        regions=(),
    )
    return app


@pytest.mark.parametrize(
    ("path", "expected"),
    (
        ("pages/business_services.py", "Sample Enterprise · Synthetic Demo"),
    ),
)
def test_demo_context_is_consistent_with_retained_prospect_authority(
    path, expected, monkeypatch
):
    app = _app(path, monkeypatch)
    app.run()
    assert not app.exception
    rendered = "\n".join(
        str(item.value)
        for kind in ("markdown", "caption", "title", "subheader", "info", "warning")
        for item in app.get(kind)
    )
    assert expected in rendered
    assert "TEMPORARY PROSPECT ANALYSIS" not in rendered
    assert app.session_state["pue_upload_admission"].fingerprint == (
        "retained-cur-fingerprint"
    )


def test_home_twin_and_ask_consume_the_authoritative_context_contract():
    root = Path(__file__).parents[2]
    home = (root / "pages" / "welcome.py").read_text(encoding="utf-8")
    twin = (root / "pages" / "twin_explorer.py").read_text(encoding="utf-8")
    ask = (root / "pages" / "enterprise_ai_copilot.py").read_text(encoding="utf-8")
    assert "evidence_context = resolve_active_evidence_context(st.session_state)" in home
    assert "is_demo = evidence_context.is_demo" in home
    assert "if evidence_context.is_demo:" in twin
    assert "if evidence_context.is_demo" in ask


@pytest.mark.parametrize(
    "path",
    ("pages/business_services.py", "pages/twin_explorer.py", "pages/enterprise_ai_copilot.py"),
)
def test_prospect_context_restores_fail_closed_routing(path, monkeypatch):
    app = _app(path, monkeypatch)
    app.session_state["active_workspace_context"] = EvidenceContextKind.PROSPECT.value
    app.run()
    assert not app.exception
    rendered = "\n".join(
        str(item.value)
        for kind in ("markdown", "caption", "title", "subheader", "info", "warning")
        for item in app.get(kind)
    )
    assert "PROSPECT" in rendered
    assert "SYNTHETIC DEMONSTRATION DATA" not in rendered
