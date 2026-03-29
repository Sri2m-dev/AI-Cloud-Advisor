import pandas as pd

def generate_recommendations(df):
    recommendations = []

    if df.empty:
        return recommendations

    # Ensure numeric
    df["total_cost"] = pd.to_numeric(df["total_cost"], errors="coerce")
    df = df.dropna(subset=["total_cost"])

    avg_cost = df["total_cost"].mean()
    latest_cost = df["total_cost"].iloc[-1]

    # 🔴 1. Cost Spike Detection
    if latest_cost > avg_cost * 1.2:
        recommendations.append({
            "title": "Investigate cost spike",
            "category": "anomaly",
            "priority": "High",
            "savings": round(latest_cost - avg_cost, 2),
            "confidence": 0.9,
            "description": "Recent spend is significantly higher than average.",
            "actions": [
                "Check top services contributing to spike",
                "Compare last 7 days vs previous baseline",
                "Validate expected vs unexpected usage"
            ]
        })

    # 🟡 2. Idle Resource Detection (example)
    if df["total_cost"].mean() < 50:
        recommendations.append({
            "title": "Review underutilized resources",
            "category": "optimization",
            "priority": "Medium",
            "savings": 200,
            "confidence": 0.75,
            "description": "Low usage detected — possible idle resources.",
            "actions": [
                "Check EC2 CPU utilization",
                "Identify unused storage volumes",
                "Stop idle workloads"
            ]
        })

    # 🔵 3. Forecast Risk (basic)
    if len(df) > 7:
        trend = df["total_cost"].pct_change().mean()
        if trend > 0.05:
            recommendations.append({
                "title": "Rising cost trend detected",
                "category": "forecast",
                "priority": "High",
                "savings": 500,
                "confidence": 0.85,
                "description": "Costs are steadily increasing.",
                "actions": [
                    "Enable budgets and alerts",
                    "Evaluate Savings Plans",
                    "Review scaling policies"
                ]
            })

    return recommendations
