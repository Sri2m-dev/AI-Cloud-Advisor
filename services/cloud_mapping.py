def map_instance(service):
    mapping = {
        "m5.large": {
            "AWS": {"cost": 1200, "perf": 100},
            "Azure": {"instance": "D4s v5", "cost": 950, "perf": 110},
            "GCP": {"instance": "e2-standard-4", "cost": 900, "perf": 108},
        }
    }

    return mapping.get(service, {})


def compare_clouds(service):
    if isinstance(service, dict):
        resource = service
        instance_name = resource.get("instance", "")
        service_name = resource.get("service", instance_name or "Unknown")
        utilization = resource.get("utilization")
    else:
        instance_name = service
        service_name = service
        utilization = None

    data = map_instance(instance_name)

    if not data:
        return None

    aws_cost = data["AWS"]["cost"]
    insights = []

    for provider in ["Azure", "GCP"]:
        diff = aws_cost - data[provider]["cost"]
        insights.append(
            {
                "provider": provider,
                "service": service_name,
                "source_instance": instance_name,
                "instance": data[provider].get("instance", "N/A"),
                "utilization": utilization,
                "savings": diff,
                "performance": data[provider]["perf"],
            }
        )

    return insights
