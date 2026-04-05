def normalize_aws(resource):
    return {
        "provider": "AWS",
        "service_type": "compute",
        "instance_type": resource["instance"],
        "cpu": 2,
        "memory": 8,
        "region": resource.get("region", "us-east-1"),
        "cost": resource["cost"],
    }
