from __future__ import annotations

import streamlit as st

from components.executive_experience import render_workspace
from components.sidebar_navigation import PAGE_PATHS, ROLE_PAGES, render_sidebar_navigation
from services.enterprise_spend_composition import (
    authenticated_tenant_context,
    enterprise_spend_service,
)
from services.executive_workspace_composition_service import (
    ExecutiveWorkspaceCompositionService,
)
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
    authenticated = authenticated_tenant_context(st.session_state)
    snapshot = ExecutiveWorkspaceCompositionService.get_snapshot(
        key,
        authenticated,
        enterprise_spend_service(),
    )
    allowed_page_paths = frozenset(
        PAGE_PATHS[label] for label in ROLE_PAGES.get(role, ()) if label in PAGE_PATHS
    )
    render_workspace(
        key,
        role=role,
        tenant_id=tenant_id,
        allowed_page_paths=allowed_page_paths,
        snapshot=snapshot,
    )
