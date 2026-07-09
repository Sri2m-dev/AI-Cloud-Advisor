from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st

from components.layout import render_section
from shared.streamlit_compat import dataframe


def _render_dataframe(rows: Any, empty_message: str) -> None:
    df = rows if isinstance(rows, pd.DataFrame) else pd.DataFrame(rows or [])
    if df.empty:
        st.info(empty_message)
        return
    dataframe(df, hide_index=True)


def render_evidence_panel(evidence: dict[str, Any]) -> None:
    render_section(
        "Evidence",
        "Standard certification evidence for source data, coverage, relationships, financial reconciliation, and interpretation.",
    )
    sections = [
        ("Source Data", "source_data", "No source data evidence is available."),
        ("Data Coverage", "data_coverage", "No data coverage evidence is available."),
        ("Relationship Summary", "relationship_summary", "No relationship summary evidence is available."),
        ("Financial Reconciliation", "financial_reconciliation", "No financial reconciliation evidence is available."),
    ]
    for label, key, empty_message in sections:
        with st.expander(label, expanded=False):
            _render_dataframe(evidence.get(key), empty_message)

    with st.expander("AI Interpretation", expanded=False):
        st.write(evidence.get("ai_interpretation") or "No AI interpretation is available.")

    with st.expander("Raw Evidence", expanded=False):
        raw = evidence.get("raw_evidence") or {}
        if not raw:
            st.info("No raw evidence is available.")
        for label, rows in raw.items():
            st.markdown(f"**{label}**")
            _render_dataframe(rows, f"No {label.lower()} evidence is available.")
