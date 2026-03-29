# login.py
# Simple authentication logic for AI-Cloud-Advisor


import streamlit as st
import bcrypt

# Pre-generated bcrypt hashes for demo purposes
users = {
    "admin": {
        "password": b"$2b$12$YFj9WQ1H3qYlPqYgHkzV3uF3k7Y0l3m2Fv8o3rJzPq1q7H2n8mJ2e",  # Updated hash for cloud123
        "role": "admin",
        "company": "DemoCorp"
    },
    "finops": {
        "password": b"$2b$12$KIXQJQwK0QZK0QZK0QZK0eQZK0QZK0QZK0QZK0QZK0QZK0QZK0QZK0",  # Replace with real hash
        "role": "finops",
        "company": "AcmeCorp"
    },
    "client2": {
        "password": b"$2b$12$KIXQJQwK0QZK0QZK0QZK0eQZK0QZK0QZK0QZK0QZK0QZK0QZK0QZK0",  # Replace with real hash
        "role": "viewer",
        "company": "GlobalTech"
    }
}

def login():
    st.title("Cloud Advisory Platform Login")
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")
    if st.button("Login"):
        if username in users:
            stored_hash = users[username]["password"]
            if bcrypt.checkpw(password.encode(), stored_hash):
                st.session_state["logged_in"] = True
                st.session_state["user"] = username
                st.session_state["role"] = users[username]["role"]
                st.session_state["company"] = users[username]["company"]
                st.rerun()
            else:
                st.error("Invalid credentials")
        else:
            st.error("Invalid credentials")
