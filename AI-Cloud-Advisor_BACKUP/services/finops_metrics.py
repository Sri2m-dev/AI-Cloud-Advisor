import pandas as pd

def calculate_unit_cost(service_cost_df):
    total_cost = service_cost_df["Cost"].sum()
    service_cost_df["Cost_Percentage"] = (
        service_cost_df["Cost"] / total_cost * 100
    )
    return service_cost_df

def detect_cost_anomaly(cost_df):
    avg_cost = cost_df["Cost"].mean()
    threshold = avg_cost * 1.5
    anomalies = cost_df[cost_df["Cost"] > threshold]
    return anomalies