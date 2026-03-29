import streamlit as st
import pandas as pd

def dashboard_page():
    st.title("Dashboard")
    df = pd.DataFrame({"cost": [100, 200, 300, 400], "service": ["ec2", "s3", "rds", "ec2"], "date": pd.date_range("2024-01-01", periods=4)})
    st.subheader("🤖 AI Recommendations")
    recs = []
    if df["cost"].max() > df["cost"].mean() * 2:
        recs.append("Investigate sudden cost spikes")
    if "ec2" in df["service"].str.lower().values:
        recs.append("Consider Reserved Instances for EC2")
    if "s3" in df["service"].str.lower().values:
        recs.append("Enable lifecycle policies for S3")
    if not recs:
        recs.append("No major optimization needed")
    for r in recs:
        st.info(f"💡 {r}")
    total = df["cost"].sum()
    idle_savings = total * 0.10
    optimization_savings = total * 0.15
    savings_opportunity = idle_savings + optimization_savings
    st.metric("💡 Savings Opportunity", f"${savings_opportunity:,.2f}", help="Estimated savings if idle and overprovisioned resources are optimized.")
    st.subheader("📈 Forecast")
    df_daily = df.groupby("date")["cost"].sum().reset_index()
    df_daily = df_daily.sort_values("date")
    df_daily["rolling_avg"] = df_daily["cost"].rolling(7).mean()
    last_value = df_daily["rolling_avg"].iloc[-1]
    forecast = [last_value] * 3
    for i, val in enumerate(forecast, 1):
        st.info(f"Month +{i}: ${val:,.0f}")
