from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st

from auth.connector_context import get_current_organization_id
from auth.guards import require_login
from auth.role_constants import normalize_role
from components.sidebar_navigation import render_sidebar_navigation
from services.disaster_recovery_service import DisasterRecoveryService


st.set_page_config(page_title="Disaster Recovery Dashboard", layout="wide")

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
        st.error("Disaster Recovery Dashboard is available to enterprise operations roles.")
        st.stop()

    dashboard = DisasterRecoveryService(get_current_organization_id()).get_dr_readiness(persist=True)
    kpis = dashboard["kpis"]

    st.title("Disaster Recovery Dashboard")
    st.caption("Backup, restore, replication, RPO/RTO, retention, and disaster recovery readiness.")
    cols = st.columns(5)
    cols[0].metric("DR Readiness", f"{kpis['DR Readiness']}%")
    cols[1].metric("Backup Health", kpis["Backup Health"])
    cols[2].metric("RPO", kpis["RPO"])
    cols[3].metric("RTO", kpis["RTO"])
    cols[4].metric("Restore", kpis["Restore Validation"])
    _table(dashboard["checks"], "No DR checks are available.")


if __name__ == "__main__":
    main()
