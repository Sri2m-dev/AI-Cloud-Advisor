import streamlit as st

st.set_page_config(page_title="Cloud Advisory Platform", layout="wide")

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if "user" not in st.session_state:
    st.session_state.user = ""

# LOGIN
if not st.session_state.logged_in:

    st.title("☁ Cloud Advisory Platform")

    username = st.text_input("Username")
    password = st.text_input("Password", type="password")

    if st.button("Login"):

        if username == "admin" and password == "cloud123":

            st.session_state.logged_in = True
            st.session_state.user = username
            st.rerun()

        else:
            st.error("Invalid credentials")

# MAIN APP
else:

    st.sidebar.title("☁ Cloud Advisory")

    st.sidebar.write(f"👤 {st.session_state.user}")

    clients = ["Demo Account", "Enterprise Client", "Startup Client"]

    client = st.sidebar.selectbox("Select Client", clients)

    st.sidebar.write(f"Client: {client}")

    if st.sidebar.button("Logout"):
        st.session_state.logged_in = False
        st.rerun()

    st.title("Welcome to Cloud Advisory Platform")