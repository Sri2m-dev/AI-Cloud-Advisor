from __future__ import annotations

from typing import Any

import streamlit as st

from components.layout import render_section


def render_business_context(context: dict[str, Any]) -> None:
    render_section(
        "Business Architecture Context",
        "Traceability across business, application, technology, and governance layers.",
    )
    metrics = [
        ("Business Units", "business_units"),
        ("Capabilities", "capabilities"),
        ("Business Services", "business_services"),
        ("Business Processes", "business_processes"),
        ("Applications", "applications"),
        ("Technologies", "technologies"),
    ]
    cols = st.columns(6)
    for col, (label, key) in zip(cols, metrics):
        col.metric(label, f"{int(context.get(key) or 0):,}")
