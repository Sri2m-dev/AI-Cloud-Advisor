from __future__ import annotations

from collections.abc import Iterable, Sequence
from typing import Any

import streamlit as st

from auth.role_constants import normalize_role
from components.design_system import get_theme
from components.design_system.icons import ICONS, NAVIGATION_SECTIONS, icon as resolve_icon
from components.layout import render_status_badge


SECTION_ORDER = [
    "Home",
    "Executive",
    "Finance",
    "Cloud",
    "Technology",
    "Intelligence",
    "Observability",
    "Governance",
    "Platform",
    "Marketplace",
    "Administration",
    "Settings",
]

SECTION_KEYWORDS = {
    "Executive": ["Executive", "Leadership"],
    "Finance": ["FinOps", "Spend", "Cost", "Budget", "Forecasting", "Chargeback", "Savings", "Financial"],
    "Cloud": ["Cloud", "AWS", "Azure", "GCP"],
    "Technology": ["Technology", "Application", "Business Service", "Service Explorer", "Operations Workspace", "Technical"],
    "Intelligence": ["AI", "Copilot", "Knowledge Graph", "Dependency", "Impact", "Simulation", "Prediction", "Capacity", "Goal", "Agent", "Workflow", "Learning"],
    "Observability": ["Observability", "Incident", "Scheduler", "Performance"],
    "Governance": ["Governance", "Risk", "Approval", "Audit", "Security", "Compliance", "Disaster Recovery", "Readiness", "Data Quality"],
    "Platform": ["Platform", "Connector Health", "Connector Operations", "Data Sources", "Entity Registry"],
    "Marketplace": ["Marketplace", "Connector Studio", "Connector Marketplace"],
    "Administration": ["Administration", "Reports"],
    "Settings": ["Settings"],
}

SIMPLIFIED_ROLE_NAVIGATION: dict[str, list[dict[str, str]]] = {
    "executive": [
        {"label": "Executive Overview", "page_label": "Executive Dashboard", "section": "Home", "icon": "home"},
        {"label": "Executive Dashboard", "page_label": "Executive Dashboard", "section": "Executive", "icon": "executive"},
        {"label": "Enterprise Spend", "page_label": "Enterprise Spend", "section": "Finance", "icon": "finance"},
        {"label": "Approvals", "page_label": "Approvals", "section": "Governance", "icon": "approval"},
        {"label": "Governance", "page_label": "Risk & Governance", "section": "Governance", "icon": "governance"},
        {"label": "Reports", "page_label": "Reports", "section": "Administration", "icon": "reports"},
    ],
    "cio": [
        {"label": "Technology Health", "page_label": "Technology Health & Risk", "section": "Technology", "icon": "technology"},
        {"label": "Technology Inventory", "page_label": "Technology Portfolio", "section": "Technology", "icon": "technology"},
        {"label": "Knowledge Graph", "page_label": "Technology Knowledge Graph", "section": "Intelligence", "icon": "intelligence"},
        {"label": "Applications", "page_label": "Application Portfolio", "section": "Technology", "icon": "technology"},
        {"label": "SaaS Intelligence", "page_label": "SaaS + AI Intelligence", "section": "Technology", "icon": "marketplace"},
        {"label": "Risk & Governance", "page_label": "Risk & Governance", "section": "Governance", "icon": "governance"},
        {"label": "Reports", "page_label": "Reports", "section": "Administration", "icon": "reports"},
    ],
    "technical": [
        {"label": "Operations", "page_label": "Operations Workspace", "section": "Technology", "icon": "platform"},
        {"label": "Observability", "page_label": "Enterprise Observability", "section": "Observability", "icon": "observability"},
        {"label": "Incidents", "page_label": "Incident Timeline", "section": "Observability", "icon": "warning"},
        {"label": "Recommendations", "page_label": "AI Reasoning Center", "section": "Intelligence", "icon": "ai"},
        {"label": "Dependency Analysis", "page_label": "Dependency Analysis", "section": "Intelligence", "icon": "technology"},
        {"label": "Automation", "page_label": "Automation Center", "section": "Platform", "icon": "platform"},
    ],
    "finance": [
        {"label": "Enterprise Spend", "page_label": "Enterprise Spend", "section": "Finance", "icon": "finance"},
        {"label": "Forecasting", "page_label": "Forecasting", "section": "Finance", "icon": "trend_up"},
        {"label": "Savings", "page_label": "Savings Governance", "section": "Finance", "icon": "cost"},
        {"label": "Budget vs Actual", "page_label": "FinOps Dashboard", "section": "Finance", "icon": "finance"},
        {"label": "Reports", "page_label": "Reports", "section": "Administration", "icon": "reports"},
    ],
}


def _section_for_page(label: str) -> str:
    if "Dashboard" in label and "Executive" in label:
        return "Executive"
    for section, keywords in SECTION_KEYWORDS.items():
        if any(keyword.lower() in label.lower() for keyword in keywords):
            return section
    return "Home"


def _roles_for_page(label: str, role_pages: dict[str, Sequence[str]]) -> list[str]:
    roles = [role for role, pages in role_pages.items() if label in pages]
    return roles or ["super_admin"]


def build_navigation_items(
    *,
    page_paths: dict[str, str],
    role_pages: dict[str, Sequence[str]],
) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = {section: [] for section in SECTION_ORDER}
    for label, page in page_paths.items():
        section = _section_for_page(label)
        grouped.setdefault(section, []).append(
            {
                "label": label,
                "icon": resolve_icon(section.lower(), "circle"),
                "page": page,
                "section": section,
                "roles": _roles_for_page(label, role_pages),
                "children": [],
                "badge": None,
                "status": None,
            }
        )

    navigation = []
    section_icons = {item["label"]: item["icon"] for item in NAVIGATION_SECTIONS}
    for section in SECTION_ORDER:
        children = sorted(grouped.get(section, []), key=lambda item: item["label"])
        navigation.append(
            {
                "label": section,
                "icon": section_icons.get(section, ICONS.get(section.lower(), "circle")),
                "page": None,
                "section": section,
                "roles": sorted({role for child in children for role in child["roles"]}),
                "children": children,
                "badge": len(children) if children else None,
                "status": None,
            }
        )
    return navigation


def build_persona_navigation_items(
    *,
    role: str,
    page_paths: dict[str, str],
) -> list[dict[str, Any]]:
    normalized_role = normalize_role(role)
    persona_items = SIMPLIFIED_ROLE_NAVIGATION.get(normalized_role)
    if not persona_items:
        return []

    children = []
    for index, item in enumerate(persona_items):
        page_label = item["page_label"]
        section = item.get("section") or _section_for_page(page_label)
        page = page_paths.get(page_label)
        if not page:
            continue
        children.append(
            {
                "label": item["label"],
                "icon": resolve_icon(item.get("icon", section.lower()), "circle"),
                "page": page,
                "section": section,
                "roles": [normalized_role],
                "children": [],
                "badge": item.get("badge"),
                "status": item.get("status"),
                "order": index,
            }
        )

    if not children:
        return []

    return [
        {
            "label": "Workspace",
            "icon": ICONS.get("home", "home"),
            "page": None,
            "section": "Workspace",
            "roles": [normalized_role],
            "children": sorted(children, key=lambda item: item.get("order", 0)),
            "badge": None,
            "status": None,
        }
    ]


def filter_navigation_by_role(
    items: Iterable[dict[str, Any]],
    role: str,
) -> list[dict[str, Any]]:
    normalized_role = normalize_role(role)
    filtered = []
    for item in items:
        roles = {normalize_role(role_name) for role_name in item.get("roles", [])}
        children = filter_navigation_by_role(item.get("children", []), normalized_role)
        if normalized_role in roles or normalized_role == "super_admin" or children:
            cloned = dict(item)
            cloned["children"] = children
            filtered.append(cloned)
    return filtered


def _render_page_button(item: dict[str, Any], current_page: str) -> None:
    label = item["label"]
    page = item.get("page")
    badge = item.get("badge")
    status = item.get("status")
    active = current_page == page or current_page == label
    button_label = f"{label}  {badge}" if badge and not item.get("children") else label

    if st.button(button_label, key=f"nav_{label}", use_container_width=True, type="primary" if active else "secondary"):
        if page:
            st.session_state["current_page"] = page
            st.switch_page(page)
    if status:
        render_status_badge(status)


def render_enterprise_sidebar(
    role: str,
    *,
    navigation_items: Sequence[dict[str, Any]] | None = None,
    page_paths: dict[str, str] | None = None,
    role_pages: dict[str, Sequence[str]] | None = None,
    active_page: str | None = None,
    show_logout: bool = True,
    theme_mode: str = "light",
) -> list[dict[str, Any]]:
    theme = get_theme(theme_mode)
    if navigation_items is None:
        normalized_role = normalize_role(role)
        if normalized_role == "super_admin":
            navigation_items = build_navigation_items(page_paths=page_paths or {}, role_pages=role_pages or {})
        else:
            navigation_items = build_persona_navigation_items(role=normalized_role, page_paths=page_paths or {})
            if not navigation_items:
                navigation_items = build_navigation_items(page_paths=page_paths or {}, role_pages=role_pages or {})
    visible_items = filter_navigation_by_role(navigation_items, role)
    current_page = active_page or st.session_state.get("current_page", "")

    with st.sidebar:
        st.title("NEXORA")
        st.caption("Next Generation Technology Intelligence")
        st.divider()
        st.write(f"**User:** {st.session_state.get('email') or st.session_state.get('user', '-')}")
        st.write(f"**Role:** {normalize_role(role)}")
        st.write(f"**Organization:** {st.session_state.get('organization_name', 'Demo Enterprise')}")
        st.divider()
        st.subheader("Navigation")
        st.markdown(
            f"<div style='height:{theme.spacing['1']}'></div>",
            unsafe_allow_html=True,
        )

        for section in visible_items:
            children = section.get("children", [])
            if not children:
                continue
            with st.expander(section["label"], expanded=section["label"] in {"Workspace", "Home", "Executive", "Platform"}):
                for child in children:
                    _render_page_button(child, current_page)

        st.divider()
        if show_logout and st.button("Logout", key="sidebar_logout", use_container_width=True):
            st.session_state.clear()
            st.switch_page("pages/login.py")

    return visible_items


def render_navigation(role: str | None = None) -> None:
    if not st.session_state.get("authenticated", False):
        st.page_link("pages/login.py", label="Login")
        return

    selected_role = normalize_role(role or st.session_state.get("role", "viewer"))
    from components.sidebar_navigation import PAGE_PATHS, ROLE_PAGES

    render_enterprise_sidebar(
        selected_role,
        page_paths=PAGE_PATHS,
        role_pages=ROLE_PAGES,
    )
