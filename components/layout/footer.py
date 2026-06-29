from __future__ import annotations

from datetime import datetime, timezone

import streamlit as st


def render_footer(
    *,
    product_name: str = "Nexora",
    version: str = "1.0",
    generated_at: str | None = None,
) -> None:
    timestamp = generated_at or datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    st.markdown(
        f"""
        <div class="nexora-footer" style="
            margin-top:2rem;
            padding-top:1rem;
            border-top:1px solid var(--nexora-border);
            color:var(--nexora-text-muted);
            font-size:0.8125rem;
        ">
            {product_name} {version} · Generated {timestamp}
        </div>
        """,
        unsafe_allow_html=True,
    )
