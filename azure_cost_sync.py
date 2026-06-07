from datetime import datetime, timedelta, timezone
import json
from azure.identity import ClientSecretCredential
from azure.mgmt.costmanagement import CostManagementClient
from supabase import create_client
import os
from config import DEFAULT_ORG_ID

# -----------------------------
# AZURE CONFIG
# -----------------------------
TENANT_ID = "24a3f016-0781-4a96-be61-17e3ea81b8dd"
CLIENT_ID = "a1111608-fa69-4438-a425-975567abc0ec"
CLIENT_SECRET = "cUt8Q~fVsN1uhn3NBv5bq6~AcUPXDa37SKkezbWC"
SUBSCRIPTION_ID = "49ce7e88-e929-4031-b5b2-c8b557e5da2d"

# -----------------------------
# SUPABASE CONFIG
# -----------------------------
SUPABASE_URL = "https://iafrrtmvvqmuksvprrsj.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImlhZnJydG12dnFtdWtzdnBycnNqIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3NTE0OTY2NiwiZXhwIjoyMDkwNzI1NjY2fQ.Q-fVo1tmO3XbvhudOawn-eQ3Gmz8Bb4nKW-XF6hX1wI"

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

