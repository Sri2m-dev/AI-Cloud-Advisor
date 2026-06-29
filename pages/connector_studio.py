from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st

from auth.connector_context import get_current_organization_id
from auth.guards import require_login
from auth.role_constants import normalize_role
from components.sidebar_navigation import render_sidebar_navigation
from services.universal_connector_platform_service import UniversalConnectorPlatformService


st.set_page_config(page_title="Connector Studio", layout="wide")

ALLOWED_ROLES = {"super_admin", "client_admin", "cio", "technical"}


def _table(rows: list[dict[str, Any]] | dict[str, Any], empty: str) -> None:
    if isinstance(rows, dict):
        rows = [{"Metric": key, "Value": value} for key, value in rows.items()]
    if rows:
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    else:
        st.info(empty)


def main() -> None:
    user = require_login()
    role = normalize_role(st.session_state.get("role") or user.get("role") or "cio")
    render_sidebar_navigation(role)
    if role not in ALLOWED_ROLES:
        st.error("Connector Studio is available to enterprise integration and technology roles.")
        st.stop()

    dashboard = UniversalConnectorPlatformService.get_studio_dashboard(get_current_organization_id())
    kpis = dashboard["kpis"]

    st.title("Connector Studio")
    st.caption("Build, map, certify, and publish customer connectors for the Enterprise AI fabric.")

    cols = st.columns(7)
    cols[0].metric("Marketplace", kpis["Marketplace Connectors"])
    cols[1].metric("Templates", kpis["Templates"])
    cols[2].metric("Auth Methods", kpis["Auth Methods"])
    cols[3].metric("Drafts", kpis["Draft Connectors"])
    cols[4].metric("Published", kpis["Published Connectors"])
    cols[5].metric("AI Generated", kpis["AI Generated"])
    cols[6].metric("Readiness", f"{kpis['Studio Readiness']}%")

    st.info(dashboard["executive_summary"])

    tabs = st.tabs(
        [
            "Marketplace",
            "My Connectors",
            "Templates",
            "API Explorer",
            "Schema Mapper",
            "Authentication",
            "Scheduler",
            "Certification",
            "Publishing",
        ],
    )

    with tabs[0]:
        st.subheader("AI Connector Marketplace")
        _table(dashboard["marketplace"], "No marketplace connectors are available.")

    with tabs[1]:
        st.subheader("My Connectors")
        _table(dashboard["my_connectors"], "No customer connectors are available.")

    with tabs[2]:
        st.subheader("Templates")
        _table(dashboard["templates"], "No connector templates are available.")
        st.subheader("Database Connector")
        _table(dashboard["database_connectors"], "No database connector support is available.")
        st.subheader("File Connector")
        _table(dashboard["file_connectors"], "No file connector support is available.")
        st.subheader("Webhook Builder")
        _table(dashboard["webhook_builder"], "No webhook builder metadata is available.")

    with tabs[3]:
        st.subheader("API Discovery")
        api = dashboard["api_discovery"]
        _table({key: value for key, value in api.items() if key != "Endpoints"}, "No API discovery metadata is available.")
        st.subheader("Endpoints")
        _table(api.get("Endpoints", []), "No endpoints were discovered.")
        st.subheader("AI Connector Generator")
        _table(dashboard["ai_connector_generator"], "No AI connector generation plan is available.")

    with tabs[4]:
        st.subheader("Schema Discovery")
        _table(dashboard["schema_discovery"], "No schema fields were discovered.")
        st.subheader("AI Field Mapping")
        _table(dashboard["field_mapping"], "No field mappings are available.")
        st.subheader("Knowledge Graph Mapping")
        _table(dashboard["knowledge_graph_mapping"], "No Knowledge Graph mappings are available.")
        st.subheader("Digital Twin Mapping")
        _table(dashboard["digital_twin_mapping"], "No Digital Twin mappings are available.")

    with tabs[5]:
        st.subheader("Authentication Builder")
        _table(dashboard["authentication_types"], "No authentication methods are available.")

    with tabs[6]:
        st.subheader("Scheduler")
        _table(dashboard["scheduler"], "No scheduler plan is available.")

    with tabs[7]:
        st.subheader("Connector Certification")
        _table(dashboard["certification"], "No certification result is available.")

    with tabs[8]:
        st.subheader("Publish Plan")
        _table(dashboard["publish_plan"], "No publish plan is available.")
        st.subheader("Copilot Example")
        _table(dashboard["copilot_example"], "No Copilot example is available.")


if __name__ == "__main__":
    main()
