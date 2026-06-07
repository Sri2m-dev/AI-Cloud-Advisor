import streamlit as st


def init_session():
    defaults = {
        "authenticated": False,
        "user": None,
        "role": None,
        "organization_id": None,
    }

    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

