def generate_finops_insights(service_cost):
    insights = []
    total_spend = service_cost["Cost_Display"].sum()
    for _, row in service_cost.iterrows():
        service = row["Service"]
        cost = row["Cost_Display"]
        percent = (cost / total_spend) * 100
        # EC2 Savings Plan opportunity
        if "Elastic Compute" in service and percent > 20:
            savings = cost * 0.30
            insights.append({
                "title": "⚡ EC2 Savings Plan Opportunity",
                "description": f"{service} accounts for {percent:.1f}% of spend.",
                "savings": savings
            })
        # RDS Reserved Instance opportunity
        if "Relational Database" in service and percent > 15:
            savings = cost * 0.35
            insights.append({
                "title": "🗄 RDS Reserved Instance Opportunity",
                "description": f"{service} represents {percent:.1f}% of cost.",
                "savings": savings
            })
        # S3 lifecycle policy
        if "Simple Storage" in service and percent > 5:
            savings = cost * 0.25
            insights.append({
                "title": "📦 S3 Lifecycle Optimization",
                "description": "Consider moving older objects to Glacier.",
                "savings": savings
            })
    return insights
