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
from shared.currency import format_currency_amount
from shared.evidence_context import resolve_active_evidence_context


def _render_prospect_workspace(key: str, analysis: object) -> None:
    currency = getattr(analysis, "currency", None)
    unresolved = bool(getattr(analysis, "currency_resolution_required", True))
    st.caption("TEMPORARY PROSPECT ANALYSIS · PROSPECT EVIDENCE ONLY")
    if unresolved:
        st.warning("Currency could not be determined from the uploaded evidence.")
        st.page_link("pages/analyze_environment.py", label="Resolve currency")
        return

    total = format_currency_amount(getattr(analysis, "total_spend", 0), currency)
    qualified = format_currency_amount(
        getattr(analysis, "opportunity_evidence_qualified", 0), currency
    )
    title = {
        "ceo": "Prospect Executive Brief",
        "cfo": "Prospect Investment & Value",
    }.get(key, "Prospect Evidence Summary")
    st.title(title)
    metrics = st.columns(4)
    metrics[0].metric("Observed spend", total)
    metrics[1].metric("Evidence rows", f"{getattr(analysis, 'row_count', 0):,}")
    metrics[2].metric(
        "Evidence coverage", f"{getattr(analysis, 'evidence_coverage', 0):.1f}%"
    )
    metrics[3].metric("Evidence-qualified opportunity", qualified)
    st.info(
        "Observed spend and evidence coverage come from the current uploaded analysis. "
        "Forecast, realized value, service health, risk, and portfolio decisions are UNKNOWN "
        "unless supported by prospect evidence."
    )


def run_executive_workspace(key: str, title: str) -> None:
    configure_page(title, page_icon=":material/space_dashboard:", layout="wide")
    init_session()
    if not st.session_state.get("authenticated"):
        st.switch_page("pages/login.py")
        st.stop()
    role = str(st.session_state.get("role") or "")
    evidence_context = resolve_active_evidence_context(st.session_state)
    tenant_id = str(
        evidence_context.organization_id
        or st.session_state.get("organization_id")
        or st.session_state.get("org_id")
        or "UNKNOWN"
    )
    if tenant_id == "UNKNOWN":
        st.error("An authenticated tenant context is required.")
        st.stop()
    render_sidebar_navigation(role)
    if evidence_context.is_prospect:
        _render_prospect_workspace(key, evidence_context.prospect_analysis)
        return
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
