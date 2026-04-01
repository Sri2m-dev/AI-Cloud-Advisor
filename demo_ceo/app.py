import streamlit as st
import pandas as pd
import plotly.express as px

st.markdown("""
<style>
.kpi-card {
    padding: 20px;
    border-radius: 14px;
    color: white;
    transition: all 0.25s ease;
    cursor: pointer;
}

/* HOVER EFFECT */
.kpi-card:hover {
    transform: translateY(-8px) scale(1.02);
    box-shadow: 0 20px 40px rgba(0,0,0,0.25);
}

/* TEXT */
.kpi-title {
    font-size: 14px;
    opacity: 0.9;
}
.kpi-value {
    font-size: 28px;
    font-weight: 700;
}
.kpi-sub {
    font-size: 13px;
    opacity: 0.85;
}
</style>
""", unsafe_allow_html=True)

# -----------------------
# PAGE CONFIG
# -----------------------
st.set_page_config(page_title="AI Cloud Advisor", layout="wide")

# -----------------------
# HEADER
# -----------------------
def render_header():
    st.markdown("""
        <div style="text-align:center; padding: 10px 0;">
            <h1 style="margin-bottom:0;">☁️ AI Cloud Advisor</h1>
            <p style="color:gray; font-size:16px;">
                Executive Cost & Savings Report — March 2026
            </p>
        </div>
    """, unsafe_allow_html=True)

# -----------------------
# EXECUTIVE SNAPSHOT
# -----------------------
def render_executive_snapshot():
    st.markdown("## 📊 1. Executive Snapshot")

    def card(title, value, sub, color):
        return f"""
        <div class="kpi-card" style="background:{color};">
            <div class="kpi-title">{title}</div>
            <div class="kpi-value">{value}</div>
            <div class="kpi-sub">{sub}</div>
        </div>
        """

    col1, col2, col3, col4 = st.columns(4)

    col1.markdown(card("Monthly Spend", "$6,500", "Current Month", "#3b82f6"), unsafe_allow_html=True)
    col2.markdown(card("Yearly Projection", "$78,000", "Forecast", "#7c3aed"), unsafe_allow_html=True)
    col3.markdown(card("Top Service", "Amazon EC2", "76% of spend", "#14b8a6"), unsafe_allow_html=True)
    col4.markdown(card("Savings Opportunity", "$3,294", "Potential Optimization", "#22c55e"), unsafe_allow_html=True)

# -----------------------
# COST DRIVERS
# -----------------------
def render_cost_drivers():
    st.markdown("## 🔍 2. Primary Cost Drivers")

    df = pd.DataFrame({
        "Service": ["Compute", "Databases", "Storage", "Networking", "Analytics"],
        "Cloud": ["AWS", "Azure", "AWS", "AWS", "Azure"],
        "Cost (€)": [17800, 8900, 6200, 4100, 3300],
        "MoM Change": ["+14%", "+9%", "+5%", "+18%", "+11%"],
        "Cause": [
            "Oversized instances",
            "Over-provisioned DB",
            "No lifecycle policy",
            "Cross-region traffic",
            "Uncontrolled batch jobs"
        ]
    })

    st.dataframe(df, use_container_width=True)

    fig = px.bar(df, x="Service", y="Cost (€)", color="Cloud", title="Cost Distribution")
    st.plotly_chart(fig, use_container_width=True)

# -----------------------
# COST SAVINGS
# -----------------------
def render_savings():
    st.markdown("## 💰 3. Cost Reduction Opportunity")

    col1, col2, col3 = st.columns(3)
    col1.metric("No-disruption", "€5,200")
    col2.metric("Controlled Optimization", "€3,100")
    col3.metric("Total Savings", "€8,300")

    st.success("~20% cost reduction achievable without impacting business operations.")

# -----------------------
# COST OWNERSHIP
# -----------------------
def render_ownership():
    st.markdown("## 📊 4. Cost Ownership")

    df = pd.DataFrame({
        "Business Unit": ["Product & Engineering", "Customer Ops", "Data & AI", "Platform", "Unowned"],
        "Monthly (€)": [21600, 10200, 6800, 2500, 1200],
        "%": [51, 24, 16, 6, 3]
    })

    st.dataframe(df, use_container_width=True)

# -----------------------
# RECOMMENDATIONS
# -----------------------
def render_recommendations():
    st.markdown("## 🎯 Recommended Actions")

    st.markdown("""
    - ✅ Right-size compute (AWS EC2)  
    - ✅ Optimize Azure DB capacity  
    - ✅ Apply storage lifecycle policies  
    - ✅ Reduce cross-region transfer  
    """)

# -----------------------
# CEO SUMMARY
# -----------------------
def render_ceo_summary():
    st.markdown("## 🧠 CEO Bottom Line")

    st.warning("""
Cloud cost is increasing faster than business growth.

• Compute is the primary cost driver  
• €8.3K monthly savings identified  
• Immediate optimization required  

**Bottom Line:** ~€100K annual savings achievable with low risk.
""")

# -----------------------
# MAIN
# -----------------------
def main():
    render_header()
    render_executive_snapshot()
    render_cost_drivers()
    render_savings()
    render_ownership()
    render_recommendations()
    render_ceo_summary()

if __name__ == "__main__":
    main()