import streamlit as st
from shared.session import init_session
from auth.role_constants import normalize_role

# Initialize session defaults
init_session()

# Page configuration
st.set_page_config(
    page_title="AI Cloud Advisor Login",
    page_icon="🔐",
    layout="wide"
)

# ------------------------------------------------------------------
# Temporary Local Users
# ------------------------------------------------------------------

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
        "role": "technical"
    }
}


def route_user(role: str):
    """
    Route users to the correct dashboard based on role.
    """

    role = normalize_role(role)

    if role in ["executive", "super_admin"]:
        st.switch_page("pages/executive_dashboard.py")

    elif role == "technical":
        st.switch_page("pages/technical_analytics.py")

    elif role == "finance":
        st.switch_page("pages/leadership_dashboard.py")

    else:
        st.switch_page("pages/executive_dashboard.py")


# ------------------------------------------------------------------
# Login Page
# ------------------------------------------------------------------

st.title("AI Cloud Advisor Login")

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

        user = VALID_USERS.get(username)

        if user and user["password"] == password:

            st.session_state["authenticated"] = True
            st.session_state["user"] = username
            st.session_state["role"] = normalize_role(user["role"])

            # Temporary organization mapping
            st.session_state["organization_id"] = (
                "bff29e99-1a33-4bf7-a2dc-3abe9bd2a03c"
            )

            st.success("Login successful")

            route_user(st.session_state["role"])

        else:
            st.error("Invalid credentials")


# ------------------------------------------------------------------
# Development Auto Login
# ------------------------------------------------------------------

try:

    params = st.experimental_get_query_params()

    if (
        params.get("auto_login") == ["1"]
        and not st.session_state.get("authenticated")
    ):

        st.session_state["authenticated"] = True
        st.session_state["user"] = "ceo@company.com"
        st.session_state["role"] = "executive"

        st.session_state["organization_id"] = (
            "bff29e99-1a33-4bf7-a2dc-3abe9bd2a03c"
        )

        route_user("executive")

except Exception:
    pass
