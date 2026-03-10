def detect_cost_anomalies(service_cost):
    insights = []
    mean_cost = service_cost["Cost_Display"].mean()
    for _, row in service_cost.iterrows():
        service = row["Service"]
        cost = row["Cost_Display"]
        if cost > mean_cost * 2:
            insights.append({
                "service": service,
                "cost": cost
            })
    return insights

def recommend_savings_plans(service_cost):
    recommendations = []
    for _, row in service_cost.iterrows():
        service = row["Service"]
        cost = row["Cost_Display"]
        if "Elastic Compute" in service or "EC2" in service:
            if cost > 50000:
                savings = cost * 0.30
                recommendations.append({
                    "title": "EC2 Savings Plan Opportunity",
                    "savings": savings
                })
    return recommendations

def generate_finops_summary(service_cost):
    total = service_cost["Cost_Display"].sum()
    top_service = service_cost.sort_values(
        "Cost_Display", ascending=False
    ).iloc[0]
    percent = top_service["Cost_Display"] / total * 100
    summary = (
        f"Total cloud spend is ${total:,.0f}. "
        f"The largest cost driver is {top_service['Service']} "
        f"representing {percent:.1f}% of total spend."
    )
    return summary
