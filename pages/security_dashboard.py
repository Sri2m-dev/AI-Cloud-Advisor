from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st

from auth.connector_context import get_current_organization_id
from auth.guards import require_login
from auth.role_constants import normalize_role
from components.sidebar_navigation import render_sidebar_navigation
from services.enterprise_security_service import EnterpriseSecurityService


st.set_page_config(page_title="Security Dashboard", layout="wide")

ALLOWED_ROLES = {"super_admin", "client_admin", "cio", "executive", "technical"}


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
        st.error("Security Dashboard is available to enterprise operations roles.")
        st.stop()

    service = EnterpriseSecurityService(get_current_organization_id())
    force = st.sidebar.button("Run Security Validation", use_container_width=True)
    dashboard = service.run_security_validation(persist=force or "security_dashboard" not in st.session_state)
    st.session_state["security_dashboard"] = dashboard
    kpis = dashboard["kpis"]

    st.title("Security Dashboard")
    st.caption("Enterprise Security Framework for connector credentials, RBAC, tenant isolation, execution boundaries, and compliance evidence.")

    cols = st.columns(6)
    cols[0].metric("Security Health", f"{kpis['Security Health']}%")
    cols[1].metric("Status", kpis["Status"])
    cols[2].metric("Critical Findings", kpis["Critical Findings"])
    cols[3].metric("Warnings", kpis["Warnings"])
    cols[4].metric("Connectors", kpis["Connectors"])
    cols[5].metric("Token Expiry", kpis["Token Expiry"])

    tabs = st.tabs(["Overview", "Connector Security", "RBAC", "Tenant Isolation", "Execution Security", "Compliance", "Events"])

    with tabs[0]:
        st.subheader("Security Validation Results")
        _table(dashboard["results"], "No security validation results are available.")
        st.subheader("Recommendations")
        _table(dashboard["recommendations"], "No security recommendations are available.")

    with tabs[1]:
        st.subheader("Connector Security")
        _table(dashboard["connector_security"], "No connector security records are available.")
        st.subheader("Credential Inventory")
        _table(dashboard["credential_inventory"], "No credential inventory records are available.")
        st.subheader("Secret Rotation")
        _table(dashboard["credential_rotation"], "No rotation records are available.")
        st.subheader("Token Expiry")
        _table(dashboard["token_expiry"], "No token expiry records are available.")

    with tabs[2]:
        st.subheader("RBAC Validation")
        _table(dashboard["rbac_validation"], "No RBAC validation records are available.")

    with tabs[3]:
        st.subheader("Tenant Isolation")
        _table(dashboard["tenant_validation"], "No tenant isolation records are available.")

    with tabs[4]:
        st.subheader("Execution Security")
        _table(dashboard["execution_security"], "No execution security records are available.")

    with tabs[5]:
        st.subheader("Compliance")
        _table(dashboard["compliance"], "No compliance records are available.")

    with tabs[6]:
        st.subheader("Security Events")
        _table(dashboard["events"], "No security events have been published.")
        st.subheader("Historical Scores")
        _table(dashboard.get("history", []), "No security validation history is available.")


if __name__ == "__main__":
    main()
