# 1_Dashboard.py
import streamlit as st
import pandas as pd
import plotly.express as px
from services.finops_metrics import calculate_unit_cost, detect_cost_anomaly
from services.ai_recommendations import generate_finops_recommendation
from services.aws_cost import get_aws_cost

import streamlit as st

# Protect page
if not st.session_state.get("authenticated"):
    st.warning("Please login from the main page")
    st.stop()

st.title("📊 Cloud Cost Dashboard")

# KPI Row
col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric("Monthly Cost", "$12,450", "5%")
with col2:
    st.metric("Forecast", "$13,100", "2%")
with col3:
    st.metric("Savings Opportunity", "$3,200")
with col4:
    st.metric("Idle Resources", "17")

st.divider()

# Cost Trend
st.subheader("Cost Trend")

data = pd.DataFrame({
    "Month": ["Jan","Feb","Mar","Apr","May"],
    "Cost": [8000,9000,11000,12000,12450]
})

fig = px.line(data, x="Month", y="Cost", markers=True)

st.plotly_chart(fig, use_container_width=True)

# AWS Cost Trend
df = get_aws_cost()
st.subheader("AWS Cost Trend")
st.line_chart(df.set_index("date"))

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

# AI FinOps Recommendation
if st.button("Generate AI Optimization Insights"):
    df_summary = df.groupby("Service")["Cost"].sum().to_dict()
    recommendation = generate_finops_recommendation(
        cost_summary=df_summary,
        region="us-east-1"
    )
    st.subheader("AI FinOps Recommendations")
    st.write(recommendation)

# Cost Anomaly Detection
st.subheader("Cost Anomaly Detection")
anomalies = detect_cost_anomaly(service_cost)

if not anomalies.empty:
    st.error("⚠ Cost anomaly detected!")
    st.dataframe(anomalies)
else:
    st.success("No anomalies detected")