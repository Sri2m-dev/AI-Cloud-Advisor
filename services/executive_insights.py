def generate_executive_insights(
    spend_df,
    recommendations_df,
    governance_score,
):
    """Generate safe executive insight bullets for dashboards/reports."""

    insights = []

    try:
        if spend_df is not None and not spend_df.empty and "cost" in spend_df.columns:
            total_spend = float(spend_df["cost"].fillna(0).sum())
            insights.append(f"Total tracked technology spend is {total_spend:,.2f}.")
        else:
            insights.append("Spend data is not available for the selected period.")

        if recommendations_df is not None and not recommendations_df.empty:
            insights.append(
                f"There are {len(recommendations_df)} active optimization recommendations."
            )
        else:
            insights.append("No active optimization recommendations are available.")

        if governance_score is not None:
            insights.append(f"Current governance score is {governance_score}.")
        else:
            insights.append("Governance score is not available.")

    except Exception:
        return [
            "Executive insights are currently unavailable.",
            "Please validate source data and try again.",
        ]

    return insights