from __future__ import annotations

import streamlit as st

from auth.role_constants import normalize_role
from config import DEFAULT_ORG_ID


CONNECTOR_ADMIN_ROLES = {"client_admin", "super_admin"}


def get_current_organization_id() -> str:
    user = st.session_state.get("user") or {}
    return str(
        st.session_state.get("organization_id")
        or st.session_state.get("org_id")
        or user.get("organization_id")
        or user.get("org_id")
        or DEFAULT_ORG_ID
    )


def get_current_user_id() -> str:
    user = st.session_state.get("user") or {}
    return str(
        st.session_state.get("user_id")
        or st.session_state.get("email")
        or user.get("id")
        or user.get("user_id")
        or user.get("email")
        or "unknown"
    )


def is_super_admin() -> bool:
    role = normalize_role(st.session_state.get("role") or (st.session_state.get("user") or {}).get("role"))
    return role == "super_admin"


def is_client_admin() -> bool:
    role = normalize_role(st.session_state.get("role") or (st.session_state.get("user") or {}).get("role"))
    return role == "client_admin"


def require_connector_admin() -> None:
    role = normalize_role(st.session_state.get("role") or (st.session_state.get("user") or {}).get("role"))
    if role not in CONNECTOR_ADMIN_ROLES:
        st.error("Connector setup is restricted to Client Admins and Super Admins.")
        st.stop()

