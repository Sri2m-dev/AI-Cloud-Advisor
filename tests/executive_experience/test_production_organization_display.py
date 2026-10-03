from pathlib import Path
from types import SimpleNamespace

import streamlit as st
from streamlit.testing.v1 import AppTest

from services import enterprise_spend_composition
import shared.executive_page as executive_page

ROOT = Path(__file__).resolve().parents[2]
ORGANIZATION_ID = "71cf875a-2103-47a0-8886-41a97c5750ec"


class FakeOrganizationQuery:
    def select(self, columns):
        assert columns == "id,name"
        return self

    def eq(self, column, value):
        assert column == "id"
        assert value == ORGANIZATION_ID
        return self

    def limit(self, count):
        assert count == 1
        return self

    def execute(self):
        return SimpleNamespace(data=[{"id": ORGANIZATION_ID, "name": "Default Org"}])


class FakeSupabaseClient:
    def table(self, name):
        assert name == "organizations"
        return FakeOrganizationQuery()


def test_command_center_resolves_authoritative_name_before_sidebar(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("NEXORA_DEMO_MODE", "false")
    monkeypatch.setattr(enterprise_spend_composition, "supabase", FakeSupabaseClient())
    monkeypatch.setattr(
        executive_page,
        "resolve_active_evidence_context",
        lambda session: SimpleNamespace(organization_id=ORGANIZATION_ID, is_prospect=False),
    )
    monkeypatch.setattr(executive_page, "enterprise_spend_service", lambda: object())
    monkeypatch.setattr(executive_page, "CanonicalOptimizationService", lambda: object())
    monkeypatch.setattr(
        executive_page, "EnterpriseIntelligenceQueryService", lambda **kwargs: object()
    )
    monkeypatch.setattr(
        executive_page.ExecutiveWorkspaceCompositionService,
        "get_snapshot",
        staticmethod(lambda *args, **kwargs: object()),
    )
    monkeypatch.setattr(executive_page, "render_workspace", lambda *args, **kwargs: None)

    sidebar_organization_names = []
    render_sidebar = executive_page.render_sidebar_navigation

    def capture_sidebar_organization(role):
        sidebar_organization_names.append(st.session_state.get("organization_name"))
        return render_sidebar(role)

    monkeypatch.setattr(executive_page, "render_sidebar_navigation", capture_sidebar_organization)

    app = AppTest.from_file(str(ROOT / "pages" / "executive_command_center.py"), default_timeout=30)
    app.session_state["authenticated"] = True
    app.session_state["role"] = "super_admin"
    app.session_state["email"] = "admin@company.com"
    app.session_state["user_id"] = "auth-user-id"
    app.session_state["organization_id"] = ORGANIZATION_ID
    app.session_state["org_id"] = ORGANIZATION_ID
    app.session_state["profile"] = {"email": "admin@company.com", "org_id": ORGANIZATION_ID}
    app.run()

    assert not app.exception
    assert app.session_state["organization_id"] == ORGANIZATION_ID
    assert app.session_state["organization_name"] == "Default Org"
    assert sidebar_organization_names == ["Default Org"]
    rendered_sidebar = "\n".join(str(element.value) for element in app.get("markdown"))
    assert "Default Org" in rendered_sidebar
    assert "Demo Enterprise" not in rendered_sidebar