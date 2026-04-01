
import streamlit as st
import pandas as pd
import plotly.express as px
from services.aws_cost import get_cost_data

def render_header():
    st.markdown("""
    # ☁️ AI Cloud Advisor
    """)
    st.caption("Executive Cost Optimization Dashboard")
    st.markdown("---")

def render_executive_snapshot():
    # Example KPI cards
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Run Rate", "$42.3K", "+8.7%")
    col2.metric("30-Day Forecast", "$44K", "Upward trend")
    col3.metric("90-Day Projection", "$132K", "Sustained growth")
    col4.metric("Savings Potential", "$8.3K", "20% reducible")

def render_primary_cost_drivers():
    st.markdown("## 🔍 2. Primary Cost Drivers")
    data = [
        ["Compute", "AWS", 17800, "+14%", "Oversized instances"],
        ["Databases", "Azure", 8900, "+9%", "Over-provisioned DB"],
        ["Storage", "AWS", 6200, "+5%", "No lifecycle policy"],
        ["Networking", "AWS", 4100, "+18%", "Cross-region traffic"],
        ["Analytics", "Azure", 3300, "+11%", "Uncontrolled jobs"],
    ]
    df = pd.DataFrame(data, columns=["Service", "Cloud", "Cost ($)", "MoM", "Insight"])
    st.dataframe(df, use_container_width=True)

def render_cost_opportunity():
    st.markdown("## 💰 3. Cost Reduction Opportunity")
    col1, col2, col3 = st.columns(3)
    col1.metric("No-disruption", "$5,200")
    col2.metric("Controlled Optimization", "$3,100")
    col3.metric("Total Savings", "$8,300")
    st.success("~20% cost reduction achievable without impacting business operations.")

def render_ownership():
    st.markdown("## 📊 4. Cost Ownership")
    data = [
        ("Product & Engineering", 21600, 51),
        ("Customer Operations", 10200, 24),
        ("Data & AI", 6800, 16),
        ("Shared / Platform", 2500, 6),
        ("Unowned", 1200, 3),
    ]
    df = pd.DataFrame(data, columns=["Business Unit", "Monthly ($)", "%"])
    st.dataframe(df, use_container_width=True)

def render_recommendations():
    st.markdown("## 🎯 Recommended Actions")
    st.markdown("""
    - ✅ Right-size compute instances (AWS EC2)
    - ✅ Optimize database capacity (Azure)
    - ✅ Apply storage lifecycle policies
    - ✅ Reduce cross-region data transfer
    """)

def render_ceo_summary():
    st.markdown("## 🧠 CEO Bottom Line")
    st.warning("""
    Cloud cost is increasing faster than business growth.

    • Compute is the primary cost driver  
    • $8.3K monthly savings identified  
    • Immediate optimization required  

    **Bottom Line:** ~$100K annual savings achievable with low risk.
    """)


def render_cost_ownership():
    st.write("COST OWNERSHIP WORKING")

def render_recommended_actions():
    st.write("RECOMMENDED ACTIONS WORKING")

def render_ceo_bottom_line():
    st.write("CEO BOTTOM LINE WORKING")

def main():
    st.write("🚨 MAIN RUNNING")

    render_header()
    render_executive_snapshot()
    render_primary_cost_drivers()
    render_cost_opportunity()
    render_cost_ownership()
    render_recommended_actions()
    render_ceo_bottom_line()

if __name__ == "__main__":
    main()