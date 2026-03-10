from sklearn.ensemble import IsolationForest

def detect_anomalies(df):
    model = IsolationForest(contamination=0.05)
    df = df.copy()
    df["anomaly"] = model.fit_predict(df[["Cost_Display"]])
    anomalies = df[df["anomaly"] == -1]
    return anomalies
