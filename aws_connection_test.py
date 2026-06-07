import boto3

ce = boto3.client('ce')

response = ce.get_cost_and_usage(
    TimePeriod={
        'Start': '2026-04-01',
        'End': '2026-04-30'
    },
    Granularity='DAILY',
    Metrics=['UnblendedCost']
)

print(response)

