import plotly.express as px
import streamlit as st

from cost_loader import load_cost_file
from finops_metrics import calculate_finops_metrics

st.title("AWS Cost Explorer")

file = st.file_uploader("Upload AWS CUR file", type="csv")

if file:

	df = load_cost_file(file)

	total, savings, service_cost = calculate_finops_metrics(df)

	st.metric("Total Spend", f"${round(total,2)}")

	st.metric("Potential Savings", f"${round(savings,2)}")

	fig = px.bar(service_cost.head(10),
				 x="product_product_name",
				 y="line_item_unblended_cost")

	st.plotly_chart(fig)
