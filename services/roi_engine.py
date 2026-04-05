def calculate_roi(current_cost, new_cost):
    savings = current_cost - new_cost
    savings_percent = (savings / current_cost) * 100

    return {
        "savings": savings,
        "percent": savings_percent
    }


def calculate_payback(migration_cost, monthly_savings):
    if monthly_savings == 0:
        return "N/A"

    months = migration_cost / monthly_savings

    return round(months, 1)
