from __future__ import annotations

import streamlit as st

from components.layout import render_status_badge


def render_certification_banner(*, score: int | float, status: str, scope: str) -> None:
    cols = st.columns([0.72, 0.28])
    with cols[0]:
        st.write(f"**{scope} Certification**")
        st.caption("Architecture, UI, data integrity, evidence, and governance readiness.")
    with cols[1]:
        st.metric("Score", f"{float(score):.0f}/100")
        render_status_badge(status, label=status)
