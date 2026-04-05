def estimate_migration_cost(instance_type):
    # Sample logic (you can refine later)
    base_cost = {
        "m5.large": {
            "compute": 500,
            "data_transfer": 800,
            "engineering": 700,
            "downtime_buffer": 200,
        }
    }

    cost = base_cost.get(instance_type, {})
    total = sum(cost.values())

    return {
        "breakdown": cost,
        "total": total,
    }


def calculate_payback(migration_cost, monthly_savings):
    if monthly_savings == 0:
        return "N/A"

    months = migration_cost / monthly_savings

    return round(months, 1)
