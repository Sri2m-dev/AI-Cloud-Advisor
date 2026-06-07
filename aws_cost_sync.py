from __future__ import annotations

from datetime import date
from typing import Any

import boto3

from config import DEFAULT_ORG_ID
from data.supabase_client import supabase_admin

from core.transformers import (
    COSTS_REQUIRED_FIELDS,
    COSTS_TYPE_MAP,
)

from utils.schema_validator import validate_schema


def fetch_aws_mtd_service_costs() -> list[dict[str, Any]]:
    """Fetch current-month AWS spend grouped by service using Cost Explorer API."""

    end_date = date.today()
    start_date = end_date.replace(day=1)

    ce = boto3.client("ce", region_name="us-east-1")

    next_token: str | None = None
    rows: list[dict[str, Any]] = []

    while True:
        kwargs: dict[str, Any] = {
            "TimePeriod": {
                "Start": start_date.isoformat(),
                "End": end_date.isoformat(),
            },
            "Granularity": "MONTHLY",
            "Metrics": ["UnblendedCost"],
            "GroupBy": [{"Type": "DIMENSION", "Key": "SERVICE"}],
        }

        if next_token:
            kwargs["NextPageToken"] = next_token

        response = ce.get_cost_and_usage(**kwargs)

        monthly_groups = []

        if response.get("ResultsByTime"):
            monthly_groups = response["ResultsByTime"][0].get("Groups", [])

        for group in monthly_groups:
            service_name = (group.get("Keys") or ["Other"])[0] or "Other"

            amount = (
                group.get("Metrics", {})
                .get("UnblendedCost", {})
                .get("Amount", "0")
            )

            rows.append(
                {
                    "organization_id": DEFAULT_ORG_ID,
                    "org_id": DEFAULT_ORG_ID,
                    "cloud": "aws",
                    "service_name": service_name,
                    "total_cost": float(amount),
                }
            )

        next_token = response.get("NextPageToken")

        if not next_token:
            break

    return rows


def sync_aws_costs() -> int:
    """Sync AWS current-month service costs into Supabase costs table."""

    rows = fetch_aws_mtd_service_costs()

    if not rows:
        print("No AWS cost rows returned from Cost Explorer.")
        return 0

    valid_rows = []
    invalid_count = 0

    for row in rows:
        validation = validate_schema(
            row,
            required_fields=COSTS_REQUIRED_FIELDS,
            type_map=COSTS_TYPE_MAP,
            allow_extra=True,
        )

        if validation["valid"]:
            valid_rows.append(row)
        else:
            invalid_count += 1

    if not valid_rows:
        print("No valid AWS cost rows after schema validation.")
        return 0

    supabase_admin.table("costs").upsert(
        valid_rows,
        on_conflict="org_id,cloud,service_name",
    ).execute()

    print(f"Upserted AWS rows: {len(valid_rows)}")

    if invalid_count:
        print(f"Dropped {invalid_count} invalid AWS rows")

    return len(valid_rows)


if __name__ == "__main__":
    sync_aws_costs()
