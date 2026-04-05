from services.mapping_engine import get_equivalent_instances
from services.pricing_engine import get_pricing


def compare_instance(instance_type):
    mapping = get_equivalent_instances(instance_type)
    pricing = get_pricing()

    results = []

    aws_cost = pricing["AWS"][instance_type]

    for provider in ["Azure", "GCP"]:
        mapped = mapping[provider]
        cost = pricing[provider][mapped]

        savings = aws_cost - cost
        perf_gain = 10 if provider == "Azure" else 8

        results.append({
            "provider": provider,
            "instance": mapped,
            "cost": cost,
            "savings": savings,
            "performance_gain": perf_gain
        })

    return results
