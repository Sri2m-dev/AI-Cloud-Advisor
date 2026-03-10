# 1_Dashboard.py
import pandas as pd
import plotly.express as px
import streamlit as st

st.title("☁ Cloud Advisory Dashboard")

col1, col2, col3, col4 = st.columns(4)

col1.metric("Monthly Spend", "$45,200")
col2.metric("Savings Potential", "$8,400")
col3.metric("Idle Resources", "12")
col4.metric("Optimization Score", "82%")

st.divider()

data = pd.DataFrame({
    "Service": ["EC2", "S3", "RDS", "Lambda"],
    "Cost": [20000, 9000, 8000, 5000]
})

fig = px.pie(data, values="Cost", names="Service")

st.plotly_chart(fig, use_container_width=True)