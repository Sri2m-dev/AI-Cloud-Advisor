from datetime import date, timedelta

import pandas as pd
import requests
from azure.identity import ClientSecretCredential
from azure.mgmt.resource import ResourceManagementClient


AZURE_MANAGEMENT_SCOPE = "https://management.azure.com/.default"
AZURE_COST_API_VERSION = "2023-03-01"


def _azure_credential(tenant_id, client_id, client_secret):
    return ClientSecretCredential(
        tenant_id=tenant_id,
        client_id=client_id,
        client_secret=client_secret,
    )


def _first_matching_column(columns, *candidates):
    normalized = {column.lower(): column for column in columns}
    for candidate in candidates:
        match = normalized.get(candidate.lower())
        if match:
            return match
    return None


def _normalize_azure_date(value):
    if value is None:
        return None
    value_str = str(value)
    if len(value_str) == 8 and value_str.isdigit():
        return pd.to_datetime(value_str, format="%Y%m%d", errors="coerce")
    return pd.to_datetime(value_str, errors="coerce")


def get_azure_cost(tenant_id, client_id, client_secret, subscription_id, days=30):
    credential = _azure_credential(tenant_id, client_id, client_secret)
    token = credential.get_token(AZURE_MANAGEMENT_SCOPE)

    end_date = date.today()
    start_date = end_date - timedelta(days=days)
    url = (
        f"https://management.azure.com/subscriptions/{subscription_id}"
        f"/providers/Microsoft.CostManagement/query?api-version={AZURE_COST_API_VERSION}"
    )
    payload = {
        "type": "ActualCost",
        "timeframe": "Custom",
        "timePeriod": {
            "from": start_date.isoformat(),
            "to": end_date.isoformat(),
        },
        "dataset": {
            "granularity": "Daily",
            "aggregation": {
                "totalCost": {
                    "name": "PreTaxCost",
                    "function": "Sum",
                }
            },
            "grouping": [
                {
                    "type": "Dimension",
                    "name": "ServiceName",
                }
            ],
        },
    }
    response = requests.post(
        url,
        headers={
            "Authorization": f"Bearer {token.token}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=60,
    )
    response.raise_for_status()

    properties = response.json().get("properties", {})
    columns = [column["name"] for column in properties.get("columns", [])]
    rows = properties.get("rows", [])
    if not rows:
        return pd.DataFrame(columns=["date", "Service", "Cost"])

    frame = pd.DataFrame(rows, columns=columns)
    date_column = _first_matching_column(frame.columns, "UsageDate", "Date")
    service_column = _first_matching_column(frame.columns, "ServiceName", "MeterCategory")
    cost_column = _first_matching_column(frame.columns, "PreTaxCost", "Cost", "CostUSD", "totalCost")
    if not date_column or not service_column or not cost_column:
        raise ValueError("Azure cost response was missing expected columns.")

    normalized = pd.DataFrame(
        {
            "date": frame[date_column].map(_normalize_azure_date).dt.date.astype("string"),
            "Service": frame[service_column].fillna("Other").astype(str),
            "Cost": pd.to_numeric(frame[cost_column], errors="coerce").fillna(0.0),
        }
    )
    normalized = normalized.dropna(subset=["date"])
    return (
        normalized.groupby(["date", "Service"], as_index=False, dropna=False)["Cost"]
        .sum()
        .sort_values(["date", "Service"], ascending=[False, True])
        .reset_index(drop=True)
    )

def get_azure_resource_groups(tenant_id, client_id, client_secret, subscription_id):
    """
    Authenticate with Azure and list resource groups.
    """
    credential = _azure_credential(tenant_id, client_id, client_secret)
    resource_client = ResourceManagementClient(credential, subscription_id)
    return [rg.name for rg in resource_client.resource_groups.list()]
