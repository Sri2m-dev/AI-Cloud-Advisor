import pandas as pd

def generate_narrative_summary(df, service_cost, insights):
    summary = []
    # Month-over-month change
    date_candidates = ["Date", "Usage", "Billing"]
    date_column = None
    for col in df.columns:
        if any(d.lower() in col.lower() for d in date_candidates):
            date_column = col
            break
    if date_column:
        df[date_column] = pd.to_datetime(df[date_column], errors='coerce')
        monthly = df.dropna(subset=[date_column]).groupby(df[date_column].dt.to_period('M'))["Cost_Display"].sum().reset_index()
        if len(monthly) >= 2:
            last = monthly.iloc[-1]["Cost_Display"]
            prev = monthly.iloc[-2]["Cost_Display"]
            change = ((last - prev) / prev) * 100 if prev > 0 else 0
            driver = service_cost.index[0] if not service_cost.empty else "Unknown"
            summary.append(f"Cloud spend increased {change:.0f}% month-over-month driven by {driver} growth.")
    # Optimization savings
    total_savings = sum(i.get("savings", 0) for i in insights)
    if total_savings > 0:
        summary.append(f"Optimization opportunities could reduce costs by ${total_savings:,.0f} annually.")
    return "\n".join(summary)
