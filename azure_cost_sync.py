import json
import os
from datetime import datetime, timedelta, timezone

from azure.identity import ClientSecretCredential
from azure.mgmt.costmanagement import CostManagementClient

from config import DEFAULT_ORG_ID
from supabase import create_client

# -----------------------------
# AZURE CONFIG
# -----------------------------
TENANT_ID = os.getenv("AZURE_TENANT_ID", "").strip()
CLIENT_ID = os.getenv("AZURE_CLIENT_ID", "").strip()
CLIENT_SECRET = os.getenv("AZURE_CLIENT_SECRET", "").strip()
SUBSCRIPTION_ID = os.getenv("AZURE_SUBSCRIPTION_ID", "").strip()

# -----------------------------
# SUPABASE CONFIG
# -----------------------------
SUPABASE_URL = os.getenv("SUPABASE_URL", "").strip()
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()

if not all((TENANT_ID, CLIENT_ID, CLIENT_SECRET, SUBSCRIPTION_ID)):
    raise RuntimeError(
        "AZURE_TENANT_ID, AZURE_CLIENT_ID, AZURE_CLIENT_SECRET and "
        "AZURE_SUBSCRIPTION_ID are required"
    )
if not SUPABASE_URL or not SUPABASE_KEY:
    raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are required")
if SUPABASE_KEY.startswith("sb_publishable_"):
    raise RuntimeError("SUPABASE_SERVICE_ROLE_KEY must be a backend credential")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# -----------------------------
# AUTH
# -----------------------------
credential = ClientSecretCredential(
    tenant_id=TENANT_ID,
    client_id=CLIENT_ID,
    client_secret=CLIENT_SECRET,
)

# -----------------------------
# DATE RANGE
# -----------------------------
end_date = datetime.now(timezone.utc)
start_date = end_date - timedelta(days=30)

# -----------------------------
# COST MANAGEMENT CLIENT
# -----------------------------
cost_client = CostManagementClient(credential)

scope = f"/subscriptions/{SUBSCRIPTION_ID}"

query_result = cost_client.query.usage(
    scope=scope,
    parameters={
        "type": "ActualCost",
        "timeframe": "MonthToDate",
        "dataset": {
            "granularity": "None",
            "aggregation": {
                "totalCost": {
                    "name": "PreTaxCost",
                    "function": "Sum"
                }
            },
            "grouping": [
                {
                    "type": "Dimension",
                    "name": "ServiceName"
                }
            ]
        }
    }
)

result_dict = query_result.as_dict()
print(json.dumps(result_dict, indent=2))

rows = result_dict.get("rows") or result_dict.get("properties", {}).get("rows", [])
columns = [
    col["name"]
    for col in (result_dict.get("columns") or result_dict.get("properties", {}).get("columns", []))
]

print("Azure rows fetched:", len(rows))

if not rows:
    print("No Azure cost data found.")
    exit()

# -----------------------------
# COLUMN INDEXES
# -----------------------------
service_idx = columns.index("ServiceName")
cost_idx = columns.index("PreTaxCost")

# -----------------------------
# PREPARE UPSERT RECORDS
# -----------------------------
records = []

for row in rows:
    service_name = row[service_idx]
    cost = float(row[cost_idx])

    record = {
        "organization_id": DEFAULT_ORG_ID,
        "cloud": "azure",
        "account_name": "azure-main",
        "service_name": service_name,
        "region": "global",
        "resource_id": None,
        "usage_date": datetime.now(timezone.utc).date().isoformat(),
        "usage_quantity": 0,
        "cost": cost,
        "currency": "USD",
        "environment": None,
        "application": None,
        "tags": None
    }

    records.append(record)

valid_records = []
invalid_count = 0
for record in records:
    # TODO: validation is not defined. Commenting out for now.
    # if validation["valid"]:
    valid_records.append(record)
    # else:
    #     invalid_count += 1

if not valid_records:
    raise RuntimeError("No valid Azure rows after schema validation; aborting upsert")

print("Prepared Azure records:")
print(records[:3])

# -----------------------------
# UPSERT INTO SUPABASE
# -----------------------------
response = (
    supabase
    .table("unified_cloud_costs")
    .upsert(
        valid_records,
        on_conflict="cloud,service_name"
    )
    .execute()
)

print("Azure upsert complete")
print(response)
if invalid_count:
    print(f"Dropped {invalid_count} invalid Azure rows")

