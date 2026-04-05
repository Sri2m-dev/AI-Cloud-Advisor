from pathlib import Path
import sys

import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from shared.auth import login_user
from shared.aws_cost import get_aws_cost
from shared.nav import route_selected_page
from services.data_loader import load_all_data


@st.cache_data(ttl=3600)
def load_cost_data():
    try:
        return get_aws_cost()
    except Exception as e:
        return {"error": f"AWS credentials not configured: {str(e)}"}

st.set_page_config(page_title="AI Cloud Advisor", layout="wide")

st.markdown("""
<style>
/* Background */
.main {
    background-color: #f5f7fb;
}

/* Sidebar */
section[data-testid="stSidebar"] {
    background: #111827;
    color: white;
}

/* Sidebar text */
section[data-testid="stSidebar"] * {
    color: white !important;
}

/* Header bar */
.header-bar {
    background: white;
    padding: 15px 25px;
    border-radius: 10px;
    margin-bottom: 15px;
    box-shadow: 0px 2px 8px rgba(0,0,0,0.05);
}

/* Profile box */
.profile-box {
    background: white;
    padding: 15px;
    border-radius: 10px;
    margin-bottom: 20px;
}

/* Section cards */
.section-card {
    background: white;
    padding: 20px;
    border-radius: 12px;
    margin-top: 20px;
    box-shadow: 0px 4px 12px rgba(0,0,0,0.06);
}

.card {
    background: white;
    padding: 20px;
    border-radius: 12px;
    box-shadow: 0px 4px 12px rgba(0,0,0,0.08);
}

.kpi {
    padding: 15px;
    border-radius: 10px;
    color: white;
    font-weight: bold;
}

.kpi-blue { background: linear-gradient(135deg, #4facfe, #00f2fe); }
.kpi-purple { background: linear-gradient(135deg, #667eea, #764ba2); }
.kpi-green { background: linear-gradient(135deg, #43e97b, #38f9d7); }
.kpi-orange { background: linear-gradient(135deg, #f7971e, #ffd200); }
</style>
""", unsafe_allow_html=True)

# -----------------------
# GET USER ROLE
# -----------------------
role = st.session_state.get("role", None)

# -----------------------
# ROLE-BASED MENU
# -----------------------
if role == "CEO":
    menu = ["CEO Dashboard", "Recommendations", "Compliance"]
elif role == "CTO":
    menu = ["CTO Dashboard", "Cloud Accounts", "Cost Explorer", "Recommendations"]
elif role == "FinOps":
    menu = ["FinOps Dashboard", "Cost Explorer", "Recommendations"]
else:
    menu = ["Dashboard"]

# -----------------------
# SIDEBAR
# -----------------------
st.sidebar.image("https://via.placeholder.com/150", width=120)
st.sidebar.markdown("### ☁️ Cloud Advisory")
st.sidebar.markdown(
    f"""
    **👤 User:** {st.session_state.get('user_email', 'Guest')}  
    **🔐 Role:** {st.session_state.get('role', 'Not logged in')}
    """
)

ai_mode = st.sidebar.toggle("🔐 AI Safety Mode", value=st.session_state.get("ai_safe_mode", True))
st.session_state["ai_safe_mode"] = ai_mode
st.sidebar.markdown("---")
if role:
    selected_page = st.sidebar.radio(
        "Navigation",
        menu,
        index=0,
    )
    if selected_page != "Dashboard":
        route_selected_page(selected_page)

    st.sidebar.markdown("---")
    if st.sidebar.button("🚪 Logout"):
        st.session_state.clear()
        st.switch_page("app.py")
else:
    st.sidebar.caption("Please log in to access dashboards.")
    st.sidebar.markdown("---")

st.title("🔐 AI Cloud Advisor Login")

try:
    cost_data = load_cost_data()
    if "error" not in cost_data:
        st.write(cost_data)
    else:
        st.warning(cost_data["error"])
except Exception as e:
    st.warning(f"Could not load cost data: {str(e)}")

email = st.text_input("Email")
password = st.text_input("Password", type="password")

if st.button("Login"):
    result = login_user(email, password)

    if result["status"]:
        st.session_state["user_email"] = email
        st.session_state["role"] = result["role"]
        st.session_state["client_id"] = result.get("client_id", "some-client-id")

        with st.spinner("Loading cloud data..."):
            usage_df, reco_df, cost_df = load_all_data(st.session_state["client_id"])

        st.session_state["usage_df"] = usage_df
        st.session_state["reco_df"] = reco_df
        st.session_state["cost_df"] = cost_df

        if usage_df.empty:
            st.info("No cloud data available yet")

        if result["role"] == "CEO":
            st.switch_page("pages/ceo_dashboard.py")
        elif result["role"] == "CTO":
            st.switch_page("pages/cto_dashboard.py")
        else:
            st.switch_page("pages/finops_dashboard.py")
    else:
        error_msg = result.get("error", "Invalid credentials")
        st.error(error_msg)
