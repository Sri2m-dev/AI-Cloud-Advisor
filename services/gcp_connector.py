import pandas as pd

def get_gcp_cost():
    # Placeholder: Replace with real GCP Billing Export integration
    return pd.DataFrame({
        "date": ["2026-03-01", "2026-03-02"],
        "Service": ["Compute Engine", "BigQuery"],
        "Cost": [2200, 800]
    })
from google.oauth2 import service_account
from google.cloud import storage
import json
import tempfile

def list_gcp_buckets(service_account_json):
    """
    Authenticate with GCP using uploaded Service Account JSON and list storage buckets.
    """
    # Write uploaded JSON to a temporary file
    with tempfile.NamedTemporaryFile(delete=False, suffix='.json') as temp:
        temp.write(service_account_json)
        temp.flush()
        credentials = service_account.Credentials.from_service_account_file(temp.name)
        client = storage.Client(credentials=credentials)
        buckets = [bucket.name for bucket in client.list_buckets()]
    return buckets
