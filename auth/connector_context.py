from __future__ import annotations

from collections.abc import Mapping
from uuid import UUID

import streamlit as st

from auth.role_constants import normalize_role

CONNECTOR_ADMIN_ROLES = {"client_admin", "sales_engineer", "super_admin"}


def _validated_identity():
    session = st.session_state
    if not session.get("authenticated"):
        raise PermissionError("An authenticated session is required")

    backend = str(session.get("auth_backend") or "").strip().lower()
    user = session.get("user")
    if backend == "supabase":
        user_id = str(getattr(user, "id", "") or "")
        try:
            user_id = str(UUID(user_id))
        except (TypeError, ValueError) as exc:
            raise PermissionError("Supabase Auth identity is invalid") from exc

        profile = session.get("profile")
        if (
            not isinstance(profile, Mapping)
            or str(profile.get("auth_user_id") or "") != user_id
            or str(session.get("user_id") or "") != user_id
        ):
            raise PermissionError("Supabase tenant identity could not be verified")
        organization_id = str(
            session.get("organization_id") or session.get("org_id") or ""
        )
        try:
            organization_id = str(UUID(organization_id))
        except (TypeError, ValueError) as exc:
            raise PermissionError("Supabase tenant identity is invalid") from exc
        authorized = session.get("authorized_organization_ids")
        if (
            not isinstance(authorized, (list, tuple, set))
            or organization_id not in authorized
            or str(profile.get("org_id") or "") != organization_id
        ):
            raise PermissionError("Supabase tenant membership could not be verified")
        return user_id, organization_id, profile

    if backend == "local":
        user_id = str(session.get("user_id") or "").strip()
        organization_id = str(
            session.get("organization_id") or session.get("org_id") or ""
        ).strip()
        authorized = session.get("authorized_organization_ids")
        if not user_id or not organization_id or not isinstance(
            authorized, (list, tuple, set)
        ) or organization_id not in authorized:
            raise PermissionError("Local tenant membership could not be verified")
        return user_id, organization_id, user

    raise PermissionError("The session authentication backend is invalid")


def get_current_organization_id() -> str:
    return _validated_identity()[1]


def get_current_user_id() -> str:
    return _validated_identity()[0]


def _current_role() -> str:
    _, _, identity = _validated_identity()
    if isinstance(identity, Mapping):
        role = identity.get("role") or st.session_state.get("role")
    else:
        role = st.session_state.get("role")
    return normalize_role(role)


def is_super_admin() -> bool:
    role = _current_role()
    return role == "super_admin"


def is_client_admin() -> bool:
    role = _current_role()
    return role == "client_admin"


def require_connector_admin() -> None:
    role = _current_role()
    if role not in CONNECTOR_ADMIN_ROLES:
        st.error(
            "Connector setup is restricted to Client Admins, Sales Engineers, "
            "and Super Admins."
        )
        st.stop()
