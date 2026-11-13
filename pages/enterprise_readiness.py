from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st

from auth.connector_context import get_current_organization_id
from auth.guards import require_login
from auth.role_constants import normalize_role
from components.sidebar_navigation import render_sidebar_navigation
from services.release_readiness_service import ReleaseReadinessService

st.set_page_config(page_title="Enterprise Readiness", layout="wide")

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
        st.error("Enterprise Readiness is available to enterprise operations roles.")
        st.stop()

    org_id = get_current_organization_id()
    service = ReleaseReadinessService(org_id)
    release = service.validate_release(persist=False)
    production = service.validate_production_readiness(persist=False)
    st.title("Enterprise Readiness")
    st.warning("NOT_VERIFIED: reviewed release and production validation evidence is unavailable.")
    st.caption("This page does not grant technical acceptance or deployment approval.")
    st.metric("Release status", release["status"])
    st.metric("Production status", production["status"])
    _table(release["checks"], "No verified release evidence.")
    _table(production["domains"], "No verified production evidence.")


if __name__ == "__main__":
    main()
