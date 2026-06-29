from __future__ import annotations

import pandas as pd
import streamlit as st

from auth.guards import require_login
from auth.role_constants import normalize_role
from components.sidebar_navigation import render_sidebar_navigation
from services.connector_service import ConnectorService


st.set_page_config(page_title="Data Sources & Connectors", layout="wide")


def _show_dataframe(df: pd.DataFrame, empty_message: str) -> None:
    if df.empty:
        st.info(empty_message)
        return
    st.dataframe(df, use_container_width=True, hide_index=True)


def main() -> None:
    user = require_login()
    role = normalize_role(st.session_state.get("role") or user.get("role") or "cio")
    render_sidebar_navigation(role)

    st.title("Data Sources & Connectors")
    st.caption("Live source connectivity for automatic Nexora portfolio, spend, governance, and Digital Twin population")

    kpis = ConnectorService.get_connector_kpis()
    cols = st.columns(4)
    cols[0].metric("Connected Connectors", kpis["Connected Connectors"])
    cols[1].metric("Assets Synced", f"{kpis['Assets Synced']:,}")
    cols[2].metric("Daily Syncs", kpis["Daily Syncs"])
    cols[3].metric("Product Readiness", kpis["Product Readiness"])

    st.divider()
    st.subheader("Connector Health")
    _show_dataframe(ConnectorService.connector_dataframe(), "No connectors are registered.")

    st.divider()
    left, right = st.columns([1, 1])
    with left:
        st.subheader("Customer Activation Flow")
        _show_dataframe(pd.DataFrame(ConnectorService.get_enablement_flow()), "No activation flow is available.")

    with right:
        st.subheader("Executive Narrative")
        st.info(ConnectorService.get_executive_narrative())


if __name__ == "__main__":
    main()

