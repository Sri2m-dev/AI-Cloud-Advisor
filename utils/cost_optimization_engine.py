import pandas as pd

def optimize_costs(cost_df: pd.DataFrame, app_mapping_df: pd.DataFrame) -> pd.DataFrame:
    """
    Cost Optimization Engine
    - Normalizes keys
    - Merges cost and application mapping
    - Adds recommendations
    """
    # Normalize keys before merge (CRITICAL)
    cost_df = cost_df.copy()
    app_mapping_df = app_mapping_df.copy()
    cost_df["service_name"] = cost_df["service_name"].astype(str).str.lower().str.strip()
    app_mapping_df["service_name"] = app_mapping_df["service_name"].astype(str).str.lower().str.strip()

    # Merge
    merged = cost_df.merge(app_mapping_df, on="service_name", how="left")

    # Add recommendation logic (simple example)
    def recommend(row):
        if pd.isna(row.get("cost")):
            return "Data Missing"
        if row["cost"] > 5000:
            return "Consider rightsizing"
        return "OK"
    merged["recommendation"] = merged.apply(recommend, axis=1)
    return merged

