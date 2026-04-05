import pandas as pd


def forecast_cost(cost_df):
    # assume monthly data
    costs = cost_df["cost"].tolist()

    if len(costs) < 2:
        return None

    # simple growth rate
    growth = (costs[-1] - costs[-2]) / costs[-2]

    forecast_1 = costs[-1] * (1 + growth)
    forecast_3 = forecast_1 * (1 + growth)

    return {
        "next_month": round(forecast_1, 2),
        "three_month": round(forecast_3, 2),
        "growth_rate": round(growth * 100, 2)
    }
