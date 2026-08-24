from __future__ import annotations

import pytest
from streamlit.testing.v1 import AppTest

from components.executive_foundation.badges import BadgeKind, BadgeSpec, badge_html
from components.executive_foundation.states import ComponentState, state_html
from components.executive_foundation.styles import foundation_css


def test_badges_escape_content_and_expose_accessible_semantics():
    markup = badge_html(BadgeSpec(BadgeKind.STATUS, "<Critical>", tone="critical"))
    assert "&lt;Critical&gt;" in markup
    assert 'role="status"' in markup
    assert "aria-label=" in markup
    assert "var(--nexora-status-critical" in markup


@pytest.mark.parametrize("state", list(ComponentState))
def test_every_standard_state_has_semantic_markup(state):
    markup = state_html(state, metadata="Safe reference")
    assert "nexora-state" in markup
    assert 'aria-live="polite"' in markup
    assert "Safe reference" in markup


def test_state_content_is_escaped():
    markup = state_html(ComponentState.ERROR, title="<unsafe>", description="a & b")
    assert "&lt;unsafe&gt;" in markup
    assert "a &amp; b" in markup


def test_foundation_css_includes_responsive_and_reduced_motion_contracts():
    css = foundation_css()
    assert "@media (max-width:767px)" in css
    assert "prefers-reduced-motion: reduce" in css
    assert "--nexora-authority" in css


def test_showcase_renders_for_super_admin():
    app = AppTest.from_file("pages/component_showcase.py", default_timeout=30)
    app.session_state["authenticated"] = True
    app.session_state["role"] = "super_admin"
    app.run()
    assert not app.exception
    assert any("Component Showcase" in item.value for item in app.markdown)


def test_showcase_rejects_non_developer_role():
    app = AppTest.from_file("pages/component_showcase.py", default_timeout=30)
    app.session_state["authenticated"] = True
    app.session_state["role"] = "executive"
    app.run()
    assert not app.exception
    assert any("restricted" in error.value.lower() for error in app.error)
