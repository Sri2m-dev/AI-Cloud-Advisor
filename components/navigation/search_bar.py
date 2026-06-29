from __future__ import annotations

import streamlit as st

from components.design_system.icons import icon as resolve_icon


def render_search_bar(
    *,
    placeholder: str = "Search Nexora",
    key: str = "enterprise_search",
) -> str:
    label = resolve_icon("search", "search")
    return st.text_input(label, placeholder=placeholder, key=key, label_visibility="collapsed")
