def get_equivalent_instances(instance_type):
    mapping = {
        "m5.large": {
            "cpu": 2,
            "memory": 8,
            "Azure": "D4s v5",
            "GCP": "e2-standard-4",
        }
    }
    return mapping.get(instance_type, {})
