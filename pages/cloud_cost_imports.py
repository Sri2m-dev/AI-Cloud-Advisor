"""Read-only, tenant-scoped Cloud Cost Import history."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from auth.authenticated_tenant import AuthenticatedTenantError
from components.layout import render_page, render_section
from components.navigation import render_enterprise_sidebar
from components.sidebar_navigation import PAGE_PATHS, ROLE_PAGES
from services.enterprise_spend_composition import (
    authenticated_tenant_context,
    enterprise_spend_service,
)
from shared.auth import require_role
from shared.session import init_session
from shared.styles import configure_page

configure_page(page_title="Cloud Cost Imports | Nexora", page_icon="cloud")
init_session()
require_role(["executive", "cio", "finance", "super_admin"])

try:
    tenant = authenticated_tenant_context(st.session_state)
    imports = enterprise_spend_service().get_import_history(tenant)
except AuthenticatedTenantError as exc:
    st.error(f"Cloud cost imports unavailable: {exc}")
    st.stop()

role = st.session_state.get("role", "Unknown")
render_enterprise_sidebar(
    role,
    page_paths=PAGE_PATHS,
    role_pages=ROLE_PAGES,
    active_page=PAGE_PATHS["Cloud Cost Imports"],
)


def render_content() -> None:
    st.caption(f"Organization: {tenant.organization_name}")
    render_section(
        "Import History",
        "Read-only canonical cloud cost imports, reconciliation, and replay state.",
        divider=False,
    )
    if not imports:
        st.info("No cloud cost imports are available for this organization.")
        return
    columns = [
        "import_id",
        "provider",
        "source_filename",
        "payer_account_id",
        "status",
        "source_rows",
        "persisted_facts",
        "total_unblended_spend",
        "total_blended_spend",
        "reconciliation_variance",
        "reconciliation_status",
        "unknown_account_count",
        "resolved_account_count",
        "billing_period_start",
        "billing_period_end",
        "started_at",
        "completed_at",
        "replay_state",
    ]
    frame = pd.DataFrame(imports)
    st.dataframe(
        frame[[column for column in columns if column in frame.columns]],
        use_container_width=True,
    )


render_page(
    title="Cloud Cost Imports",
    description="Tenant-authorized import evidence without raw CUR disclosure.",
    content=render_content,
)
