import streamlit as st
from auth.role_constants import normalize_role

ROLE_PAGES = {
    "super_admin": [
        "Executive Dashboard",
        "Executive Dashboard V2",
        "Cloud Connections",
        "Cost Upload Center",
        "Service Explorer",
        "Leadership Dashboard",
        "Technical Analytics",
        "Operations Workspace",
        "Approval Center",
        "SaaS Governance",
        "Audit Timeline",
        "Reports",
    ],

    "executive": [
        "Executive Dashboard",
        "Executive Dashboard V2",
        "Cloud Connections",
        "Cost Upload Center",
        "Service Explorer",
        "Approval Center",
        "SaaS Governance",
        "Audit Timeline",
        "Reports",
    ],

    "technical": [
        "Executive Dashboard",
        "Executive Dashboard V2",
        "Cloud Connections",
        "Cost Upload Center",
        "Service Explorer",
        "Technical Analytics",
        "Approval Center",
        "SaaS Governance",
        "Audit Timeline",
        "Reports",
    ],

    "finance": [
        "Executive Dashboard",
        "Executive Dashboard V2",
        "Cloud Connections",
        "Cost Upload Center",
        "Operations Workspace",
        "Technical Analytics",
        "SaaS Governance",
        "Audit Timeline",
        "Reports",
    ],
}

PAGE_PATHS = {
    "Executive Dashboard": "pages/executive_dashboard.py",
    "Executive Dashboard V2": "pages/executive_dashboard_v2.py",
    "Cloud Connections": "pages/cloud_connections.py",
    "Cost Upload Center": "pages/cost_upload_center.py",
    "Service Explorer": "pages/service_explorer.py",
    "Leadership Dashboard": "pages/leadership_dashboard.py",
    "Technical Analytics": "pages/technical_analytics.py",
    "Operations Workspace": "pages/operations_workspace.py",
    "Approval Center": "pages/approval_center.py",
    "SaaS Governance": "pages/saas_governance.py",
    "Audit Timeline": "pages/audit_timeline.py",
    "Reports": "pages/reports.py",
}

DEFAULT_ROLE_PAGE = {
    "super_admin": PAGE_PATHS["Executive Dashboard"],
    "executive": PAGE_PATHS["Executive Dashboard"],
    "technical": PAGE_PATHS["Executive Dashboard"],
    "finance": PAGE_PATHS["Operations Workspace"],
}


def get_role_pages(role: str):
    """Return the ordered list of page entries for the given role."""
    normalized_role = normalize_role(role)
    labels = ROLE_PAGES.get(normalized_role, [])

    return [
        (label, PAGE_PATHS[label])
        for label in labels
        if label in PAGE_PATHS
    ]


def render_sidebar_navigation(role: str):
    """Render page links for the current role."""
    pages = get_role_pages(role)

    if not pages:
        st.info("No navigation items available for this role.")
        return

    st.markdown("## Navigation")

    for label, path in pages:
        st.page_link(path, label=label)