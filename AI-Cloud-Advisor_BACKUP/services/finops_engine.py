import pandas as pd

def service_cost_breakdown(df):
    """Return total cost by service."""
    return df.groupby("service")["cost"].sum()

def unit_cost(df):
    """Return unit cost (cost per usage)."""
    return df["cost"].sum() / df["usage"].sum()

def idle_resource_detection(df):
    """Return resources with utilization < 20%."""
    return df[df["utilization"] < 20]

def cost_by_environment(df):
    """Return total cost by environment (e.g., Dev vs Prod)."""
    return df.groupby("environment")["cost"].sum()

def reservation_coverage(df):
    """Estimate reservation coverage (placeholder logic)."""
    if "reserved" in df.columns:
        return df["reserved"].mean()
    return None
