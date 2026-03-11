import streamlit as st
import pandas as pd
from services.ai_finops_advisor import generate_finops_recommendations

st.title("🤖 AI Cloud FinOps Advisor")

st.write("AI-driven cloud cost optimization recommendations")

service_cost = pd.DataFrame({
    "Service": ["EC2", "S3", "RDS", "Lambda"],
    "Cost": [5000, 2000, 3000, 450]
})

recommendations = generate_finops_recommendations(service_cost)

st.subheader("Recommended Optimizations")

for rec in recommendations:
    st.success(rec)
