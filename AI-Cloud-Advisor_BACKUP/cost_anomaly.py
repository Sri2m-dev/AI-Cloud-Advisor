import pandas as pd

def detect_cost_anomalies(df, service_column, date_column):
    insights = []
    if df.empty or not service_column or not date_column:
        return insights
    # Ensure date column is datetime
    df[date_column] = pd.to_datetime(df[date_column], errors='coerce')
    df = df.dropna(subset=[date_column])
    # Group by week and service
    df['week'] = df[date_column].dt.to_period('W').astype(str)
    weekly = df.groupby(['week', service_column])["Cost_Display"].sum().reset_index()
    # Pivot for easier comparison
    pivot = weekly.pivot(index='week', columns=service_column, values='Cost_Display').fillna(0)
    # Compare last two weeks for each service
    if len(pivot) < 2:
        return insights
    last_week, prev_week = pivot.iloc[-1], pivot.iloc[-2]
    for service in pivot.columns:
        prev = prev_week[service]
        curr = last_week[service]
        if prev > 0 and curr > prev * 2:  # Spike > 100%
            percent = ((curr - prev) / prev) * 100
            insights.append(f"⚠ {service} spend increased {percent:.0f}% this week")
    return insights
