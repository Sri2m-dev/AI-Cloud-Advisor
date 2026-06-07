
import streamlit as st
from auth.role_constants import normalize_role
from components.sidebar_navigation import render_sidebar_navigation

def render_navigation():
    authenticated = st.session_state.get("authenticated", False)
    if not authenticated:
        st.page_link("pages/login.py", label="Login")
        return

    role = normalize_role(st.session_state.get("role", ""))
    render_sidebar_navigation(role)

    st.divider()
    if st.button("Logout"):
        st.session_state.authenticated = False
        st.switch_page("pages/login.py")

