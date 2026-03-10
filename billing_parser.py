import pandas as pd

def detect_table_start(df, keywords):
    """
    Detect row containing billing table header
    """
    for i, row in df.iterrows():
        row_text = " ".join(str(v).lower() for v in row.values)
        if any(keyword in row_text for keyword in keywords):
            return i
    return None
