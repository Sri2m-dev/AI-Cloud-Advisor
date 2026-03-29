import streamlit as st
import pandas as pd

from data_loader import load_data
from analytics_engine import compute_summary
from dashboard_views import render_executive_snapshot, render_service_breakdown, render_cost_by_service, render_cost_forecast, render_ai_insights, render_monthly_trend, render_top_optimization_opportunities, render_optimization_recommendations, render_cost_anomaly_detection

# ---- HERO SECTION ----
st.markdown("""
<div style="
    text-align:center;
    padding: 60px 20px 30px 20px;
">
    <h1 style="font-size:44px; font-weight:700;">
        ☁ Cloud Advisory Platform
    </h1>
    <p style="font-size:18px; color:#6b7280;">
        AI-Driven Cloud Cost Intelligence & Transformation Advisory
    </p>
</div>
""", unsafe_allow_html=True)

st.title("Cloud Advisory Platform")

st.markdown("""
<style>

.snapshot-card {
    background: white;
    padding: 22px;
    border-radius: 16px;
    box-shadow: 0 6px 18px rgba(0,0,0,0.08);
    border-left: 6px solid #2563eb;
    height: 140px;                 /* force equal height */
    display:flex;
    flex-direction:column;
    justify-content:center;
    box-shadow:0 6px 18px rgba(0,0,0,0.08); /* SaaS dashboard card look */
}


.snapshot-title {
    font-size: 18px;
    color: #4b5563;
    font-weight: 700;
}

.snapshot-value {
    font-size: 18px;
    font-weight: 500;
    color: #111827;
}

.snapshot-card:hover {
    transform: translateY(-3px);
    box-shadow: 0 14px 30px rgba(0,0,0,0.12);
}

</style>
""", unsafe_allow_html=True)

uploaded_file = st.file_uploader("Upload Billing CSV", type=["csv"])

if uploaded_file is not None:
    df = pd.read_csv(uploaded_file)
    date_column = None
    for col in df.columns:
        if "UsageStartDate" in col or "BillingPeriodStartDate" in col:
            date_column = col
            break
    if date_column:
        df[date_column] = pd.to_datetime(df[date_column])
        df["Month"] = df[date_column].dt.strftime("%b")
    # Clean columns
    df = df.loc[:, ~df.columns.str.contains("^Unnamed")]
    df = df.dropna(axis=1, how="all")

    # Ensure required columns exist
    if "Service" in df.columns and "Cost" in df.columns:
        total_spend = df["Cost"].sum()

        top_service = (
            df.groupby("Service")["Cost"]
            .sum()
            .sort_values(ascending=False)
            .index[0]
        )

        estimated_savings = total_spend * 0.22

        summary = {
            "total_spend": total_spend,
            "top_service": top_service,
            "estimated_savings": estimated_savings
        }
        st.markdown("### Currency")
        currency = st.selectbox(
            "Select Currency",
            ["USD ($)", "INR (₹)", "EUR (€)"],
            label_visibility="collapsed"
        )
        if currency == "USD ($)":
            symbol = "$"
            rate = 1
        elif currency == "INR (₹)":
            symbol = "₹"
            rate = 83
        else:
            symbol = "€"
            rate = 0.92
        summary["total_spend"] *= rate
        summary["estimated_savings"] *= rate
        df["Cost"] = df["Cost"] * rate
        # Executive Snapshot
        render_executive_snapshot(summary, symbol)

        render_cost_by_service(df, symbol)

        render_cost_forecast(df, symbol)

        render_ai_insights(df, symbol)

        render_monthly_trend(df, symbol)

        render_top_optimization_opportunities(df, symbol)

        render_optimization_recommendations(df, symbol)

        render_cost_anomaly_detection(df, symbol)
    else:
        st.error("CSV must contain 'Service' and 'Cost' columns.")

st.markdown("""
<div class="kpi-container">
    <div class="kpi-card">
        <div class="kpi-title">AVG COST OPTIMIZATION</div>
        <div class="kpi-value">18–32%</div>
    </div>
    <div class="kpi-card">
        <div class="kpi-title">EXECUTIVE READINESS</div>
        <div class="kpi-value">Board-Ready</div>
    </div>
    <div class="kpi-card">
        <div class="kpi-title">INSIGHT GENERATION</div>
        <div class="kpi-value">AI-Powered</div>
    </div>
</div>
""", unsafe_allow_html=True)

st.markdown("""
<style>
    .stApp {
        background-color: #f9fafb;
    }
    h1, h2, h3 {
        font-weight: 600;
    }
</style>
""", unsafe_allow_html=True)

st.markdown("""
<style>
.snapshot-card {
    background: white;
    padding: 25px;
    border-radius: 16px;
    box-shadow: 0 8px 20px rgba(0,0,0,0.05);
    border-left: 6px solid #2563eb;
    height: 150px;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    transition: all 0.25s ease-in-out;
}
.snapshot-card:hover {
    transform: translateY(-6px);
    box-shadow: 0 16px 35px rgba(0,0,0,0.12);
}
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div style="margin-top:15px;">
    <div style="display:inline-block; font-size:24px; font-weight:700;">
        $189,602
    </div>
    <div style="
        display:inline-block;
        background:#16a34a;
        color:white;
        padding:5px 10px;
        border-radius:15px;
        font-size:12px;
        font-weight:600;
        margin-left:10px;
    ">
        22.0%
    </div>
</div>
""", unsafe_allow_html=True)
