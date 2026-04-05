import boto3
from datetime import datetime, timedelta


def get_aws_cost():
    client = boto3.client("ce")  # Cost Explorer

    today = datetime.today()
    start = (today - timedelta(days=30)).strftime('%Y-%m-%d')
    end = today.strftime('%Y-%m-%d')

    response = client.get_cost_and_usage(
        TimePeriod={
            'Start': start,
            'End': end
        },
        Granularity='MONTHLY',
        Metrics=['UnblendedCost'],
        GroupBy=[
            {'Type': 'DIMENSION', 'Key': 'SERVICE'}
        ]
    )

    results = []

    for group in response['ResultsByTime'][0]['Groups']:
        service = group['Keys'][0]
        cost = float(group['Metrics']['UnblendedCost']['Amount'])

        results.append({
            "provider": "AWS",
            "service": service,
            "cost": cost
        })

    return results
