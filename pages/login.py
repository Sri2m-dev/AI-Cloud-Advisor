import streamlit as st

from auth.role_constants import normalize_role
from components.sidebar_navigation import DEFAULT_ROLE_PAGE
from services import audit_service
from services.local_auth_service import (
    authenticate_local_user,
    ensure_nonproduction_personas,
    local_auth_enabled,
)
from shared.session import init_session
from utils.auth import login_user as supabase_login_user

# Initialize session defaults
init_session()

# Page configuration
st.set_page_config(page_title="NEXORA Login", page_icon="🔐", layout="wide")

# ------------------------------------------------------------------
# Dev-only Local Users
# ------------------------------------------------------------------

DEV_AUTH_ENABLED = local_auth_enabled()

if DEV_AUTH_ENABLED:
    ensure_nonproduction_personas()


def get_profile_org_id(profile):
    """
    Return the organization identifier from whichever profile key is populated.
    """

    if not isinstance(profile, dict):
        return None

    return (
        profile.get("org_id")
        or profile.get("organization_id")
        or profile.get("tenant_id")
        or profile.get("tenant")
    )


def set_login_session(email, role, org_id, user_id=None):
    """
    Normalize session keys used across pages, services, and repositories.
    """

    normalized_role = normalize_role(role)

    st.session_state["authenticated"] = True
    st.session_state["user"] = email
    st.session_state["email"] = email
    st.session_state["role"] = normalized_role
    st.session_state["organization_id"] = org_id
    st.session_state["org_id"] = org_id
    st.session_state["tenant_id"] = org_id
    st.session_state["tenant"] = org_id

    if user_id:
        st.session_state["user_id"] = user_id


def login_with_dev_user(username, password):
    """
    Authenticate seeded local users only when AUTH_MODE=dev is set.
    """

    if not DEV_AUTH_ENABLED:
        return False

    user = authenticate_local_user(username, password)
    if not user:
        return False

    set_login_session(
        email=user.email,
        role=user.role,
        org_id=user.organization_id,
        user_id=user.email,
    )
    st.session_state["auth_backend"] = "local"
    st.session_state["authorized_organization_ids"] = [user.organization_id]
    st.session_state["organization_name"] = user.organization_name
    return True


def login_with_supabase(username, password):
    """
    Authenticate through Supabase and normalize the resulting app session.
    """

    auth_user = supabase_login_user(username, password)

    if not auth_user:
        return False

    profile = st.session_state.get("profile", {})
    email = st.session_state.get("email") or getattr(auth_user, "email", username)
    role = profile.get("role") or st.session_state.get("role")
    org_id = (
        get_profile_org_id(profile)
        or st.session_state.get("org_id")
        or st.session_state.get("organization_id")
        or st.session_state.get("tenant_id")
        or st.session_state.get("tenant")
    )

    if not org_id:
        st.session_state["authenticated"] = False
        st.error("No organization is assigned to this user.")
        return False

    set_login_session(
        email=email, role=role, org_id=org_id, user_id=st.session_state.get("user_id")
    )
    return True


def route_user(role: str):
    """
    Route users to the correct dashboard based on role.
    """

    role = normalize_role(role)
    destination = DEFAULT_ROLE_PAGE.get(role)

    if destination:
        st.switch_page(destination)
    else:
        st.switch_page("pages/login.py")


# ------------------------------------------------------------------
# Login Page
# ------------------------------------------------------------------

st.title("NEXORA")
st.caption("Next Generation Technology Intelligence")

# Already authenticated
if st.session_state.get("authenticated"):
    st.success(f"Already logged in as {st.session_state.get('user')}")

    role = st.session_state.get("role")
    route_user(role)

else:
    username = st.text_input("Username", placeholder="you@example.com")

    password = st.text_input("Password", type="password")

    if st.button("Login"):
        try:
            if DEV_AUTH_ENABLED:
                login_success = login_with_dev_user(username, password)
            else:
                login_success = login_with_supabase(username, password)

        except Exception:
            login_success = False

        if login_success:
            # Automatically log the user login event
            try:
                audit_service.log_user_login(
                    user_id=st.session_state["email"],
                    org_id=st.session_state["organization_id"],
                    ip_address=None,  # Would come from request context in production
                    user_agent=None,  # Would come from request context in production
                    actor_role=st.session_state["role"],
                )
            except Exception:
                pass

            st.success("Login successful")

            route_user(st.session_state["role"])

        else:
            if DEV_AUTH_ENABLED:
                audit_service.log_event(
                    event_type="USER_LOGIN_FAILED",
                    user_id="anonymous",
                    action="login_failed",
                    resource_type="authentication",
                    resource_id="unknown",
                    org_id="bff29e99-1a33-4bf7-a2dc-3abe9bd2a03c",
                    details={"status": "invalid_credentials"},
                    status="failure",
                )
            st.error("Invalid credentials")
