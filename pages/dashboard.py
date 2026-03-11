# 1_Dashboard.py
import streamlit as st
import pandas as pd
import plotly.express as px
from services.finops_metrics import calculate_unit_cost, detect_cost_anomaly

st.title("📊 Cloud Cost Dashboard")

# KPI Row
col1, col2, col3, col4 = st.columns(4)

col1.metric("Monthly Cost", "$12,450", "5% ↑")
col2.metric("Forecast", "$13,100", "2% ↑")
col3.metric("Savings Opportunity", "$3,200", "-")
col4.metric("Idle Resources", "17", "-")

st.divider()

# Cost Trend
st.subheader("Cost Trend")

data = pd.DataFrame({
    "Month": ["Jan","Feb","Mar","Apr","May"],
    "Cost": [8000,9000,11000,12000,12450]
})

fig = px.line(data, x="Month", y="Cost", markers=True)

st.plotly_chart(fig, use_container_width=True)

# Service Breakdown
st.subheader("Service Cost Breakdown")

service_cost = pd.DataFrame({
    "Service": ["EC2","S3","RDS","Lambda"],
    "Cost": [5000,2000,3000,450]
})

df = calculate_unit_cost(service_cost)
st.dataframe(df)

fig2 = px.pie(service_cost, names="Service", values="Cost")
st.plotly_chart(fig2, use_container_width=True)

# Cost Anomaly Detection
st.subheader("Cost Anomaly Detection")
anomalies = detect_cost_anomaly(service_cost)

if not anomalies.empty:
    st.error("⚠ Cost anomaly detected!")
    st.dataframe(anomalies)
else:
    st.success("No anomalies detected")