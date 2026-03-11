import streamlit as st

from config import CONFIG

st.set_page_config(page_title=CONFIG.app_title, layout="wide")

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if "user" not in st.session_state:
    st.session_state.user = ""

# LOGIN
if not st.session_state.logged_in:

    st.title(f"☁ {CONFIG.app_title}")

    username = st.text_input("Username")
    password = st.text_input("Password", type="password")

    if st.button("Login"):

        if username == CONFIG.default_username and password == CONFIG.default_password:

            st.session_state.logged_in = True
            st.session_state.user = username
            st.rerun()

        else:
            st.error("Invalid credentials")

 # MAIN APP
else:
    st.sidebar.title("☁ Cloud Advisory")
    st.sidebar.write(f"👤 {st.session_state.user}")
    clients = ["Demo Account", "Client A", "Client B"]
    client = st.sidebar.selectbox("Select Client", clients)
    st.sidebar.write(f"Client: {client}")

    if client == "Client A":
        # Replace with actual data loading logic
        data = "Loaded Client A data"
    elif client == "Client B":
        # Replace with actual data loading logic
        data = "Loaded Client B data"
    else:
        data = "Loaded Demo Account data"

    if st.sidebar.button("Logout"):
        st.session_state.logged_in = False
        st.rerun()
    st.title(f"Welcome to {CONFIG.app_title}")
