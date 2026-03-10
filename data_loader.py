import pandas as pd

def load_data(uploaded_file):
    df = pd.read_csv(uploaded_file)

    # Remove empty columns
    df = df.dropna(axis=1, how="all")

    # Remove Unnamed columns
    df = df.loc[:, ~df.columns.str.contains("^Unnamed")]

    # Standardize columns
    df.columns = df.columns.str.strip()

    if "Service" not in df.columns or "Cost" not in df.columns:
        raise ValueError("CSV must contain 'Service' and 'Cost' columns.")

    df["Cost"] = pd.to_numeric(df["Cost"], errors="coerce").fillna(0)

    return df
