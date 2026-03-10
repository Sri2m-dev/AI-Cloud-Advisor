import pandas as pd

from finops_metrics import calculate_finops_metrics


def test_calculate_finops_metrics_returns_expected_values() -> None:
    df = pd.DataFrame(
        {
            "line_item_unblended_cost": [10.0, 5.0, 20.0],
            "product_product_name": ["S3", "S3", "EC2"],
        }
    )

    total, potential_savings, service_cost = calculate_finops_metrics(df)

    assert total == 35.0
    assert potential_savings == 6.3
    assert list(service_cost["product_product_name"]) == ["EC2", "S3"]
    assert list(service_cost["line_item_unblended_cost"]) == [20.0, 15.0]
