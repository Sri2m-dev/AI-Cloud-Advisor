# Utility for FinOps metrics calculations

def calculate_finops_metrics(df):
    total_cost = df["line_item_unblended_cost"].sum()
    service_cost = df.groupby(
        "product_product_name"
    )["line_item_unblended_cost"].sum().reset_index()
    service_cost = service_cost.sort_values(
        "line_item_unblended_cost",
        ascending=False
    )
    potential_savings = total_cost * 0.18  # 18% average cloud cost savings based on industry benchmarks
    return total_cost, potential_savings, service_cost
