"""Organization isolation helpers for Streamlit pages and repositories."""

from __future__ import annotations

from typing import Any

import streamlit as st


ORG_KEYS = ("organization_id", "org_id", "tenant_id", "tenant")


def get_principal_organization_id(principal: dict[str, Any]) -> str | None:
    """Return the authenticated user's organization id from known profile fields."""
    for key in ORG_KEYS:
        value = principal.get(key)
        if value:
            return str(value).strip()
    return None


def require_organization(principal: dict[str, Any]) -> str:
    """Require an authenticated principal to be scoped to exactly one organization."""
    organization_id = get_principal_organization_id(principal)
    if not organization_id:
        st.error("No organization is assigned to this user.")
        st.stop()
    return organization_id


def _normalize_requested_organization_id(requested_organization_id: Any) -> str | None:
    if isinstance(requested_organization_id, list):
        requested_organization_id = requested_organization_id[0] if requested_organization_id else None
    value = str(requested_organization_id or "").strip()
    return value or None


def enforce_organization_access(
    principal: dict[str, Any],
    requested_organization_id: Any = None,
) -> str:
    """Prevent callers from selecting another tenant's organization id."""
    assigned_organization_id = require_organization(principal)
    requested = _normalize_requested_organization_id(requested_organization_id)
    if requested and requested != assigned_organization_id:
        st.error("Unauthorized organization access.")
        st.stop()
    return assigned_organization_id

