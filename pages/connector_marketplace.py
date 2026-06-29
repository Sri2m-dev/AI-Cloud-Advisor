from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st

from auth.connector_context import get_current_organization_id
from auth.guards import require_login
from auth.role_constants import normalize_role
from components.sidebar_navigation import render_sidebar_navigation
from services.enterprise_connector_platform_service import EnterpriseConnectorPlatformService


st.set_page_config(page_title="Connector Marketplace", layout="wide")

ALLOWED_ROLES = {"super_admin", "client_admin", "cio", "technical"}


def _require_access(role: str) -> None:
    if role not in ALLOWED_ROLES:
        st.error("Connector Marketplace is available to integration and technology roles.")
        st.stop()


def _table(rows: list[dict[str, Any]], empty: str) -> None:
    if rows:
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    else:
        st.info(empty)


def main() -> None:
    user = require_login()
    role = normalize_role(st.session_state.get("role") or user.get("role") or "cio")
    render_sidebar_navigation(role)
    _require_access(role)

    organization_id = get_current_organization_id()
    marketplace = EnterpriseConnectorPlatformService.get_marketplace(organization_id)
    summary = marketplace["summary"]

    st.title("Connector Marketplace")
    st.caption("Connect once. Discover forever. Authenticate systems, schedule syncs, and feed the Enterprise Data Fabric.")

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Marketplace", summary["Total"])
    k2.metric("Connected", summary["Connected"])
    k3.metric("SDK Available", summary["SDK Available"])
    k4.metric("Categories", summary["Categories"])

    st.divider()
    left, right = st.columns([0.95, 1.35])
    with left:
        st.subheader("Connect Once")
        connector_names = [row["Connector"] for row in marketplace["connectors"]]
        selected = st.selectbox("Connector", connector_names)
        schedule = st.selectbox("Schedule", ["Manual", "Every 15 min", "Hourly", "Daily", "Weekly", "Event driven"], index=3)
        use_demo = st.checkbox("Use demo-safe credential reference", value=True)
        role_arn = st.text_input("AWS Role ARN", value="arn:aws:iam::123456789012:role/NexoraReadOnly", disabled=use_demo)
        client_id = st.text_input("OAuth Client ID", value="demo-client", disabled=use_demo)
        token = st.text_input("Refresh Token / API Key", value="demo-token", type="password", disabled=use_demo)
        if st.button("Authenticate & Save", type="primary", use_container_width=True):
            credentials = None
            if not use_demo:
                credentials = {"role_arn": role_arn, "client_id": client_id, "token": token}
            result = EnterpriseConnectorPlatformService.connect_once(
                selected,
                credentials=credentials,
                organization_id=organization_id,
                schedule=schedule,
                configured_by=user.get("email") or "connector_marketplace",
            )
            if result.get("status") == "CONNECTED":
                st.success(f"{selected} connected. Credential reference: {result['credential_ref']}")
            else:
                st.error(result.get("message", "Connector onboarding failed."))

        if st.button("Run Sync Now", use_container_width=True):
            result = EnterpriseConnectorPlatformService.run_sync(selected, organization_id)
            if result["status"] == "SUCCESS":
                st.success(f"{selected} synchronized {result['records_synced']} records into the data fabric.")
            else:
                st.error(result.get("error") or "Sync failed.")

    with right:
        st.subheader("Marketplace Catalog")
        category = st.selectbox("Category Filter", ["All"] + marketplace["categories"])
        rows = marketplace["connectors"]
        if category != "All":
            rows = [row for row in rows if row["Category"] == category]
        _table(rows, "No connectors match this category.")

    st.divider()
    st.subheader("Wave 1 Priorities")
    st.write(", ".join(summary["Wave 1"]))

    st.subheader("Connector Certification")
    cert_rows = [
        {
            "Connector": row["Connector"],
            "Certification": row.get("Certification", "Uncertified"),
            "Coverage": ", ".join(name.title() for name, enabled in row.get("Coverage", {}).items() if enabled) or "None",
            "Health": row["Health"],
            "SDK Available": row["SDK Available"],
        }
        for row in marketplace["connectors"]
    ]
    _table(cert_rows, "No connector certification metadata is available.")


if __name__ == "__main__":
    main()
