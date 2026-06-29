import os

import streamlit as st
from shared.session import init_session
from auth.role_constants import normalize_role
from components.sidebar_navigation import DEFAULT_ROLE_PAGE
from services import audit_service
from utils.auth import login_user as supabase_login_user

# Initialize session defaults
init_session()

# Page configuration
st.set_page_config(
    page_title="NEXORA Login",
    page_icon="🔐",
    layout="wide"
)

# ------------------------------------------------------------------
# Dev-only Local Users
# ------------------------------------------------------------------

AUTH_MODE = os.getenv("AUTH_MODE", "").strip().lower()
DEV_AUTH_ENABLED = AUTH_MODE == "dev"
DEV_ORG_ID = "bff29e99-1a33-4bf7-a2dc-3abe9bd2a03c"

VALID_USERS = {

    "ceo@company.com": {
        "password": "password123",
        "role": "executive"
    },

    "admin@company.com": {
        "password": "password123",
        "role": "super_admin"
    },

    "finops@client.com": {
        "password": "password123",
        "role": "finance"
    },

    "engineer@client.com": {
        "password": "password123",
        "role": "technical"
    },

    "cto@company.com": {
        "password": "password123",
        "role": "cto"
    }
}


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

    user = VALID_USERS.get(username)

    if not user or user["password"] != password:
        return False

    set_login_session(
        email=username,
        role=user["role"],
        org_id=DEV_ORG_ID
    )
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
        email=email,
        role=role,
        org_id=org_id,
        user_id=st.session_state.get("user_id")
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

    st.success(
        f"Already logged in as {st.session_state.get('user')}"
    )

    role = st.session_state.get("role")
    route_user(role)

else:

    username = st.text_input("Username")

    password = st.text_input(
        "Password",
        type="password"
    )

    if st.button("Login"):

        try:
            login_success = (
                login_with_dev_user(username, password)
                if DEV_AUTH_ENABLED
                else login_with_supabase(username, password)
            )

        except Exception:
            login_success = False

        if login_success:
            # Automatically log the user login event
            audit_service.log_user_login(
                user_id=st.session_state["email"],
                org_id=st.session_state["organization_id"],
                ip_address=None,  # Would come from request context in production
                user_agent=None   # Would come from request context in production
            )

            st.success("Login successful")

            route_user(st.session_state["role"])

        else:
            st.error("Invalid credentials")


# ------------------------------------------------------------------
# Development Auto Login, enabled only with AUTH_MODE=dev.
# ------------------------------------------------------------------

try:

    params = st.experimental_get_query_params()

    if (
        DEV_AUTH_ENABLED
        and
        params.get("auto_login") == ["1"]
        and not st.session_state.get("authenticated")
    ):

        set_login_session(
            email="ceo@company.com",
            role="executive",
            org_id=DEV_ORG_ID
        )

        # Automatically log the auto-login event
        audit_service.log_user_login(
            user_id="ceo@company.com",
            org_id=st.session_state["organization_id"]
        )

        route_user("executive")

except Exception:
    pass
