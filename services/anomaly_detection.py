from sklearn.ensemble import IsolationForest
import pandas as pd

def detect_cost_anomaly(df):
    """Detect cost anomalies using Isolation Forest."""
    model = IsolationForest(contamination=0.05, random_state=42)
    df = df.copy()
    df["anomaly"] = model.fit_predict(df[["cost"]])
    return df[df["anomaly"] == -1]
