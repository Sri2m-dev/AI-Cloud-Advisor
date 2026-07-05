from __future__ import annotations

import streamlit as st

from components.layout import render_section


def render_ai_narrative(title: str, narrative: str, *, description: str | None = None) -> None:
    render_section(title, description or "AI-assisted executive interpretation.", divider=True)
    st.write(narrative or "No AI narrative is available.")
