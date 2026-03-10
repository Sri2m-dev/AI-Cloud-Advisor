import streamlit as st
import plotly.express as px
from utils.cost_loader import load_cost_file
from utils.finops_metrics import calculate_finops_metrics

st.title("AWS Cost Explorer")

file = st.file_uploader("Upload AWS CUR file", type="csv")

if file:

    df = load_cost_file(file)

    total, savings, cost_column = calculate_finops_metrics(df)

    st.metric("Total Spend", f"${round(total,2)}")
    st.metric("Potential Savings", f"${round(savings,2)}")

    # Check if service column exists
    if "product_product_name" in df.columns:
        service_cost = df.groupby(
            "product_product_name"
        )[cost_column].sum().reset_index()

        fig = px.bar(
            service_cost.head(10),
            x="product_product_name",
            y=cost_column,
            title="Top Services by Cost"
        )

        st.plotly_chart(fig, use_container_width=True)
    else:
        st.warning("Service breakdown not available in this CUR file.")
