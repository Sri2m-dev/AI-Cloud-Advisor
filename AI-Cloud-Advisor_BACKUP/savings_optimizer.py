def ec2_savings_optimizer(service_cost):
    opportunities = []
    for _, row in service_cost.iterrows():
        service = row["Service"]
        cost = row["Cost_Display"]
        if "EC2" in service or "Elastic Compute" in service:
            if cost > 50000:
                savings = cost * 0.30
                opportunities.append({
                    "title": "EC2 Savings Plan Opportunity",
                    "savings": savings
                })
    return opportunities
