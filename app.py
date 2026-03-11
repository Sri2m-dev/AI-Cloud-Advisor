import streamlit as st
import pandas as pd

# Dummy data for demonstration
monthly_cost = pd.DataFrame({"Month": ["Jan", "Feb", "Mar", "Apr", "May"], "Cost": [80000, 90000, 110000, 120000, 124000]})
service_breakdown = pd.DataFrame({"Service": ["EC2", "S3", "RDS", "EKS", "Lambda"], "Cost": [32000, 18000, 22000, 14000, 8000]})
top_drivers = pd.DataFrame({"Service": ["EC2", "RDS", "S3", "EKS", "Lambda", "DynamoDB", "Redshift", "ElastiCache", "SageMaker", "EMR"], "Cost": [32000, 22000, 18000, 14000, 8000, 7000, 6000, 5000, 4000, 3000]})
anomalies = [
    {"service": "EC2", "increase": "65%", "reason": "scale-out event"},
    {"service": "RDS", "increase": "40%", "reason": "backup job"}
]
ai_insights = [
    "Idle EC2 instances detected",
    "Savings plan opportunity",
    "S3 lifecycle optimization"
]
finops_kpis = {
    "Monthly Spend": "$120k",
    "Unit Cost": "$0.21 per transaction",
    "Waste": "$18k",
    "Savings Potential": "$35k"
}

st.set_page_config(page_title="Executive FinOps Dashboard", layout="wide")

page = st.sidebar.selectbox(
    "Select Dashboard Page",
    ["Cost Overview", "Cost Anomalies", "AI Recommendations", "FinOps KPIs"]
)

if page == "Cost Overview":
    st.title("Cost Overview")
    st.subheader("Monthly Cost Trend")
    st.line_chart(monthly_cost.set_index("Month"))
    st.subheader("Service Breakdown")
    st.bar_chart(service_breakdown.set_index("Service"))
    st.subheader("Top 10 Cost Drivers")
    st.bar_chart(top_drivers.set_index("Service"))

elif page == "Cost Anomalies":
    st.title("Cost Anomalies")
    for anomaly in anomalies:
        st.warning(f"⚠ Cost spike detected\nService: {anomaly['service']}\nIncrease: {anomaly['increase']}\nPossible reason: {anomaly['reason']}")

elif page == "AI Recommendations":
    st.title("AI Cloud Advisor Insights")
    for insight in ai_insights:
        st.write(f"• {insight}")

elif page == "FinOps KPIs":
    st.title("FinOps KPIs")
    st.table(finops_kpis)
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
