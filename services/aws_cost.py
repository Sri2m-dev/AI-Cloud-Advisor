# Utility for loading cost data
import boto3
import pandas as pd

def load_cost_file(uploaded_file):
    df = pd.read_csv(uploaded_file)
    # Clean column names
    df.columns = [c.lower().replace("/", "_") for c in df.columns]
    return df

def get_cost_data():
    client = boto3.client("ce")
    response = client.get_cost_and_usage(
        TimePeriod={
            "Start": "2026-03-01",
            "End": "2026-03-10"
        },
        Granularity="DAILY",
        Metrics=["UnblendedCost"]
    )
    results = response["ResultsByTime"]
    data = []
    for r in results:
        data.append({
            "date": r["TimePeriod"]["Start"],
            "cost": float(r["Total"]["UnblendedCost"]["Amount"])
        })
    return pd.DataFrame(data)