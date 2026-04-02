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
    margin-top: 18px !important;
    margin-bottom: 10px !important;
    color: #111827 !important;
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

/* KPI Card Color Variants */
.kpi-card.blue {
    background: #3b82f6;
}

.kpi-card.purple {
    background: #7c3aed;
}

.kpi-card.teal {
    background: #14b8a6;
}

.kpi-card.green {
    background: #22c55e;
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

    st.info(f"""
🔥 Top Cost Driver: {top['Service']} contributing highest spend.
""")

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
    st.markdown('<div class="major-section-text">💰 Optimization Potential</div>', unsafe_allow_html=True)

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

Key Insights:
• Compute is the primary cost driver  
• €8.3K monthly savings identified  
• Immediate optimization required  

**Bottom Line:** ~€100K annual savings achievable with low risk.
""")

# -----------------------
# CTO FEATURES
# -----------------------
def render_cto_features():
    st.markdown('<div class="major-section-text">🧩 CTO Engineering View</div>', unsafe_allow_html=True)

    def cto_card(title, value, sub, color):
        return f"""
        <div class="kpi-card" style="background:{color};">
            <div class="kpi-title">{title}</div>
            <div class="kpi-value">{value}</div>
            <div class="kpi-sub">{sub}</div>
        </div>
        """

    col1, col2, col3, col4 = st.columns(4)
    col1.markdown(cto_card("Service Availability", "99.95%", "SLO compliance", "#3b82f6"), unsafe_allow_html=True)
    col2.markdown(cto_card("Deployment Frequency", "42/week", "+12% month-over-month", "#7c3aed"), unsafe_allow_html=True)
    col3.markdown(cto_card("MTTR", "28 min", "-18% month-over-month", "#14b8a6"), unsafe_allow_html=True)
    col4.markdown(cto_card("IaC Coverage", "78%", "Automated infrastructure", "#22c55e"), unsafe_allow_html=True)

    st.markdown('<h3 class="subtitle-20">Platform Reliability by Domain</h3>', unsafe_allow_html=True)

    cto_df = pd.DataFrame({
        "Domain": ["Core API", "Data Pipeline", "Auth", "Billing", "Observability"],
        "Uptime": [99.97, 99.82, 99.94, 99.76, 99.91],
        "Incidents MoM": ["-8%", "+5%", "-11%", "+9%", "-4%"],
        "Owner": ["Platform", "Data", "Security", "FinOps", "SRE"]
    })

    def format_incidents(trend):
        val = int(trend.replace("%", ""))
        if val > 0:
            return f"🔴 +{val}%"
        return f"🟢 {val}%"

    cto_display = cto_df.copy()
    cto_display["Uptime"] = cto_display["Uptime"].apply(lambda x: f"{x:.2f}%")
    cto_display["Incidents MoM"] = cto_display["Incidents MoM"].apply(format_incidents)

    st.dataframe(cto_display, use_container_width=True, hide_index=True)


def render_client_context():
    st.markdown("""
<div style="
    background:#f9fafb;
    padding:12px;
    border-radius:10px;
    border:1px solid #e5e7eb;
    margin-bottom:15px;
">
<b>Client:</b> Demo Enterprise
&nbsp;&nbsp;&nbsp;
<b>Cloud:</b> AWS + Azure
&nbsp;&nbsp;&nbsp;
<b>Report Period:</b> March 2026
</div>
""", unsafe_allow_html=True)


def render_primary_cost_drivers():
    render_cost_drivers()


def render_cost_opportunity():
    render_savings()


def sanitize_for_ai(resource):
    return {
        "resource_type": resource.get("type"),
        "cpu_avg": resource.get("cpu_avg"),
        "memory_avg": resource.get("memory_avg"),
        "monthly_cost": resource.get("monthly_cost"),
        "waste_estimate": resource.get("waste_estimate"),
        "rule_triggered": resource.get("rule_triggered")
    }


def render_infra_overview():
    def gradient_card(title, value, subtext, css_class):
        return f"""
        <div class="kpi-card {css_class}">
            <div class="kpi-title">{title}</div>
            <div class="kpi-value">{value}</div>
            <div class="kpi-sub">{subtext}</div>
        </div>
        """

    st.markdown("### Infrastructure Overview")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.markdown(gradient_card("Total Instances", "128", "Active workloads", "blue"), unsafe_allow_html=True)

    with col2:
        st.markdown(gradient_card("Avg CPU", "42%", "Utilization", "purple"), unsafe_allow_html=True)

    with col3:
        st.markdown(gradient_card("Idle Resources", "18%", "Needs cleanup", "teal"), unsafe_allow_html=True)

    with col4:
        st.markdown(gradient_card("Optimization", "€6.2K", "Monthly potential", "green"), unsafe_allow_html=True)


def render_resource_utilization():
    st.markdown("### Resource Utilization")

    utilization_data = [
        ["EC2 - m5.large", "Compute", 22, 35, "Underutilized"],
        ["EC2 - c5.xlarge", "Compute", 68, 72, "Optimal"],
        ["RDS - db.m5", "Database", 18, 40, "Over-provisioned"],
        ["S3 Storage", "Storage", 55, 60, "Optimal"],
        ["EBS Volume", "Storage", 10, 20, "Idle"],
    ]

    df_util = pd.DataFrame(
        utilization_data,
        columns=["Resource", "Type", "CPU %", "Memory %", "Status"]
    )

    df_display = df_util.copy()
    df_display.rename(columns={"Type": "Service"}, inplace=True)

    icons = {
        "Compute": "💻 Compute",
        "Database": "🗄️ Database",
        "Storage": "📦 Storage"
    }
    df_display["Service"] = df_display["Service"].map(lambda x: icons.get(x, f"⚙️ {x}"))

    def get_priority(cpu, status):
        if "Idle" in status:
            return "🔴 High"
        elif cpu > 70:
            return "🔴 High"
        elif cpu > 40:
            return "🟡 Medium"
        else:
            return "🟢 Low"

    df_display["Priority"] = df_util.apply(
        lambda row: get_priority(row["CPU %"], row["Status"]),
        axis=1
    )

    cost_map = {
        "EC2 - m5.large": 120,
        "EC2 - c5.xlarge": 220,
        "RDS - db.m5": 300,
        "S3 Storage": 80,
        "EBS Volume": 60
    }

    df_display["Monthly Cost (€)"] = df_display["Resource"].map(cost_map)

    def estimate_waste(row):
        if "Idle" in row["Status"]:
            return int(row["Monthly Cost (€)"] * 0.8)
        elif "Under" in row["Status"]:
            return int(row["Monthly Cost (€)"] * 0.5)
        else:
            return int(row["Monthly Cost (€)"] * 0.2)

    df_display["Waste (€)"] = df_display.apply(estimate_waste, axis=1)

    priority_order = {"🔴 High": 0, "🟡 Medium": 1, "🟢 Low": 2}
    df_display["priority_rank"] = df_display["Priority"].map(priority_order)

    df_display = df_display.sort_values(
        by=["priority_rank", "Waste (€)"],
        ascending=[True, False]
    )

    def color_cpu(val):
        val = int(val)
        if val > 75:
            return f"🔴 {val}%"
        elif val > 40:
            return f"🟡 {val}%"
        return f"🟢 {val}%"

    def color_mem(val):
        val = int(val)
        if val > 75:
            return f"🔴 {val}%"
        elif val > 40:
            return f"🟡 {val}%"
        return f"🟢 {val}%"

    def format_status(x):
        if "Idle" in x or "Under" in x or "Over" in x:
            return f"🔴 {x}"
        return f"🟢 {x}"

    df_display["CPU %"] = df_display["CPU %"].apply(color_cpu)
    df_display["Memory %"] = df_display["Memory %"].apply(color_mem)
    df_display["Status"] = df_display["Status"].apply(format_status)

    df_table = df_display[[
        "Service",
        "Resource",
        "Priority",
        "Monthly Cost (€)",
        "Waste (€)",
        "Status"
    ]].copy()

    df_table["Monthly Cost (€)"] = df_table["Monthly Cost (€)"].apply(lambda x: f"€{int(x):,}")
    df_table["Waste (€)"] = df_table["Waste (€)"].apply(lambda x: f"€{int(x):,}")

    df_table = df_table[[
        "Service",
        "Resource",
        "Priority",
        "Monthly Cost (€)",
        "Waste (€)",
        "Status"
    ]].astype(str)

    st.dataframe(df_table, use_container_width=True, hide_index=True)

    for _, row in df_display.iterrows():
        with st.expander(f"{row['Priority']} | {row['Service']} — {row['Resource']}"):
            st.markdown(f"""
**CPU Usage:** {row['CPU %']}  
**Memory Usage:** {row['Memory %']}  
**Monthly Cost:** €{row['Monthly Cost (€)']}  
**Estimated Waste:** €{row['Waste (€)']}  
""")
            st.markdown("### Root Cause")
            st.write("- Low utilization over 7 days")
            st.write("- No autoscaling policy")
            st.markdown("### Risk")
            st.warning("Wasted infrastructure cost accumulating monthly")
            st.markdown("### Recommendation")
            st.success("Resize instance or schedule shutdown")


def render_optimization_opportunities():
    waste_data = [
        ["Idle EC2 instances", "€2,400", "Low CPU usage (<20%)"],
        ["Over-provisioned RDS", "€1,800", "Memory underutilized"],
        ["Unattached EBS volumes", "€900", "Not linked to instances"],
        ["Unused storage tiers", "€1,100", "No lifecycle policy"],
    ]

    df_waste = pd.DataFrame(
        waste_data,
        columns=["Issue", "Monthly Waste", "Reason"]
    )

    total_savings = df_waste["Monthly Waste"].apply(
        lambda x: int(x.replace("€", "").replace(",", ""))
    ).sum()

    st.markdown(f"""
<div style="
    background: linear-gradient(135deg, #ecfdf5, #d1fae5);
    padding:18px;
    border-radius:12px;
    margin-bottom:15px;
    border:1px solid #bbf7d0;
">
    <b style="font-size:18px;">💰 Total Optimization Potential</b><br>
    <span style="font-size:28px; font-weight:700;">
        €{total_savings:,}/month
    </span>
</div>
""", unsafe_allow_html=True)

    def get_tag(issue):
        if "EC2" in issue:
            return "💻 Compute"
        elif "RDS" in issue:
            return "🗄️ Database"
        elif "EBS" in issue or "storage" in issue.lower():
            return "📦 Storage"
        return "⚙️ Other"

    st.markdown("## 🔧 Optimization Opportunities")

    df_waste_sorted = df_waste.copy()
    df_waste_sorted["waste_val"] = df_waste_sorted["Monthly Waste"].apply(
        lambda x: int(x.replace("€", "").replace(",", ""))
    )
    df_waste_sorted = df_waste_sorted.sort_values(by="waste_val", ascending=False)

    top_waste = df_waste_sorted.iloc[0]
    st.warning(f"""
🔥 Top Optimization Opportunity: {top_waste['Issue']} saving {top_waste['Monthly Waste']}
""")

    for _, row in df_waste_sorted.iterrows():
        waste_val = int(row["Monthly Waste"].replace("€", "").replace(",", ""))
        savings = int(waste_val * 0.9)

        tag = get_tag(row["Issue"])

        with st.expander(f"{tag} | {row['Issue']} — {row['Monthly Waste']}"):
            st.markdown(f"""
        **💰 Cost Impact:** {row['Monthly Waste']}  
        **📉 Root Cause:** {row['Reason']}  
        """)

            if "EC2" in row["Issue"]:
                rec = "Resize instance or schedule shutdown"
            elif "RDS" in row["Issue"]:
                rec = "Reduce DB size or enable autoscaling"
            elif "EBS" in row["Issue"]:
                rec = "Delete unattached volumes"
            else:
                rec = "Optimize storage tiering"

            st.markdown(f"""
        **🛠 Recommendation:** {rec}  
        **💡 Estimated Savings:** €{savings}/month  
        """)

            if st.button(f"Apply Fix for {row['Issue']}", key=row['Issue']):
                st.success("✅ Optimization applied (simulated)")

    csv = df_waste_sorted.to_csv(index=False).encode('utf-8')

    st.download_button(
        label="📥 Download Optimization Report",
        data=csv,
        file_name="cloud_optimization_report.csv",
        mime="text/csv",
    )


def render_architecture_risks():
    st.markdown("### Architecture Risks")

    risks = [
        ("Single AZ Deployment", "High Availability Risk", "No failover configured"),
        ("No Auto Scaling", "Scalability Risk", "Manual scaling may cause outages"),
        ("Cross-region Traffic", "Cost Risk", "High data transfer charges"),
        ("Unmonitored Batch Jobs", "Operational Risk", "Jobs running without limits"),
    ]

    for risk in risks:
        st.markdown(f"""<div style="background:#fff7ed; border-left:5px solid #f97316; padding:14px; border-radius:8px; margin-bottom:10px;"><b>{risk[0]}</b><br>{risk[1]}<br><span style="color:#6b7280;">{risk[2]}</span></div>""", unsafe_allow_html=True)


def render_ceo_dashboard():
    st.caption("High-level overview of cloud cost performance and savings potential")
    st.markdown("<br>", unsafe_allow_html=True)
    render_executive_snapshot()
    st.markdown("---")
    st.markdown("<br>", unsafe_allow_html=True)
    render_primary_cost_drivers()
    st.markdown("---")
    st.markdown("<br>", unsafe_allow_html=True)
    render_cost_opportunity()
    st.markdown("<br>", unsafe_allow_html=True)
    render_ceo_summary()


def render_cto_dashboard():
    st.markdown('<div class="major-section-text">🛠️ CTO Dashboard</div>', unsafe_allow_html=True)
    st.caption("Deep technical analysis of infrastructure efficiency and optimization opportunities")
    st.markdown("<br>", unsafe_allow_html=True)
    render_infra_overview()
    st.markdown("<br>", unsafe_allow_html=True)
    render_resource_utilization()
    st.markdown("<br>", unsafe_allow_html=True)
    render_optimization_opportunities()
    st.markdown("---")
    st.markdown("<br>", unsafe_allow_html=True)
    render_architecture_risks()
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("### ℹ️ How Intelligence Works")
    st.info("""
Optimization decisions are generated using deterministic rules.

An optional intelligence layer enhances explanations using 
enterprise-grade LLMs without accessing sensitive data.

This layer can be disabled without impacting core functionality.
""")

# -----------------------
# MAIN
# -----------------------
def main():
    render_header()
    render_client_context()

    view = st.radio(
        "Dashboard View",
        ["CEO Dashboard", "CTO Dashboard"],
        horizontal=True,
        label_visibility="collapsed"
    )

    if view == "CEO Dashboard":
        render_ceo_dashboard()
    else:
        render_cto_dashboard()

if __name__ == "__main__":
    main()