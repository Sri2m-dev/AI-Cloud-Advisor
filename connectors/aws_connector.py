def fetch_aws_cost():
    return {
        "services": [
            {"name": "EC2", "cost": 20000},
            {"name": "S3", "cost": 8000}
        ],
        "total_spend": 28000
    }

# Replace later with boto3

