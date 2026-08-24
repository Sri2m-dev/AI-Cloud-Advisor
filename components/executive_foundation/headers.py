from __future__ import annotations

from html import escape

import streamlit as st


def render_page_header(
    title: str,
    purpose: str,
    *,
    breadcrumbs: tuple[str, ...] = ("Nexora",),
    persona: str | None = None,
    scope: str | None = None,
    period: str | None = None,
) -> None:
    crumb_text = " / ".join(escape(item) for item in (*breadcrumbs, title) if item)
    meta = [("Persona", persona), ("Scope", scope), ("Period", period)]
    meta_html = "".join(
        f"<span><strong>{label}:</strong> {escape(value)}</span>" for label, value in meta if value
    )
    st.markdown(
        '<header class="nexora-page-heading">'
        f'<nav class="nexora-breadcrumbs" aria-label="Breadcrumb">{crumb_text}</nav>'
        f"<h1>{escape(title)}</h1><p>{escape(purpose)}</p>"
        f'<div class="nexora-page-meta">{meta_html}</div></header>',
        unsafe_allow_html=True,
    )


def render_section_header(
    title: str, description: str | None = None, *, eyebrow: str | None = None
) -> None:
    eyebrow_html = f'<div class="nexora-breadcrumbs">{escape(eyebrow)}</div>' if eyebrow else ""
    description_html = f"<p>{escape(description)}</p>" if description else ""
    st.markdown(
        '<header class="nexora-section-heading"><div>'
        f"{eyebrow_html}<h2>{escape(title)}</h2>{description_html}"
        "</div></header>",
        unsafe_allow_html=True,
    )
