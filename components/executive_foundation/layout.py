from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from typing import Any

import streamlit as st

from components.executive_foundation.styles import inject_foundation_styles


@contextmanager
def render_executive_shell(*, theme_mode: str = "light") -> Iterator[None]:
    inject_foundation_styles(theme_mode)
    st.markdown('<main class="nexora-executive-shell">', unsafe_allow_html=True)
    try:
        yield
    finally:
        st.markdown("</main>", unsafe_allow_html=True)


def executive_columns(count: int, *, gap: str = "medium") -> list[Any]:
    if count not in {1, 2, 3, 4, 8, 12}:
        raise ValueError("Executive grid supports 1, 2, 3, 4, 8, or 12 columns")
    return st.columns(count, gap=gap)


def render_in_shell(content: Callable[[], Any], *, theme_mode: str = "light") -> Any:
    with render_executive_shell(theme_mode=theme_mode):
        return content()
