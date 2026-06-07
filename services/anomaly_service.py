import pandas as pd

def detect_cost_anomalies(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty or "metric_date" not in df.columns:
        return pd.DataFrame()

    df = df.copy()

    # Identify cost column
    cost_col = "total_cost" if "total_cost" in df.columns else df.columns[-1]

    df = df.sort_values("metric_date")

    # Rolling average (7-day)
    df["rolling_avg"] = df[cost_col].rolling(window=7, min_periods=1).mean()

    # % deviation
    df["deviation_pct"] = (
        (df[cost_col] - df["rolling_avg"]) / df["rolling_avg"]
    ) * 100

    # Define anomaly thresholds
    df["anomaly_type"] = None

    df.loc[df["deviation_pct"] > 30, "anomaly_type"] = "SPIKE"
    df.loc[df["deviation_pct"] < -30, "anomaly_type"] = "DROP"

    # Filter only anomalies
    anomalies = df[df["anomaly_type"].notnull()]

    return anomalies

