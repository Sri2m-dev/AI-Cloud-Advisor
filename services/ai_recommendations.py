from openai import OpenAI
import streamlit as st

client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

def generate_finops_recommendation(cost_df):
    recommendations = []

    try:
        for _, row in cost_df.iterrows():
            service = row.get("Service", "")
            cost = row.get("Cost", 0)

            if service == "EC2" and cost > 4000:
                recommendations.append(
                    "EC2 optimization: Consider using Graviton instances or Savings Plans."
                )

            elif service == "S3" and cost > 1500:
                recommendations.append(
                    "S3 optimization: Move infrequently accessed data to Glacier or Intelligent Tiering."
                )

            elif service == "RDS" and cost > 2500:
                recommendations.append(
                    "RDS optimization: Evaluate Reserved Instances for steady workloads."
                )

            elif service == "Lambda" and cost > 300:
                recommendations.append(
                    "Lambda optimization: Reduce memory allocation or optimize execution time."
                )

        if not recommendations:
            recommendations.append(
                "No major FinOps optimization opportunities detected."
            )

    except Exception as e:
        recommendations.append(f"Error generating FinOps recommendations: {e}")

    return recommendations
