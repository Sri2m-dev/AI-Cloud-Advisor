from datetime import date

from services.cost_normalizer import normalize_cost_data


def import_cost_data(
    df,
    provider,
    service_column,
    cost_column,
    usage_date=None,
    account_name="default"
):
    """
    Convert uploaded dataframe into unified structure.
    """

    records = normalize_cost_data(
        df=df,
        provider=provider,
        service_column=service_column,
        cost_column=cost_column,
        usage_date=usage_date,
        account_name=account_name
    )

    return records