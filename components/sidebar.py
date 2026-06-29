import streamlit as st
from auth.role_constants import normalize_role
from components.navigation import render_navigation


def render_sidebar(user_role: str = None, role: str = None):
    """Render a modern branded sidebar and the app navigation.

    This intentionally keeps behavior simple and delegates page links to
    `components.navigation.render_navigation()` so navigation is centralized.
    """
    selected_role = normalize_role(st.session_state.get("role", role or user_role or "viewer"))
    render_navigation(selected_role)

