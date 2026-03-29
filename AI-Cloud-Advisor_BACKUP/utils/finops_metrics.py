# Utility for FinOps metrics calculations

def calculate_finops_metrics(df):
    # Normalize column names
    df.columns = [c.lower().replace("/", "_") for c in df.columns]

    # Detect cost column automatically
    cost_column = None
    for col in df.columns:
        if "cost" in col:
            cost_column = col
            break
    if cost_column is None:
        raise ValueError("No cost column found in CUR file")
    total_cost = df[cost_column].astype(float).sum()
    potential_savings = total_cost * 0.18
    return total_cost, potential_savings, cost_column
