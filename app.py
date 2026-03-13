import streamlit as st

st.set_page_config(
    page_title="Cloud Advisory Platform",
    layout="wide"
)

# -------------------
# SESSION STATE
# -------------------
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

# -------------------
# LOGIN PAGE
# -------------------
def login_page():

    st.title("☁️ Cloud Advisory Platform")

    username = st.text_input("Username")
    password = st.text_input("Password", type="password")

    if st.button("Login"):

        if username == "admin" and password == "cloud123":
            st.session_state.authenticated = True
            st.switch_page("pages/dashboard.py")
            st.rerun()

        else:
            st.error("Invalid credentials")

# -------------------
# PAGE FUNCTIONS
# -------------------
def dashboard_page():
    st.title("Dashboard")
    st.write("Welcome to the Cloud Advisory Platform 🚀")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Monthly Cost", "$12,450", "5%")
    col2.metric("Forecast", "$13,100", "2%")
    col3.metric("Savings Opportunity", "$3,200")
    col4.metric("Idle Resources", "17")

    st.divider()

    st.subheader("Cost Trend")

    data = {
        "Month": ["Jan","Feb","Mar","Apr","May"],
        "Cost": [8000,9000,11000,12000,12500]
    }

    import pandas as pd
    df = pd.DataFrame(data)

    st.line_chart(df.set_index("Month"))

def ai_advisor_page():
    st.title("AI FinOps Advisor")

    st.write("AI-driven cloud cost optimization recommendations")

    if st.button("Generate AI Recommendations"):
        st.success("Recommendations Generated")
        st.markdown("""
        **EC2 Optimization**

        • 3 EC2 instances are underutilized  
        • Recommended: downgrade from m5.large → t3.medium  

        **Estimated Monthly Savings:** $840
        """)

def cost_explorer_page():
    st.title("Cost Explorer")

    import pandas as pd

    data = {
        "Service": ["EC2","S3","RDS","Lambda"],
        "Cost": [5000,2000,3000,450]
    }

    df = pd.DataFrame(data)

    st.subheader("Service Cost Breakdown")

    st.dataframe(df)

    st.bar_chart(df.set_index("Service"))

def finops_insights_page():
    st.title("FinOps Insights")

    st.subheader("Cost Allocation by Team")

    import pandas as pd

    data = {
        "Team":["Platform","Data","DevOps","AI"],
        "Cost":[4000,3500,2800,2150]
    }

    df = pd.DataFrame(data)

    st.bar_chart(df.set_index("Team"))

def optimization_page():
    st.title("Optimization Opportunities")

    st.warning("Idle resources detected")

    st.write("""
    • 5 unattached EBS volumes  
    • 2 idle load balancers  
    • 3 underutilized EC2 instances
    """)

    st.metric("Potential Savings", "$1,750 / month")

def optimization_insights_page():
    st.title("Optimization Insights")

    st.info("Top Cost Drivers")

    import pandas as pd

    data = {
        "Service":["EC2","RDS","S3","Data Transfer"],
        "Cost":[5000,3000,2000,900]
    }

    df = pd.DataFrame(data)

    st.bar_chart(df.set_index("Service"))

def reports_page():
    st.title("Reports")

    st.write("Generate FinOps reports")

    if st.button("Generate Monthly Report"):
        st.success("Report generated successfully")

    if st.button("Download CSV"):
        st.info("Download feature coming soon")

# -------------------
# APP FLOW
# -------------------

if not st.session_state.authenticated:
    login_page()
    st.stop()

# Sidebar logout
with st.sidebar:
    st.button("Logout", on_click=lambda: st.session_state.update(authenticated=False))

# Navigation
pg = st.navigation(
    [
        st.Page(dashboard_page, title="Dashboard", default=True),
        st.Page(ai_advisor_page, title="AI Advisor"),
        st.Page(cost_explorer_page, title="Cost Explorer"),
        st.Page(finops_insights_page, title="FinOps Insights"),
        st.Page(optimization_page, title="Optimization"),
        st.Page(optimization_insights_page, title="Optimization Insights"),
        st.Page(reports_page, title="Reports"),
    ]
)

pg.run()
