# Utility for FinOps metrics calculations
from typing import Tuple

import pandas as pd


def calculate_finops_metrics(df: pd.DataFrame) -> Tuple[float, float, pd.DataFrame]:
    total_cost = df["line_item_unblended_cost"].sum()
    service_cost = df.groupby(
        "product_product_name"
    )["line_item_unblended_cost"].sum().reset_index()
    service_cost = service_cost.sort_values(
        "line_item_unblended_cost",
        ascending=False
    )
    potential_savings = total_cost * 0.18
    return total_cost, potential_savings, service_cost
