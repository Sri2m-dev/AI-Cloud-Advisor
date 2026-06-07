"""Enterprise dashboard layout helpers."""

from __future__ import annotations

from shared.components import page_header, section_container, section_header


def render_page_header(title: str, subtitle: str | None = None) -> None:
    page_header(title, subtitle)


def render_section(title: str, description: str | None = None) -> None:
    section_header(title, description)


def render_section_container(title: str, description: str | None = None, *, border: bool = True):
    return section_container(title, description, border=border)

