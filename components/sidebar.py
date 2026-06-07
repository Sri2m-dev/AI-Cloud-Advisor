import streamlit as st
from components.navigation import render_navigation


def render_sidebar(user_role: str = None, role: str = None):
    """Render a modern branded sidebar and the app navigation.

    This intentionally keeps behavior simple and delegates page links to
    `components.navigation.render_navigation()` so navigation is centralized.
    """
    user = st.session_state.get("user", "Unknown")
    selected_role = st.session_state.get("role", role or user_role or "Unknown")
    organization = st.session_state.get("organization_name", "Demo Enterprise")

    with st.sidebar:
        st.markdown("# AI Cloud Advisor")
        st.markdown("#### Enterprise Cloud Governance")
        st.markdown("---")
        st.markdown(
            f"**User:** {user}  \n"
            f"**Role:** {selected_role}  \n"
            f"**Organization:** {organization}"
        )
        st.markdown("---")
        render_navigation()

