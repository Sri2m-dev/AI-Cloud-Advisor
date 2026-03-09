# 3_Optimization.py
import streamlit as st
import pandas as pd
from utils.ai_recommender import generate_recommendations

st.title("Optimization Opportunities")

st.write("AI-driven cost savings and recommendations")

df = pd.DataFrame({
    "Resource": ["EC2 Instances", "RDS Instances", "EBS Volumes", "S3 Storage"],
    "Potential Savings ($)": [4200, 2100, 800, 1200],
    "Effort": ["Low", "Medium", "Low", "Low"],
    "Priority": ["High", "High", "Medium", "Medium"]
})

st.subheader("Top Optimization Opportunities")
st.dataframe(df, use_container_width=True)

st.divider()

st.subheader("AI Recommendations")
service_cost = pd.DataFrame({
    "product_product_name": ["EC2", "S3", "RDS"]
})
recommendations = generate_recommendations(service_cost)
for rec in recommendations:
    st.success(f"✅ {rec}")
