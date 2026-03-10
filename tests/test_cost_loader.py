import io

import pandas as pd

from cost_loader import load_cost_file


def test_load_cost_file_casts_unblended_cost_to_float() -> None:
    csv_data = io.StringIO("line_item_unblended_cost,product_product_name\n12.5,EC2\n7,S3")

    df = load_cost_file(csv_data)

    assert pd.api.types.is_float_dtype(df["line_item_unblended_cost"])
    assert df["line_item_unblended_cost"].sum() == 19.5


def test_load_cost_file_keeps_other_columns() -> None:
    csv_data = io.StringIO("usage_type,qty\nBoxUsage,2")

    df = load_cost_file(csv_data)

    assert list(df.columns) == ["usage_type", "qty"]
