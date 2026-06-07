import boto3

client = boto3.client("ce")

response = client.get_cost_and_usage(
    TimePeriod={
        "Start": "2026-04-01",
        "End": "2026-04-02"
    },
    Granularity="DAILY",
    Metrics=["UnblendedCost"]
)

print(response)

