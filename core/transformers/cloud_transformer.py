def normalize_cloud_costs(df):
    """
    Normalize cloud cost dataframe columns to enterprise contract.
    """
    rename_map = {
        "cost": "spend",
        "service_name": "service",
        "usage_date": "date",
        "account_name": "account"
    }
    return df.rename(columns=rename_map)

