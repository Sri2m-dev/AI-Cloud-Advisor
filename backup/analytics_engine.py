def compute_summary(df):
    total_spend = df["Cost"].sum()

    top_service = (
        df.groupby("Service")["Cost"]
        .sum()
        .sort_values(ascending=False)
        .reset_index()
        .iloc[0]
    )

    savings_estimate = total_spend * 0.22  # Conservative 22%

    return {
        "total_spend": total_spend,
        "top_service": top_service["Service"],
        "top_cost": top_service["Cost"],
        "estimated_savings": savings_estimate
    }
