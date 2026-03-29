# Utility for loading cost data
import pandas as pd

def load_cost_file(uploaded_file):
    df = pd.read_csv(uploaded_file)
    # Clean column names
    df.columns = [c.lower().replace("/", "_") for c in df.columns]
    return df
