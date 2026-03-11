# Add get_aws_cost function
def get_aws_cost():
    # Example placeholder implementation with 'date' column
    return pd.DataFrame({
        "date": ["2026-03-01", "2026-03-02"],
        "Service": ["EC2", "S3"],
        "Cost": [5000, 2000]
    })
# Utility for loading cost data
import boto3
import pandas as pd
import os

def load_cost_file(uploaded_file):
    df = pd.read_csv(uploaded_file)
    # Clean column names
    df.columns = [c.lower().replace("/", "_") for c in df.columns]
    return df

    client = boto3.client(
        "ce",
        aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
        region_name=os.getenv("AWS_DEFAULT_REGION")
    )
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
        date = r["TimePeriod"]["Start"]
        cost = float(
            r["Total"]["UnblendedCost"]["Amount"]
        )
        data.append({
            "date": date,
            "cost": cost
        })
    return pd.DataFrame(data)