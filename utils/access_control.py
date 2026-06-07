"""
RBAC enforcement middleware and helpers for Streamlit apps.
"""
import streamlit as st
from config.role_permissions import ROLE_PERMISSIONS
from auth.guards import require_auth, require_role as require_guard_role


def has_permission(role, permission):
    """
    Check if a role has a specific permission.
    """
    return permission in ROLE_PERMISSIONS.get(role, [])


def require_permission(permission):
    """
    Enforce that the current user has the given permission. Stops page if not.
    """
    user = require_auth()
    if not has_permission(user.get("role"), permission):
        st.error(f"You do not have permission: {permission}")
        st.stop()


def require_role(role):
    """
    Enforce that the current user has the given role. Stops page if not.
    """
    return require_guard_role(role)

