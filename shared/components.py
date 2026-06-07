"""Reusable enterprise Streamlit components."""

from __future__ import annotations

from collections.abc import Sequence
from html import escape
from typing import Any

import streamlit as st

from shared.styles import apply_enterprise_styles


def page_header(title: str, subtitle: str | None = None) -> None:
    """Render page header."""
    apply_enterprise_styles()

    st.markdown(
        f"""
        <div class="enterprise-page-header">
            <h1>{escape(title)}</h1>
            {"<p>" + escape(subtitle) + "</p>" if subtitle else ""}
        </div>
        """,
        unsafe_allow_html=True,
    )


def section_header(title: str, description: str | None = None) -> None:
    """Render section header."""
    apply_enterprise_styles()

    st.markdown(
        f"""
        <div class="enterprise-section">
            <h2>{escape(title)}</h2>
            {"<p>" + escape(description) + "</p>" if description else ""}
        </div>
        """,
        unsafe_allow_html=True,
    )


def section_container(
    title: str,
    description: str | None = None,
    *,
    border: bool = True,
):
    """Section container."""
    section_header(title, description)
    return st.container(border=border)


def kpi_cards(metrics: Sequence[dict[str, Any]]) -> None:
    """
    Enterprise KPI cards.
    Uses Streamlit columns instead of raw HTML.
    """

    apply_enterprise_styles()

    if not metrics:
        return

    cols = st.columns(len(metrics))

    for col, metric in zip(cols, metrics):

        label = str(metric.get("label", ""))
        value = str(metric.get("value", ""))
        delta = metric.get("delta")

        with col:
            st.markdown(
                f"""
                <div class="enterprise-kpi-card">
                    <div class="enterprise-kpi-label">{escape(label)}</div>
                    <div class="enterprise-kpi-value">{escape(value)}</div>
                    {
                        f'<div class="enterprise-kpi-delta">{escape(str(delta))}</div>'
                        if delta else ""
                    }
                </div>
                """,
                unsafe_allow_html=True,
            )


def info_panel(content: str) -> None:
    """Reusable information panel."""

    apply_enterprise_styles()

    with st.container(border=True):
        st.markdown(content)