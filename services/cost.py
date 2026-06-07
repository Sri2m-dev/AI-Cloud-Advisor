import boto3
from datetime import date

def get_cost_data():
    client = boto3.client("ce")
    response = client.get_cost_and_usage(
        TimePeriod={
            "Start": "2024-03-01",
            "End": "2024-03-31"
        },
        Granularity="MONTHLY",
        Metrics=["UnblendedCost"],
        GroupBy=[{"Type": "DIMENSION", "Key": "SERVICE"}]
    )
    return response

