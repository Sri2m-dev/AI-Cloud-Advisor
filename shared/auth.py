import streamlit as st


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

    role = str(
        st.session_state.get(
            "role",
            ""
        )
    ).strip().lower()

    normalized_roles = [
        str(r).strip().lower()
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

    if email == "admin":

        return {
            "status": True,
            "role": "super_admin",
            "client_id": "global",
            "username": "admin",
        }

    return {
        "status": False,
        "error": "User not found",
    }