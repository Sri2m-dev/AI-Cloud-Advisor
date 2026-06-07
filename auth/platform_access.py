import streamlit as st

from auth.guards import require_role


def _jwt_role_enforcement(allowed_roles: set[str]) -> str:
    user = require_role(allowed_roles)
    return str(user.get("role") or "").strip()


def require_page_role(required_role: str) -> str:
    """Stop page execution unless the active role matches the required role."""
    role_name = str(required_role).strip()
    if not role_name:
        st.error("Configuration error: required role is empty.")
        st.stop()
    return _jwt_role_enforcement({role_name})


def require_any_role(*allowed_roles: str) -> str:
    """Stop page execution unless the active role is in the allowed list."""
    normalized = {str(role).strip() for role in allowed_roles if role}
    if not normalized:
        st.error("Configuration error: allowed roles are empty.")
        st.stop()
    return _jwt_role_enforcement(normalized)

