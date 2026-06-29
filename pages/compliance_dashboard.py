from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st

from auth.connector_context import get_current_organization_id
from auth.guards import require_login
from auth.role_constants import normalize_role
from components.sidebar_navigation import render_sidebar_navigation
from services.compliance_service import ComplianceService


st.set_page_config(page_title="Compliance Dashboard", layout="wide")

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
        st.error("Compliance Dashboard is available to enterprise operations roles.")
        st.stop()

    service = ComplianceService(get_current_organization_id())
    force = st.sidebar.button("Run Compliance Assessment", use_container_width=True)
    dashboard = service.run_compliance_assessment(persist=force or "compliance_dashboard" not in st.session_state)
    st.session_state["compliance_dashboard"] = dashboard
    kpis = dashboard["kpis"]

    st.title("Compliance Dashboard")
    st.caption("Automated compliance controls, evidence, audit packages, and enterprise framework readiness.")

    cols = st.columns(6)
    cols[0].metric("Overall Compliance", f"{kpis['Overall Compliance']}%")
    cols[1].metric("ISO 27001", f"{kpis['ISO 27001']}%")
    cols[2].metric("SOC 2", f"{kpis['SOC 2']}%")
    cols[3].metric("NIST", f"{kpis['NIST']}%")
    cols[4].metric("GDPR", f"{kpis['GDPR']}%")
    cols[5].metric("Evidence", kpis["Audit Evidence"])

    tabs = st.tabs(["Frameworks", "Controls", "Evidence", "Audit Package", "Recommendations", "History"])
    with tabs[0]:
        _table(dashboard["frameworks"], "No compliance frameworks are available.")
    with tabs[1]:
        _table(dashboard["controls"], "No compliance controls are available.")
    with tabs[2]:
        _table(dashboard["evidence"], "No audit evidence is available.")
    with tabs[3]:
        if st.button("Generate Audit Evidence Package", use_container_width=True):
            st.session_state["audit_package"] = service.generate_audit_package(persist=True)
        _table(st.session_state.get("audit_package", dashboard["audit_package"]), "No audit package is available.")
    with tabs[4]:
        _table(dashboard["recommendations"], "No compliance recommendations are available.")
    with tabs[5]:
        _table(dashboard.get("history", []), "No compliance history is available.")


if __name__ == "__main__":
    main()
