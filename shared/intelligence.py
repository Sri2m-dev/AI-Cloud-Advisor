def generate_recommendations(usage_df):
    recommendations = []

    for _, row in usage_df.iterrows():
        util = row.get("utilization", 0)
        resource = row.get("resource", "Unknown")

        if util < 30:
            recommendations.append({
                "resource": resource,
                "recommendation": "Underutilized - डाउनsize recommended",
                "impact": "High Savings"
            })

        elif util > 85:
            recommendations.append({
                "resource": resource,
                "recommendation": "Overutilized - Scale up required",
                "impact": "Performance Risk"
            })

        elif util == 0:
            recommendations.append({
                "resource": resource,
                "recommendation": "Idle resource - Terminate",
                "impact": "Critical Waste"
            })

    return recommendations


def generate_alerts(usage_df):
    alerts = []

    for _, row in usage_df.iterrows():
        util = row.get("utilization", 0)
        resource = row.get("resource", "")

        if util > 90:
            alerts.append(f"🔥 High utilization on {resource}")

        elif util < 20:
            alerts.append(f"⚠️ Low utilization on {resource}")

    return alerts


def generate_insights(usage_df, reco_df):
    insights = []

    if not usage_df.empty:
        avg_util = usage_df["utilization"].mean()

        if avg_util < 40:
            insights.append("Overall infrastructure is underutilized. Opportunity to reduce cost.")

        elif avg_util > 75:
            insights.append("Infrastructure is highly utilized. Risk of performance bottlenecks.")

    if not reco_df.empty:
        total_savings = reco_df["savings"].sum()
        insights.append(f"Potential monthly savings identified: ${total_savings}")

    return insights


def detect_anomalies(cost_df):
    alerts = []

    if cost_df.empty or "cost" not in cost_df.columns or "service" not in cost_df.columns:
        return alerts

    avg_cost = cost_df["cost"].mean()

    for _, row in cost_df.iterrows():
        if row["cost"] > avg_cost * 1.5:
            alerts.append(f"🚨 Spike detected in {row['service']}")

    return alerts


def forecast_cost(cost_df):
    if cost_df.empty or "cost" not in cost_df.columns:
        return 0

    total = cost_df["cost"].sum()
    forecast = total * 1.1  # 10% growth

    return forecast
