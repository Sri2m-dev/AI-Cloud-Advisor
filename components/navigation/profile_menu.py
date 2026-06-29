from __future__ import annotations

import streamlit as st

from auth.role_constants import normalize_role


def render_profile_menu(*, show_logout: bool = True) -> None:
    email = st.session_state.get("email") or st.session_state.get("user") or "Unknown user"
    role = normalize_role(st.session_state.get("role") or "viewer")
    organization = st.session_state.get("organization_name", "Demo Enterprise")

    menu = st.popover if hasattr(st, "popover") else st.expander
    with menu("Profile"):
        st.write(f"**{email}**")
        st.caption(f"Role: {role}")
        st.caption(f"Workspace: {organization}")
        if show_logout and st.button("Logout", key="profile_logout", use_container_width=True):
            st.session_state.clear()
            st.switch_page("pages/login.py")
