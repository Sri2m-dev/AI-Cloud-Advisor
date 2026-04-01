import streamlit as st
import pandas as pd
import plotly.express as px

st.markdown("""
<style>
/* GLOBAL FONT */
html, body, [class*="css"]  {
    font-family: 'Inter', sans-serif;
}

/* MAIN TITLE (AI Cloud Advisor) */
.stApp h1, h1, [data-testid="stMarkdownContainer"] h1 {
    font-size: 60px !important;
    font-weight: 700 !important;
    line-height: 1.1 !important;
    margin-bottom: 10px !important;
}

/* SECTION TITLES (1. Executive Snapshot, 2. Primary Cost Drivers) */
.stApp h2, h2, [data-testid="stMarkdownContainer"] h2 {
    font-size: 44px !important;
    font-weight: 600 !important;
    line-height: 1.15 !important;
    margin-top: 32px !important;
    margin-bottom: 16px !important;
}

/* SUB SECTIONS (Cost Drivers Breakdown, Cost Distribution) */
.stApp h3, h3, [data-testid="stMarkdownContainer"] h3 {
    font-size: 20px !important;
    font-weight: 600 !important;
    line-height: 1.2 !important;
    margin-top: 24px !important;
    margin-bottom: 14px !important;
}

.subtitle-20 {
    font-size: 20px !important;
    font-weight: 600 !important;
    line-height: 1.2 !important;
    margin-top: 24px !important;
    margin-bottom: 14px !important;
}

/* BODY TEXT */
p, span, div {
    font-size: 16px;
}

/* TABLE FONT */
[data-testid="stDataFrame"] {
    font-size: 14px;
}

/* KPI TEXT */
.kpi-title {
    font-size: 16px !important;
}

.kpi-value {
    font-size: 36px !important;
    font-weight: 700;
}

.kpi-sub {
    font-size: 14px !important;
}

/* Explicit heading targets (only highlighted areas) */
.hero-title {
    font-size: 80px !important;
    font-weight: 800 !important;
    line-height: 1.05 !important;
    margin: 0 !important;
}

.major-section {
    font-size: 30px !important;
    font-weight: 700 !important;
    line-height: 1.1 !important;
    margin: 28px 0 14px 0 !important;
}

.major-section-text {
    font-size: 30px !important;
    font-weight: 700 !important;
    line-height: 1.1 !important;
    margin: 28px 0 14px 0 !important;
}

.hero-subtitle {
    font-size: 30px !important;
    color: gray;
    margin-top: 8px !important;
}

/* Hard-targeted header text classes */
.hero-title-text {
    font-size: 80px !important;
    font-weight: 800 !important;
    line-height: 1.05 !important;
    margin: 0 !important;
}

.hero-subtitle-text {
    font-size: 30px !important;
    color: gray;
    margin-top: 8px !important;
}

/* FIX: prevent unwanted shrinking */
strong {
    font-weight: 600;
}

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

/* Table container */
[data-testid="stDataFrame"] {
    border-radius: 12px;
    border: 1px solid #e5e7eb;
    overflow: hidden;
}

/* Header */
[data-testid="stDataFrame"] thead th {
    background-color: #f9fafb !important;
    font-weight: 600;
    font-size: 14px;
}

/* Rows */
[data-testid="stDataFrame"] tbody tr {
    border-bottom: 1px solid #f1f5f9;
}

/* Data cells */
[data-testid="stDataFrame"] tbody td {
    font-size: 17px;
}

/* Hover effect */
[data-testid="stDataFrame"] tbody tr:hover {
    background-color: #f9fafb;
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
    <div class="hero-title-text">☁️ AI Cloud Advisor</div>
    <div class="hero-subtitle-text">Executive Cost & Savings Report — March 2026</div>
</div>
    """, unsafe_allow_html=True)

# -----------------------
# EXECUTIVE SNAPSHOT
# -----------------------
def render_executive_snapshot():
    st.markdown('<div class="major-section-text">📊 Executive Snapshot</div>', unsafe_allow_html=True)

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
    st.markdown('<div class="major-section-text">🔍 Primary Cost Drivers</div>', unsafe_allow_html=True)

    df = pd.DataFrame({
        "Service": ["Compute", "Databases", "Storage", "Networking", "Analytics"],
        "Cloud": ["AWS", "Azure", "AWS", "AWS", "Azure"],
        "Cost": [17800, 8900, 6200, 4100, 3300],
        "MoM": ["+14%", "+9%", "+5%", "+18%", "+11%"],
        "Cause": [
            "Oversized instances",
            "Over-provisioned DB",
            "No lifecycle policy",
            "Cross-region traffic",
            "Uncontrolled batch jobs"
        ]
    })

    top = df.sort_values(by="Cost", ascending=False).iloc[0]

    st.warning(
        f"🔥 Top Cost Driver: {top['Service']} ({top['Cloud']}) — "
        f"{top['MoM']} increase driven by {top['Cause']}"
    )

    st.markdown('<h3 class="subtitle-20">Cost Drivers Breakdown</h3>', unsafe_allow_html=True)

    df_display = df.copy()

    # Format values
    df_display["Cost (€)"] = df_display["Cost"].apply(lambda x: f"€{x:,.0f}")

    def format_mom(x):
        val = int(str(x).replace("%", "").replace("+", ""))
        if val >= 10:
            return f"🔴 {val}%"
        else:
            return f"🟢 {val}%"

    df_display["MoM Change"] = df_display["MoM"].apply(format_mom)

    icons = {
        "Compute": "💻 Compute",
        "Databases": "🗄️ Databases",
        "Storage": "📦 Storage",
        "Networking": "🌐 Networking",
        "Analytics": "📊 Analytics"
    }

    df_display["Service"] = df_display["Service"].map(icons)

    df_display = df_display[["Service", "Cloud", "Cost (€)", "MoM Change", "Cause"]]

    st.dataframe(df_display, use_container_width=True, hide_index=True)

    df_chart = df.copy()
    if "Cost" not in df_chart.columns and "Cost (€)" in df_chart.columns:
        df_chart["Cost"] = df_chart["Cost (€)"]

    st.markdown('<h3 class="subtitle-20">Cost Distribution by Service</h3>', unsafe_allow_html=True)

    fig = px.bar(
        df_chart,
        x="Service",
        y="Cost",
        color="Cloud",
        text="Cost"
    )

    fig.update_traces(
        texttemplate='€%{text:,.0f}',
        textposition='outside',
        textfont=dict(size=18)
    )

    fig.update_layout(
        height=400,
        plot_bgcolor='white',
        paper_bgcolor='white',
        font=dict(size=16),
        xaxis=dict(title_font=dict(size=18), tickfont=dict(size=16)),
        yaxis=dict(title_font=dict(size=18), tickfont=dict(size=16)),
        legend=dict(title_font=dict(size=16), font=dict(size=16))
    )
    st.plotly_chart(fig, use_container_width=True)

# -----------------------
# COST SAVINGS
# -----------------------
def render_savings():
    st.markdown('<div class="major-section-text">💰 Cost Reduction Opportunity</div>', unsafe_allow_html=True)

    def savings_card(title, value, subtitle, color):
        return f"""
        <div class="kpi-card" style="background:{color};">
            <div class="kpi-title">{title}</div>
            <div class="kpi-value">{value}</div>
            <div class="kpi-sub">{subtitle}</div>
        </div>
        """

    col1, col2, col3 = st.columns(3)
    col1.markdown(savings_card("No-disruption", "€5,200", "Low-risk actions", "#14b8a6"), unsafe_allow_html=True)
    col2.markdown(savings_card("Controlled Optimization", "€3,100", "Planned improvements", "#3b82f6"), unsafe_allow_html=True)
    col3.markdown(savings_card("Total Savings", "€8,300", "Combined opportunity", "#22c55e"), unsafe_allow_html=True)

    st.success("~20% cost reduction achievable without impacting business operations.")

# -----------------------
# COST OWNERSHIP
# -----------------------
def render_ownership():
    st.markdown('<div class="major-section-text">📊 Cost Ownership</div>', unsafe_allow_html=True)

    df = pd.DataFrame({
        "Business Unit": ["Product & Engineering", "Customer Ops", "Data & AI", "Platform", "Unowned"],
        "Monthly (€)": [21600, 10200, 6800, 2500, 1200],
        "%": [51, 24, 16, 6, 3]
    })

    df_display = df.copy()
    ownership_icons = {
        "Product & Engineering": "🛠️ Product & Engineering",
        "Customer Ops": "🎧 Customer Ops",
        "Data & AI": "🤖 Data & AI",
        "Platform": "🧱 Platform",
        "Unowned": "❓ Unowned"
    }

    df_display["Business Unit"] = df_display["Business Unit"].map(ownership_icons)
    df_display["Monthly (€)"] = df_display["Monthly (€)"].apply(lambda x: f"€{x:,.0f}")

    def format_pct(x):
        if x >= 10:
            return f"🔴 {x}%"
        return f"🟢 {x}%"

    df_display["%"] = df_display["%"].apply(format_pct)

    st.dataframe(df_display, use_container_width=True, hide_index=True)

# -----------------------
# RECOMMENDATIONS
# -----------------------
def render_recommendations():
    st.markdown('<div class="subtitle-20">🎯 Recommended Actions</div>', unsafe_allow_html=True)

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
    st.markdown('<div class="subtitle-20">🧠 CEO Bottom Line</div>', unsafe_allow_html=True)

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