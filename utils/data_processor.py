from core.currency import convert_currency

def process_cost_data(df, currency):
    df = df.copy()
    if "total_cost" not in df.columns:
        raise Exception("Missing total_cost column")
    df["cost"] = df["total_cost"].apply(lambda x: convert_currency(x, currency))
    return df

