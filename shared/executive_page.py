from __future__ import annotations

import streamlit as st

from components.executive_experience import render_workspace
from components.sidebar_navigation import PAGE_PATHS, ROLE_PAGES, render_sidebar_navigation
from shared.session import init_session
from shared.styles import configure_page


def run_executive_workspace(key: str, title: str) -> None:
    configure_page(title, page_icon=":material/space_dashboard:", layout="wide")
    init_session()
    if not st.session_state.get("authenticated"):
        st.switch_page("pages/login.py")
        st.stop()
    role = str(st.session_state.get("role") or "")
    tenant_id = str(
        st.session_state.get("organization_id") or st.session_state.get("org_id") or "UNKNOWN"
    )
    if tenant_id == "UNKNOWN":
        st.error("An authenticated tenant context is required.")
        st.stop()
    render_sidebar_navigation(role)
    allowed_page_paths = frozenset(
        PAGE_PATHS[label] for label in ROLE_PAGES.get(role, ()) if label in PAGE_PATHS
    )
    render_workspace(
        key,
        role=role,
        tenant_id=tenant_id,
        allowed_page_paths=allowed_page_paths,
    )
