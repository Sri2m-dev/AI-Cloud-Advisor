import os
import streamlit as st

ENV = os.getenv("APP_ENV", "demo")  # default = demo
st.write("ENV MODE:", ENV)  # TEMP debug, remove if not needed

def load_demo_ceo_data():
    import pandas as pd
    return pd.DataFrame({
        'business_unit': ['A', 'B', 'C'],
        'monthly_spend': [10000, 15000, 12000],
        'percentage': [40, 35, 25]
    })

def connect_db():
    try:
        PGHOST = st.secrets["PGHOST"]
    except Exception:
        PGHOST = os.getenv("PGHOST")  # local fallback
    st.write("Connected to:", PGHOST)
    # Return a DB connection object (placeholder: None)
    return None

def load_real_data(conn):
    import pandas as pd
    # Use conn to load real data (placeholder)
    return pd.DataFrame()  # Placeholder for real DB data

if ENV == "demo":
    df = load_demo_ceo_data()
else:
    conn = connect_db()
    df = load_real_data(conn)
    st.write("API Demo: Cost Data from Backend")

# Inject global CSS for professional KPI cards (ONLY ONCE at top)
st.markdown("""
<style>

/* KPI Cards */
.kpi-card {
    background: linear-gradient(135deg, #ffffff, #f8fafc);
    padding: 18px 20px;
    border-radius: 14px;
    border: 1px solid #E5E7EB;
    box-shadow: 0 4px 12px rgba(0,0,0,0.05);
    transition: all 0.25s ease-in-out;
    position: relative;
}

/* Accent line */
.kpi-card::before {
    content: "";
    position: absolute;
    top: 0;
    left: 0;
    height: 4px;
    width: 100%;
    background: linear-gradient(90deg, #3B82F6, #6366F1);
}

/* Hover */
.kpi-card:hover {
    transform: translateY(-5px);
    box-shadow: 0 12px 28px rgba(59,130,246,0.15);
}

/* Text styles */
.kpi-title {
    font-size: 13px;
    color: #6B7280;
    margin-bottom: 8px;
}

.kpi-value {
    font-size: 28px;
    font-weight: 700;
    color: #111827;
}

.kpi-trend {
    font-size: 13px;
    margin-top: 6px;
}

.positive { color: #16A34A; }
.negative { color: #DC2626; }

</style>
""", unsafe_allow_html=True)

import streamlit as st
st.set_page_config(layout="wide")

# Professional KPI Card CSS
st.markdown("""
<style>

/* Page background */
.main {
    background-color: #f5f7fb;
}

/* KPI Cards */
.kpi-card {
    background: #ffffff;
    padding: 18px;
    border-radius: 12px;
    border: 1px solid #e5e7eb;
    box-shadow: 0 2px 6px rgba(0,0,0,0.05);
    height: 140px;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
}

/* Title */
.kpi-title {
    font-size: 13px;
    color: #6b7280;
}

/* Value */
.kpi-value {
    font-size: 28px;
    font-weight: 600;
    color: #111827;
}

/* Delta */
.kpi-delta {
    font-size: 13px;
    color: #16a34a;
}

</style>
""", unsafe_allow_html=True)

# --- AI Insights Function ---


def generate_ai_insights(summary_df, drivers_df):
    insights = []

    run_rate = summary_df["current_month_runrate"][0]
    mom = summary_df["mom_change_percent"][0]

    if mom > 5:
        insights.append(f"📈 Costs increased by {mom}%. Investigate recent changes.")

    # 🔍 Detect correct column dynamically
    possible_cols = ["cost", "value", "amount", "monthly_cost"]
    cost_col = None
    for col in possible_cols:
        if col in drivers_df.columns:
            cost_col = col
            break

    if cost_col:
        top_driver = drivers_df.sort_values(cost_col, ascending=False).iloc[0]
        # Check for 'service' column, else use first non-cost column
        if 'service' in drivers_df.columns:
            driver_label = top_driver['service']
        else:
            # Fallback: use first non-cost column
            non_cost_cols = [col for col in drivers_df.columns if col != cost_col]
            driver_label = top_driver[non_cost_cols[0]] if non_cost_cols else 'Unknown'
        insights.append(
            f"💰 Highest cost driver is {driver_label} (€{top_driver[cost_col]:,})."
        )
        # Only add compute recommendation if 'service' column exists and value is 'compute'
        if 'service' in drivers_df.columns and str(top_driver['service']).lower() == "compute":
            insights.append("⚙️ Consider Reserved Instances or Savings Plans for compute.")
    else:
        insights.append("⚠️ Unable to determine cost column in cost drivers table.")

    return insights
# Custom KPI card function
def kpi_card(title, value, delta, icon, color):
            import re
            # Remove all HTML tags from value and delta
            clean_value = re.sub(r'<.*?>', '', str(value))
            clean_delta = re.sub(r'<.*?>', '', str(delta))
            st.markdown(f"""
                <div style="
                    background-color:{color};
                    padding:20px;
                    border-radius:12px;
                    box-shadow:0px 2px 8px rgba(0,0,0,0.05);
                    min-height:120px;
                ">
                    <div style="font-size:14px; color:#666;">{icon} {title}</div>
                    <div style="font-size:28px; font-weight:600; margin-top:5px;">
                        {clean_value}
                    </div>
                    <div style="font-size:14px; color:green; margin-top:5px;">
                        {clean_delta}
                    </div>
                </div>
            """, unsafe_allow_html=True)
# Clean helper function for loading tables

def load_table(table_name):
    if ENV != "demo":
        return pd.DataFrame(supabase.table(table_name).select("*").execute().data) if supabase else pd.DataFrame()
    else:
        return pd.DataFrame()

import streamlit as st
import pandas as pd
try:
    from supabase import create_client
except ImportError:
    st.error("Supabase client not installed. Please install with 'pip install supabase-py'.")
    create_client = None

# -----------------------
# CONFIG
# -----------------------

st.set_page_config(page_title="CEO Dashboard", layout="wide")



supabase = create_client(SUPABASE_URL, SUPABASE_KEY) if create_client else None
def load_table(schema, table_name):

if ENV != "demo":
    SUPABASE_URL = "https://uuebwablmphflqccgtrr.supabase.co"
    SUPABASE_KEY = "sb_publishable_GsrUjTNd6Zctu3ps8IrMjQ_gGFIUeKu"
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY) if create_client else None

    def load_table(schema, table_name):
        if supabase:
            return pd.DataFrame(
                supabase.schema(schema).table(table_name).select("*").execute().data
            )
        else:
            return pd.DataFrame()

    summary_df = load_table("public", "executive_summary")
    drivers_df = load_table("public", "cost_drivers")
    savings_df = load_table("public", "savings_opportunities")
    units_df = load_table("public", "business_units")
    ownership_df = units_df.copy()
    pipeline_df = load_table("public", "savings_pipeline")
else:
    summary_df = pd.DataFrame()
    drivers_df = pd.DataFrame()
    savings_df = pd.DataFrame()
    units_df = pd.DataFrame()
    ownership_df = pd.DataFrame()
    pipeline_df = pd.DataFrame()

# st.write("executive_summary columns:", summary_df.columns.tolist())
# st.write("executive_summary sample:", summary_df.head())


# -----------------------
# HEADER
# -----------------------
# HEADER
st.markdown("""
<h1 style='margin-bottom: 4px;'>☁️ AI Cloud Advisor</h1>

<p style='
    color:#4B5563;
    font-size:16px;
    font-weight:500;
    margin-top:0px;
    margin-bottom:12px;
'>
Executive Cost & Savings Dashboard
</p>
""", unsafe_allow_html=True)

# INSIGHT BANNER (consistent styling)
st.markdown("""
<div style="
    background-color:#EEF4FF;
    padding:14px;
    border-radius:8px;
    border-left:4px solid #3B82F6;
    margin-top:20px;
    margin-bottom:20px;
">
    <span style="color:#1E3A8A; font-size:14px;">
    Cloud spend is increasing month-over-month, primarily driven by compute and data platform usage.
    </span>
</div>
""", unsafe_allow_html=True)
st.markdown("## 💼 Executive Overview")
# KPI SECTION
# -----------------------


# --- PROFESSIONAL KPI CARDS (STATIC HTML) ---
col1, col2, col3, col4 = st.columns(4)

with col1:
    st.markdown("""
    <div class="kpi-card blue">
        <div class="kpi-title">💰 Run Rate</div>
        <div class="kpi-value">€42,300</div>
        <div class="kpi-trend positive">+8.7%</div>
    </div>
    """, unsafe_allow_html=True)

with col2:
    st.markdown("""
    <div class="kpi-card green">
        <div class="kpi-title">📉 MoM Change</div>
        <div class="kpi-value">8.7%</div>
        <div class="kpi-trend positive">Trend improving</div>
    </div>
    """, unsafe_allow_html=True)

with col3:
    st.markdown("""
    <div class="kpi-card purple">
        <div class="kpi-title">📊 30-Day Forecast</div>
        <div class="kpi-value">€44,000</div>
        <div class="kpi-trend positive">+3% vs last month</div>
    </div>
    """, unsafe_allow_html=True)

with col4:
    st.markdown("""
    <div class="kpi-card orange">
        <div class="kpi-title">📈 90-Day Forecast</div>
        <div class="kpi-value">€132,000</div>
    </div>
    """, unsafe_allow_html=True)

# -----------------------
# COST DRIVERS
# -----------------------

st.markdown("## 💰 Spend by Business Unit")
st.markdown("## 🚀 Top Cost Drivers (Where money is going)")
import plotly.express as px
# Fallback for empty data
if drivers_df.empty:
    st.info("No cost driver data available")
elif "service" in drivers_df.columns and "cost" in drivers_df.columns:
    # Sort by cost descending and take top 5
    top5_df = drivers_df.sort_values("cost", ascending=False).head(5)
    # Optional: filter out zero or negative cost if needed
    top5_df = top5_df[top5_df["cost"] > 0]
    fig = px.bar(
        top5_df,
        x="service",
        y="cost",
        text="cost",
        color="service",
        color_discrete_sequence=px.colors.qualitative.Safe
    )
    fig.update_traces(
        texttemplate="€%{text:,.0f}",
        textposition="outside"
    )
    fig.update_layout(
        xaxis_title="Service",
        yaxis_title="Cost (€)",
        plot_bgcolor="white",
        paper_bgcolor="white",
        font=dict(color="#111827"),
        margin=dict(t=30, b=30),
        xaxis=dict(tickangle=0),
        showlegend=False
    )
    st.plotly_chart(fig, use_container_width=True)
if 'ownership_df' in locals() and not ownership_df.empty:
    # FINAL DEMO FLOW: Add insight above chart
    if (
        "monthly_spend" in ownership_df.columns and
        "business_unit" in ownership_df.columns and
        not ownership_df.empty
    ):
        ownership_df["monthly_spend"] = pd.to_numeric(ownership_df["monthly_spend"], errors="coerce").fillna(0)
        ownership_df = ownership_df.sort_values(by="monthly_spend", ascending=False)
        top_unit = ownership_df.iloc[0]
        st.success(
            f"{top_unit['business_unit']} contributes the highest spend at €{top_unit['monthly_spend']:,.0f} per month."
        )
        # Remove small/noisy categories
        ownership_df = ownership_df[ownership_df["monthly_spend"] > 0]
        # Chart
        fig = px.bar(
            ownership_df,
            x="business_unit",
            y="monthly_spend",
            text="monthly_spend"
        )
        fig.update_traces(
            texttemplate="€%{text:,.0f}",
            textposition="outside"
        )
        fig.update_layout(
            xaxis_title="",
            yaxis_title="Monthly Spend (€)",
            plot_bgcolor="white",
            paper_bgcolor="white",
            xaxis=dict(tickangle=0),
        )
        st.plotly_chart(fig, use_container_width=True)
        # Format for table display
        ownership_df["monthly_spend"] = ownership_df["monthly_spend"].apply(lambda x: f"€{x:,.0f}")
        # Show only key columns
        if all(col in ownership_df.columns for col in ["business_unit", "monthly_spend", "percentage"]):
            st.dataframe(ownership_df[["business_unit", "monthly_spend", "percentage"]])
        else:
            st.dataframe(ownership_df[[c for c in ["business_unit", "monthly_spend"] if c in ownership_df.columns]])
else:
    st.info("No ownership data available.")
# -----------------------
# KEY TAKEAWAYS
# -----------------------
st.markdown("## 🧠 Key Takeaways")
st.write("""
- Compute and Product Engineering are primary cost drivers  
- Spend is trending upward (+8.7% MoM)  
- Optimization opportunity exists in shared/platform workloads  
""")

# -----------------------
# SAVINGS
# -----------------------

st.subheader("Savings Opportunity")
if not savings_df.empty and "monthly_impact" in savings_df:
    total_savings = savings_df["monthly_impact"].sum()
    st.success(f"💰 Total Potential Savings: €{total_savings:,} / month")
else:
    st.info("No savings opportunity data available.")

# -----------------------
# PIPELINE
# -----------------------

st.subheader("Savings Pipeline")
if not pipeline_df.empty:
    st.dataframe(pipeline_df)
else:
    st.info("No savings pipeline data available.")


# -----------------------
# AI INSIGHTS & RECOMMENDATIONS
# -----------------------
st.markdown("## 🧠 AI Insights & Recommendations")
insights = generate_ai_insights(summary_df, drivers_df)
for insight in insights:
    st.markdown(f"""
        <div style="
            background-color:#F9FAFB;
            padding:15px;
            border-radius:10px;
            margin-bottom:10px;
            border-left:5px solid #6366F1;
        ">
            {insight}
        </div>
    """, unsafe_allow_html=True)

# -----------------------
# EXECUTIVE MESSAGE
# -----------------------
if not summary_df.empty:
    data = summary_df.iloc[0]
    if "executive_takeaway" in data:
        st.info(data["executive_takeaway"])
