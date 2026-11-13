from __future__ import annotations

from typing import Any

import streamlit as st

from auth.role_constants import normalize_role
from auth.v1_route_policy import is_v1_page_allowed
from components.sidebar_navigation import PAGE_PATHS, ROLE_PAGES


def v1_page_link(page: str, *, label: str, **kwargs: Any) -> bool:
    role = normalize_role(st.session_state.get("role", ""))
    if not is_v1_page_allowed(
        page,
        role,
        page_paths=PAGE_PATHS,
        role_pages=ROLE_PAGES,
    ):
        return False
    st.page_link(page, label=label, **kwargs)
    return True


def switch_to_v1_page(page: str) -> bool:
    role = normalize_role(st.session_state.get("role", ""))
    if not is_v1_page_allowed(
        page,
        role,
        page_paths=PAGE_PATHS,
        role_pages=ROLE_PAGES,
    ):
        return False
    st.switch_page(page)
    return True
