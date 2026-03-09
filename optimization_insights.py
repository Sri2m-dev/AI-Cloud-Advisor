# 2_Optimization.py
import streamlit as st
import pandas as pd

st.title("Optimization Opportunities")

st.write("AI-driven cost savings and recommendations")

# Example dataset
df = pd.DataFrame({
    "Resource": ["EC2 Instances", "RDS Instances", "EBS Volumes", "S3 Storage"],
    "Potential Savings ($)": [4200, 2100, 800, 1200]
})

st.subheader("Top Optimization Opportunities")

st.dataframe(df)

st.success("Recommendation: Implement EC2 Savings Plans")
st.warning("Recommendation: Rightsize RDS instances")
st.info("Recommendation: Remove unattached EBS volumes")
