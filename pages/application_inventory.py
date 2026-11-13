"""Authenticated canonical Application Portfolio page."""

from __future__ import annotations

import streamlit as st

from components.layout import render_page
from components.navigation import render_enterprise_sidebar
from components.sidebar_navigation import PAGE_PATHS, ROLE_PAGES
from services.application_portfolio_service import ApplicationPortfolioService
from services.enterprise_spend_composition import authenticated_tenant_context
from shared.auth import require_role
from shared.session import init_session
from shared.streamlit_compat import dataframe
from shared.styles import configure_page


def render_application_content():
    try:
        context = authenticated_tenant_context(st.session_state)
    except PermissionError:
        st.error("Application portfolio unavailable: authenticated tenant could not be verified.")
        return
    except Exception:
        st.error("Application portfolio unavailable: tenant context could not be resolved.")
        return
    portfolio = ApplicationPortfolioService.get_portfolio(context)
    if portfolio["status"] == "NOT_AVAILABLE":
        st.warning("Application portfolio NOT_AVAILABLE: canonical inventory could not be read.")
    elif not portfolio["applications"]:
        st.info("No canonical applications are registered for this tenant.")
    else:
        st.metric("Applications", len(portfolio["applications"]))
        dataframe(portfolio["applications"], hide_index=True)
    st.info("Application spend: UNKNOWN. " + portfolio["financial"]["reason"])


configure_page(page_title="Application Portfolio", page_icon="A")
init_session()
require_role(["executive", "cio", "super_admin"])
render_enterprise_sidebar(
    st.session_state.get("role", "cio"),
    page_paths=PAGE_PATHS,
    role_pages=ROLE_PAGES,
    active_page=PAGE_PATHS["Application Portfolio"],
)
render_page(
    title="Applications",
    description="Canonical tenant application inventory and financial attribution availability.",
    breadcrumbs=["Home", "CIO", "Applications"],
    content=render_application_content,
    status="info",
)
