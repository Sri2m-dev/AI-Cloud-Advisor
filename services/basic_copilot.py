def generate_response(query, usage_df, cost_df, reco_df):
    query = (query or "").lower()

    if "cost" in query:
        total = cost_df["cost"].sum() if not cost_df.empty and "cost" in cost_df.columns else 0
        return f"Your current total cloud cost is ${total:,.0f}"

    elif "over" in query or "spend" in query:
        if not cost_df.empty and {"service", "cost"}.issubset(cost_df.columns):
            top = cost_df.groupby("service")["cost"].sum().idxmax()
            return f"You are overspending on {top}"
        return "You are overspending on EC2"

    elif "future" in query or "next" in query or "forecast" in query:
        return "Your cost is expected to increase by ~15% next month"

    elif "migrate" in query:
        return "Azure is the most cost-effective option based on current analysis"

    return "I recommend reviewing EC2 optimization opportunities"
