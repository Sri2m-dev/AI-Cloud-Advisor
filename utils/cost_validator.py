import pandas as pd


def validate_cost_data(
    df,
    service_column,
    cost_column
):
    errors = []

    if service_column not in df.columns:
        errors.append(
            f"Missing service column: {service_column}"
        )

    if cost_column not in df.columns:
        errors.append(
            f"Missing cost column: {cost_column}"
        )

    if not pd.api.types.is_numeric_dtype(
        df[cost_column]
    ):
        try:
            pd.to_numeric(
                df[cost_column]
            )
        except Exception:
            errors.append(
                f"{cost_column} must be numeric"
            )

    return errors