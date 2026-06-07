from shared.db import supabase
import pandas as pd


# -----------------------
# LOAD COST DATA (CLIENT SAFE)
# -----------------------
def load_cost_data(client_id):
    response = supabase.table("cost_data") \
        .select("*") \
        .eq("client_id", client_id) \
        .order("date", desc=False) \
        .execute()

    data = response.data

    if not data:
        return pd.DataFrame()

    df = pd.DataFrame(data)

    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"])

    return df

