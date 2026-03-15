import json
from datetime import datetime, timedelta

import pandas as pd
import requests
from google.auth.transport.requests import Request
from google.cloud import storage
from google.oauth2 import service_account


BIGQUERY_SCOPE = "https://www.googleapis.com/auth/bigquery.readonly"
STORAGE_SCOPE = "https://www.googleapis.com/auth/devstorage.read_only"


def _service_account_info(service_account_json):
    if isinstance(service_account_json, (bytes, bytearray)):
        raw_json = service_account_json.decode("utf-8")
    else:
        raw_json = service_account_json
    return json.loads(raw_json)


def _refresh_service_account_credentials(service_account_info, scopes):
    credentials = service_account.Credentials.from_service_account_info(
        service_account_info,
        scopes=scopes,
    )
    credentials.refresh(Request())
    return credentials


def _parse_bigquery_rows(response_json):
    fields = [field["name"] for field in response_json.get("schema", {}).get("fields", [])]
    rows = []
    for row in response_json.get("rows", []):
        values = [cell.get("v") for cell in row.get("f", [])]
        rows.append(dict(zip(fields, values)))
    return rows


def get_gcp_cost(
    service_account_json,
    billing_project_id,
    billing_dataset,
    billing_table,
    billing_account_id=None,
    days=30,
):
    service_account_info = _service_account_info(service_account_json)
    credentials = _refresh_service_account_credentials(service_account_info, [BIGQUERY_SCOPE])

    start_date = (datetime.utcnow().date() - timedelta(days=days)).isoformat()
    query = f"""
    SELECT
      DATE(usage_start_time) AS usage_date,
      COALESCE(service.description, 'Other') AS service_name,
      SUM(cost) AS total_cost
    FROM `{billing_project_id}.{billing_dataset}.{billing_table}`
    WHERE DATE(usage_start_time) >= @start_date
    """
    query_parameters = [
        {
            "name": "start_date",
            "parameterType": {"type": "DATE"},
            "parameterValue": {"value": start_date},
        }
    ]
    if billing_account_id:
        query += "\n      AND billing_account_id = @billing_account_id"
        query_parameters.append(
            {
                "name": "billing_account_id",
                "parameterType": {"type": "STRING"},
                "parameterValue": {"value": billing_account_id},
            }
        )
    query += """
    GROUP BY usage_date, service_name
    ORDER BY usage_date DESC, total_cost DESC
    """

    response = requests.post(
        f"https://bigquery.googleapis.com/bigquery/v2/projects/{billing_project_id}/queries",
        headers={
            "Authorization": f"Bearer {credentials.token}",
            "Content-Type": "application/json",
        },
        json={
            "query": query,
            "useLegacySql": False,
            "parameterMode": "NAMED",
            "queryParameters": query_parameters,
            "timeoutMs": 60000,
            "maxResults": 5000,
        },
        timeout=90,
    )
    response.raise_for_status()
    rows = _parse_bigquery_rows(response.json())
    if not rows:
        return pd.DataFrame(columns=["date", "Service", "Cost"])

    frame = pd.DataFrame(rows)
    normalized = pd.DataFrame(
        {
            "date": pd.to_datetime(frame["usage_date"], errors="coerce").dt.date.astype("string"),
            "Service": frame["service_name"].fillna("Other").astype(str),
            "Cost": pd.to_numeric(frame["total_cost"], errors="coerce").fillna(0.0),
        }
    )
    normalized = normalized.dropna(subset=["date"])
    return normalized.reset_index(drop=True)

def list_gcp_buckets(service_account_json):
    """
    Authenticate with GCP using uploaded Service Account JSON and list storage buckets.
    """
    service_account_info = _service_account_info(service_account_json)
    credentials = _refresh_service_account_credentials(service_account_info, [STORAGE_SCOPE])
    client = storage.Client(project=service_account_info.get("project_id"), credentials=credentials)
    return [bucket.name for bucket in client.list_buckets()]
