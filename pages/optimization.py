import pandas as pd
import streamlit as st

from ai_recommender import generate_recommendations

st.title("Optimization Opportunities")

service_cost = pd.DataFrame({
	"product_product_name": ["EC2", "S3", "RDS"]
})

recommendations = generate_recommendations(service_cost)

for r in recommendations:
	st.success(r)
