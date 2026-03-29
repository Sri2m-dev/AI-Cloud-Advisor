import pandas as pd

def generate_finops_recommendations(service_cost_df):
    recommendations = []
    for _, row in service_cost_df.iterrows():
        service = row["Service"]
        cost = row["Cost"]
        if service == "EC2" and cost > 4000:
            recommendations.append(
                "Reduce EC2 cost by rightsizing instances or purchasing Savings Plans."
            )
        elif service == "S3" and cost > 1500:
            recommendations.append(
                "Move infrequently accessed S3 data to S3 Intelligent-Tiering or Glacier."
            )
        elif service == "RDS" and cost > 2500:
            recommendations.append(
                "Consider Reserved Instances for RDS workloads."
            )
        elif service == "Lambda" and cost > 300:
            recommendations.append(
                "Optimize Lambda memory allocation to reduce compute cost."
            )
    if len(recommendations) == 0:
        recommendations.append("No major optimization opportunities detected.")
    return recommendations
