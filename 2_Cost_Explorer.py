import streamlit as st
import plotly.express as px
from utils.cost_loader import load_cost_file
from utils.finops_metrics import calculate_finops_metrics
from utils.ai_recommender import generate_recommendations

st.title("AWS Cost Explorer")

file = st.file_uploader("Upload AWS CUR file", type="csv")

if file:
    df = load_cost_file(file)

    total, savings, service_cost = calculate_finops_metrics(df)

    col1, col2 = st.columns(2)
    col1.metric("Total Spend", f"${total:,.2f}")
    col2.metric("Potential Savings (18%)", f"${savings:,.2f}")

    st.divider()

    st.subheader("Top Services by Cost")
    fig = px.bar(
        service_cost.head(10),
        x="product_product_name",
        y="line_item_unblended_cost",
        labels={
            "product_product_name": "Service",
            "line_item_unblended_cost": "Cost ($)"
        },
        color="line_item_unblended_cost",
        color_continuous_scale="Blues"
    )
    st.plotly_chart(fig, use_container_width=True)

    st.divider()

    st.subheader("AI-Powered Recommendations")
    recommendations = generate_recommendations(service_cost)
    for rec in recommendations:
        st.success(f"✅ {rec}")

else:
    st.info("📂 Upload an AWS Cost and Usage Report (CUR) CSV file to get started.")
