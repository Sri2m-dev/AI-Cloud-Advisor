import pandas as pd
import streamlit as st

from ai_recommender import generate_recommendations
from services.optimization_engine import find_idle_resources, ri_recommendation

st.title("Optimization Opportunities")

service_cost = pd.DataFrame({
	"product_product_name": ["EC2", "S3", "RDS"]
})

recommendations = generate_recommendations(service_cost)

for r in recommendations:
	st.success(r)

# Example resource data for idle detection
resource_data = pd.DataFrame({
    "Instance": ["i-123", "i-456", "i-789"],
    "cpu_utilization": [5, 15, 8],
    "network": [2, 10, 3]
})

idle = find_idle_resources(resource_data)

if not idle.empty:
    st.warning(f"{len(idle)} idle instances detected")
    st.dataframe(idle)

# Reserved Instance / Savings Plan Recommendation
usage_hours = 600  # Example usage
rec = ri_recommendation(usage_hours)
st.success(rec)
