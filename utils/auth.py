from uuid import UUID

import streamlit as st

from auth.role_constants import normalize_role
from services.supabase_client import create_user_auth_client

AUTH_SESSION_KEYS = frozenset(
    {
        "authenticated",
        "user",
        "session",
        "auth_client",
        "user_id",
        "email",
        "profile",
        "role",
        "role_display",
        "permissions",
        "organization_id",
        "organization_name",
        "org_id",
        "tenant_id",
        "tenant",
        "authorized_organization_ids",
        "auth_backend",
        "customer_workflow_workspace_id",
        "active_customer_export",
    }
)


class AuthenticationError(RuntimeError):
    """Raised when a trusted identity or tenant membership cannot be verified."""


def create_session_client():
    return create_user_auth_client()


def clear_auth_state(session_state) -> None:
    for key in AUTH_SESSION_KEYS:
        if key in session_state:
            del session_state[key]


def _auth_user_id(auth_user) -> str:
    user_id = getattr(auth_user, "id", None)
    try:
        return str(UUID(str(user_id)))
    except (AttributeError, TypeError, ValueError) as exc:
        raise AuthenticationError("Supabase Auth returned an invalid user identity") from exc


def _rows(response) -> list:
    data = getattr(response, "data", None)
    if data is None:
        return []
    return data if isinstance(data, list) else [data]


def login_user(email, password):
    """Authenticate with a session-local client and bind profile by Auth UUID."""
    clear_auth_state(st.session_state)
    client = create_session_client()

    try:
        response = client.auth.sign_in_with_password({"email": email, "password": password})
        auth_user = getattr(response, "user", None)
        auth_session = getattr(response, "session", None)
        if auth_user is None or auth_session is None:
            raise AuthenticationError("Supabase Auth did not establish an authenticated session")

        user_id = _auth_user_id(auth_user)
        user_email = str(getattr(auth_user, "email", "") or "").strip().lower()
        if not user_email:
            raise AuthenticationError("Supabase Auth returned no verified email")

        profiles = _rows(
            client.table("users")
            .select("auth_user_id,email,org_id,role")
            .eq("auth_user_id", user_id)
            .limit(2)
            .execute()
        )
        if len(profiles) != 1:
            raise AuthenticationError("No unique tenant membership is assigned to this user")
        profile = profiles[0]
        if str(profile.get("auth_user_id") or "") != user_id:
            raise AuthenticationError("Tenant membership identity does not match Supabase Auth")
        if str(profile.get("email") or "").strip().lower() != user_email:
            raise AuthenticationError("Tenant membership email does not match Supabase Auth")

        organization_id = str(profile.get("org_id") or "").strip()
        try:
            organization_id = str(UUID(organization_id))
        except (TypeError, ValueError) as exc:
            raise AuthenticationError("Tenant membership has no valid organization") from exc

        organizations = _rows(
            client.table("organizations")
            .select("id,name,status")
            .eq("id", organization_id)
            .limit(2)
            .execute()
        )
        if len(organizations) != 1:
            raise AuthenticationError("Organization membership is missing or revoked")
        organization = organizations[0]
        if (
            str(organization.get("id") or "") != organization_id
            or str(organization.get("status") or "").strip().lower() != "active"
        ):
            raise AuthenticationError("Organization membership is inactive")

        role_value = str(profile.get("role") or "").strip()
        if not role_value:
            raise AuthenticationError("Tenant membership has no assigned role")
        role = normalize_role(role_value)
        session_state = st.session_state
        session_state["authenticated"] = True
        session_state["user"] = auth_user
        session_state["session"] = auth_session
        session_state["auth_client"] = client
        session_state["user_id"] = user_id
        session_state["email"] = user_email
        session_state["profile"] = profile
        session_state["role_display"] = role_value
        session_state["role"] = role
        session_state["permissions"] = profile.get("permissions") or []
        session_state["organization_id"] = organization_id
        session_state["org_id"] = organization_id
        session_state["tenant_id"] = organization_id
        session_state["tenant"] = organization_id
        session_state["organization_name"] = str(organization.get("name") or "").strip()
        session_state["authorized_organization_ids"] = [organization_id]
        session_state["auth_backend"] = "supabase"
        return auth_user
    except Exception:
        clear_auth_state(st.session_state)
        raise


def select_tenant(organization_id: str) -> None:
    """Select only the tenant in the current UID-bound membership."""
    session_state = st.session_state
    if not session_state.get("authenticated") or session_state.get("auth_backend") != "supabase":
        raise AuthenticationError("An authenticated Supabase session is required")

    user_id = _auth_user_id(session_state.get("user"))
    profile = session_state.get("profile")
    if (
        not isinstance(profile, dict)
        or str(profile.get("auth_user_id") or "") != user_id
        or user_id != str(session_state.get("user_id") or "")
    ):
        raise AuthenticationError("Tenant membership identity could not be verified")

    try:
        selected = str(UUID(str(organization_id)))
    except (TypeError, ValueError) as exc:
        raise AuthenticationError("Selected organization is invalid") from exc

    authorized = session_state.get("authorized_organization_ids")
    if not isinstance(authorized, (list, tuple, set)) or selected not in authorized:
        raise AuthenticationError("Selected organization is not an authorized membership")
    if selected != str(profile.get("org_id") or ""):
        raise AuthenticationError("Selected organization is not an authorized membership")

    session_state["organization_id"] = selected
    session_state["org_id"] = selected
    session_state["tenant_id"] = selected
    session_state["tenant"] = selected


def logout_user():
    """Sign out this session's client and clear all local identity/scope state."""
    client = st.session_state.get("auth_client")
    try:
        if client is not None:
            client.auth.sign_out()
    finally:
        clear_auth_state(st.session_state)


def require_auth():
    from auth.guards import require_auth as require_guard_auth

    return require_guard_auth()


def require_role(role):
    from auth.guards import require_role as require_guard_role

    return require_guard_role(role)


def get_current_user():
    return st.session_state.get("user")
