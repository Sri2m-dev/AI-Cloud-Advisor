import streamlit as st

ROLE_ACCESS = {
    "super_admin": [
        "executive_dashboard",
        "leadership_dashboard",
        "finops_dashboard",
        "technical_dashboard",
        "approval_center",
        "admin_panel",
    ],

    "executive": [
        "executive_dashboard",
        "leadership_dashboard",
    ],

    "finance": [
        "finops_dashboard",
    ],

    "technical": [
        "technical_dashboard",
    ],

    "operations": [
        "approval_center",
    ],

    "viewer": [
        "executive_dashboard",
    ],
}


def require_role(*allowed_roles):

    role = st.session_state.get("role")

    if role not in allowed_roles:
        st.error("Access denied")
        st.stop()