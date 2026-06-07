import boto3
from datetime import date, timedelta

client = boto3.client("ce")

end = date.today() - timedelta(days=1)
start = end - timedelta(days=30)

response = client.get_cost_and_usage(
    TimePeriod={
        "Start": start.strftime("%Y-%m-%d"),
        "End": end.strftime("%Y-%m-%d")
    },
    Granularity="MONTHLY",
    Metrics=["AmortizedCost"]
)

print(response)

