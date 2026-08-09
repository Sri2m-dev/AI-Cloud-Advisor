import streamlit as st

from auth.role_constants import normalize_role


def require_role(allowed_roles):
    """
    Streamlit RBAC helper.

    Example:
        require_role(
            [
                "executive",
                "super_admin"
            ]
        )
    """

    authenticated = bool(
        st.session_state.get("authenticated")
    )

    if not authenticated:
        st.error("Please log in")
        st.stop()

    role = normalize_role(st.session_state.get("role", ""))
    st.session_state["role"] = role

    normalized_roles = [
        normalize_role(r)
        for r in allowed_roles
    ]

    if role not in normalized_roles:
        st.error(
            f"""
Unauthorized Access

Current Role:
{role}

Allowed Roles:
{', '.join(normalized_roles)}
"""
        )
        st.stop()

    return {
        "username": st.session_state.get("user"),
        "role": role,
        "organization_id": st.session_state.get("organization_id"),
        "authenticated": True,
    }


def login_user(email, password):
    """
    Legacy compatibility helper.
    Current application uses pages/login.py.
    """

    return {
        "status": False,
        "error": "Legacy login is disabled; use pages/login.py",
    }
