"""Bounded regressions discovered during v1.1 commercial acceptance."""

import sqlite3
from uuid import uuid4

import pytest
from streamlit.testing.v1 import AppTest

from data_fabric.foundation import TenantContext
from enterprise_copilot.composition import enterprise_ai_copilot
from enterprise_copilot.models import CopilotRequest


@pytest.mark.parametrize("role", ["client_admin", "super_admin"])
def test_optional_scenario_policy_does_not_block_authorized_ask(tmp_path, monkeypatch, role):
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    organization = str(uuid4())
    context = TenantContext(organization, organization)

    def connection():
        conn = sqlite3.connect(tmp_path / "empty-customer.db")
        conn.row_factory = sqlite3.Row
        return conn

    copilot = enterprise_ai_copilot(
        context,
        role=role,
        environment="development",
        supabase_url="",
        supabase_key="",
        connection_factory=connection,
    )
    response = copilot.ask(CopilotRequest(context, "hello", role, "synthetic-session"))
    assert not response.blocked
    assert response.unsupported
    assert not response.citations
    if role == "client_admin":
        assert copilot.scenario_service is None
        with pytest.raises(RuntimeError, match="ScenarioService is not configured"):
            copilot.explain_scenario(CopilotRequest(context, "hello", role, "session"), None)
    else:
        assert copilot.scenario_service is not None


def test_profile_logout_clears_all_tenant_and_role_state(monkeypatch):
    import streamlit as st

    destinations = []
    monkeypatch.setattr(st, "switch_page", destinations.append)
    app = AppTest.from_string(
        "from components.navigation.profile_menu import render_profile_menu\n"
        "render_profile_menu()\n"
    )
    identity = {
        "authenticated": True,
        "email": "synthetic@example.test",
        "role": "client_admin",
        "organization_id": str(uuid4()),
        "organization_name": "Synthetic Customer",
        "authorized_organization_ids": [str(uuid4())],
        "prospect_context": "synthetic-old-context",
    }
    for key, value in identity.items():
        app.session_state[key] = value
    app.run()
    app.button(key="profile_logout").click().run()
    assert not app.exception
    assert destinations == ["pages/login.py"]
    for key in identity:
        assert key not in app.session_state
