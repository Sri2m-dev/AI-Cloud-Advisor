# 1_Dashboard.py
import streamlit as st
import pandas as pd
import plotly.express as px

st.title("☁ Cloud Advisory Dashboard")

col1, col2, col3, col4 = st.columns(4)

col1.metric("Monthly Spend", "$45,200", delta="-$2,100 vs last month")
col2.metric("Savings Potential", "$8,400", delta="18% of total spend")
col3.metric("Idle Resources", "12", delta="-3 vs last month")
col4.metric("Optimization Score", "82%", delta="+5% vs last month")

st.divider()

service_data = pd.DataFrame({
    "Service": ["EC2", "S3", "RDS", "Lambda"],
    "Cost": [20000, 9000, 8000, 5000]
})

col_pie, col_bar = st.columns(2)

with col_pie:
    st.subheader("Cost by Service")
    fig_pie = px.pie(service_data, values="Cost", names="Service",
                     color_discrete_sequence=px.colors.sequential.Blues_r)
    st.plotly_chart(fig_pie, use_container_width=True)

with col_bar:
    st.subheader("Monthly Spend Trend")
    trend_data = pd.DataFrame({
        "Month": ["Oct", "Nov", "Dec", "Jan", "Feb", "Mar"],
        "Spend": [41000, 43500, 47200, 46800, 47300, 45200]
    })
    fig_trend = px.line(trend_data, x="Month", y="Spend", markers=True,
                        labels={"Spend": "Cost ($)"},
                        color_discrete_sequence=["#1f77b4"])
    st.plotly_chart(fig_trend, use_container_width=True)

st.divider()

st.subheader("Top Optimization Opportunities")
opportunities = pd.DataFrame({
    "Resource": ["EC2 Instances", "RDS Instances", "EBS Volumes", "S3 Storage"],
    "Potential Savings ($)": [4200, 2100, 800, 1200],
    "Effort": ["Low", "Medium", "Low", "Low"],
    "Priority": ["High", "High", "Medium", "Medium"]
})
st.dataframe(opportunities, use_container_width=True)
