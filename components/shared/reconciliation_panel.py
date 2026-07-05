from __future__ import annotations

from typing import Any

import streamlit as st

from components.layout import render_section


def render_reconciliation_panel(cards: dict[str, Any]) -> None:
    render_section(
        "Data Reconciliation Status",
        "Canonical allocation and variance posture from the Enterprise Financial Model.",
    )
    cols = st.columns(5)
    cols[0].metric("Status", cards.get("status", "Unknown"))
    cols[1].metric("Allocation Coverage", cards.get("allocation_coverage_display", "0.0%"))
    cols[2].metric("Allocated Spend", cards.get("allocated_spend_display", "$0"))
    cols[3].metric("Unallocated Spend", cards.get("unallocated_spend_display", "$0"))
    cols[4].metric("Variance Status", cards.get("variance_status", "Unknown"))
