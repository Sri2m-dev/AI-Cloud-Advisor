import time
import os
import boto3
import pandas as pd
from supabase import create_client
from config import DEFAULT_ORG_ID

# =====================================================
# SUPABASE CONFIG
# =====================================================

SUPABASE_URL = os.getenv(
    "SUPABASE_URL",
    "https://iafrrtmvvqmuksvprrsj.supabase.co"
)
SUPABASE_KEY = os.getenv(
    "SUPABASE_SERVICE_ROLE_KEY",
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImlhZnJydG12dnFtdWtzdnBycnNqIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3NTE0OTY2NiwiZXhwIjoyMDkwNzI1NjY2fQ.Q-fVo1tmO3XbvhudOawn-eQ3Gmz8Bb4nKW-XF6hX1wI"
)

if SUPABASE_KEY.startswith("sb_publishable_"):
    print(
        "Warning: publishable key detected. Inserts may fail under RLS. "
        "Set SUPABASE_SERVICE_ROLE_KEY for backend ingestion."
    )

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# =====================================================
# ATHENA CONFIG
# =====================================================

DATABASE = "finops"

QUERY = """
SELECT
    'aws' AS cloud,
    'aws-main' AS account_name,
    line_item_product_code AS service_name,
    'global' AS region,
    '' AS resource_id,
    DATE(line_item_usage_start_date) AS usage_date,
    SUM(line_item_usage_amount) AS usage_quantity,
    SUM(line_item_unblended_cost) AS cost,
    'USD' AS currency
FROM data
WHERE line_item_line_item_type = 'Usage'
GROUP BY 1,2,3,4,5,6,9
"""

OUTPUT_LOCATION = "s3://sribucket-s3/athena-results/"

athena = boto3.client(
    "athena",
    region_name="us-east-1"
)

# =====================================================
# START ATHENA QUERY
# =====================================================

response = athena.start_query_execution(
    QueryString=QUERY,
    QueryExecutionContext={
        "Database": DATABASE
    },
    ResultConfiguration={
        "OutputLocation": OUTPUT_LOCATION
    }
)

query_execution_id = response["QueryExecutionId"]

print(f"\nQuery started: {query_execution_id}")

# =====================================================
# WAIT FOR QUERY TO COMPLETE
# =====================================================

while True:

    status_response = athena.get_query_execution(
        QueryExecutionId=query_execution_id
    )

    status = status_response["QueryExecution"]["Status"]["State"]

    print("Current status:", status)

    if status in ["SUCCEEDED", "FAILED", "CANCELLED"]:
        break

    time.sleep(3)

# =====================================================
# HANDLE FAILURE
# =====================================================

if status != "SUCCEEDED":
    failure_reason = status_response["QueryExecution"]["Status"].get(
        "StateChangeReason",
        "No reason returned by Athena"
    )
    raise Exception(
        f"Athena query failed with status: {status}. Reason: {failure_reason}"
    )

print("\nAthena query completed successfully.")

# =====================================================
# FETCH RESULTS
# =====================================================

results_paginator = athena.get_paginator("get_query_results")

results_iter = results_paginator.paginate(
    QueryExecutionId=query_execution_id
)

rows = []

for results_page in results_iter:

    for row in results_page["ResultSet"]["Rows"][1:]:

        data = row["Data"]

        values = []

        for item in data:
            values.append(item.get("VarCharValue", None))

        rows.append(values)

# =====================================================
# CREATE DATAFRAME
# =====================================================

columns = [
    "cloud",
    "account_name",
    "service_name",
    "region",
    "resource_id",
    "usage_date",
    "usage_quantity",
    "cost",
    "currency"
]

df = pd.DataFrame(rows, columns=columns)

# =====================================================
# DATA CLEANING
# =====================================================

df["usage_quantity"] = pd.to_numeric(
    df["usage_quantity"],
    errors="coerce"
)

df["cost"] = pd.to_numeric(
    df["cost"],
    errors="coerce"
)

df = df.fillna("")

print("\nPreview:")
print(df.head())

print(f"\nTotal records fetched: {len(df)}")

# =====================================================
# INSERT INTO SUPABASE
# =====================================================

records = df.to_dict(orient="records")
for record in records:
    record["organization_id"] = DEFAULT_ORG_ID
    record.setdefault("org_id", DEFAULT_ORG_ID)

batch_size = 100

for i in range(0, len(records), batch_size):

    batch = records[i:i + batch_size]

    response = supabase.table(
        "unified_cloud_costs"
    ).upsert(
        batch,
        on_conflict="cloud,account_name,service_name,usage_date"
    ).execute()

    print(f"Upserted batch {i} to {i + len(batch)}")

print("\nData successfully upserted into Supabase.")

