# Utility for loading cost data
from typing import IO

import pandas as pd


def load_cost_file(uploaded_file: IO[str]) -> pd.DataFrame:
    df = pd.read_csv(uploaded_file)
    if "line_item_unblended_cost" in df.columns:
        df["line_item_unblended_cost"] = df["line_item_unblended_cost"].astype(float)
    return df
