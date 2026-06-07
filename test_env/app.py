
import sys
import os
# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from shared.auth import login_user
from services.cost_service import fetch_cost_data
from auth.role_constants import normalize_role

def show_login():
    st.title("🔐 Login")
    email = st.text_input("Email")
    password = st.text_input("Password", type="password")
    if st.button("Login"):
        result = login_user(email, password)
        if result["status"]:
            st.session_state["role_display"] = result["role"]
            st.session_state["role"] = normalize_role(result["role"])
            st.rerun()
        else:
            st.error("Invalid credentials")


import streamlit as st
import sys
from pathlib import Path

# Protect auth import to avoid crashes
try:
    from shared.auth import login_user
except Exception as e:
    st.error(f"Auth system error: {e}")
    st.stop()


# -----------------------
# SESSION STATE INIT (CRITICAL)
# -----------------------
if "role" not in st.session_state:
    st.session_state["role"] = None

# -----------------------
# LOGIN GATE (BLOCK APP BEFORE LOGIN)
# -----------------------
if not st.session_state["role"]:
    show_login()

    st.stop()

# -----------------------
# PATH SETUP
# -----------------------
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))



# -----------------------
# AFTER LOGIN ONLY (SIDEBAR)
# -----------------------
st.sidebar.title("AI Cloud Advisor")
st.sidebar.caption(f"Role: {st.session_state['role']}")

# -----------------------
# DATA MODE
# -----------------------
mode = st.sidebar.selectbox(
    "Select Data Source",
    ["mock", "file", "supabase"]
)

st.session_state["data_mode"] = mode

if mode == "file":
    uploaded_file = st.sidebar.file_uploader("Upload Cost File", type=["xlsx"])
    st.session_state["uploaded_file"] = uploaded_file
else:
    st.session_state["uploaded_file"] = None


if "role" not in st.session_state:
    st.session_state["role"] = "CTO"

page = st.session_state["role"]

# -----------------------
# SERVICE LAYER IMPORT (CLEAN ARCHITECTURE)
# -----------------------
from services.cost_service import fetch_cost_data

# Example usage (inside your dashboard/page):
# result = fetch_cost_data(mode=st.session_state["data_mode"], file=st.session_state["uploaded_file"])
# services = result["services"]
# total_spend = result["total_spend"]
# error = result["error"]
# if error:
#     st.error(error)



