from datetime import date
from typing import Optional

import pandas as pd

from data.supabase_client import supabase


def fetch_cost_data(
    tenant_id: str,
    cloud: Optional[str] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    requested_by: Optional[str] = None,
):
    try:
        print(f"[COST] tenant_id={tenant_id}")

        query = (
            supabase
            .table("unified_cloud_costs")
            .select("*")
            .eq("organization_id", tenant_id)
        )

        if cloud:
            query = query.eq("cloud", cloud)

        if start_date:
            query = query.gte(
                "usage_date",
                start_date.isoformat(),
            )

        if end_date:
            query = query.lte(
                "usage_date",
                end_date.isoformat(),
            )

        response = query.execute()

        rows = response.data or []

        print(f"[COST] rows returned={len(rows)}")

        if not rows:
            return {
                "tenant_id": tenant_id,
                "requested_by": requested_by,
                "record_count": 0,
                "total_cost": 0.0,
                "cloud_breakdown": [],
                "daily_trend": [],
            }

        df = pd.DataFrame(rows)

        if "cost" not in df.columns:
            df["cost"] = 0

        df["cost"] = pd.to_numeric(
            df["cost"],
            errors="coerce",
        ).fillna(0)

        cloud_breakdown = []

        if "cloud" in df.columns:
            cloud_breakdown = (
                df.groupby("cloud", dropna=False)["cost"]
                .sum()
                .reset_index()
                .rename(
                    columns={
                        "cloud": "name",
                        "cost": "cost",
                    }
                )
                .to_dict("records")
            )

        daily_trend = []

        if "usage_date" in df.columns:
            df["usage_date"] = pd.to_datetime(
                df["usage_date"],
                errors="coerce",
            )

            trend_df = (
                df.dropna(subset=["usage_date"])
                .groupby(df["usage_date"].dt.date)["cost"]
                .sum()
                .reset_index(name="cost")
            )

            trend_df["date"] = trend_df["usage_date"].astype(str)

            daily_trend = (
                trend_df[["date", "cost"]]
                .to_dict("records")
            )

        return {
            "tenant_id": tenant_id,
            "requested_by": requested_by,
            "record_count": len(rows),
            "total_cost": float(df["cost"].sum()),
            "cloud_breakdown": cloud_breakdown,
            "daily_trend": daily_trend,
        }

    except Exception as exc:
        import traceback

        traceback.print_exc()

        return {
            "tenant_id": tenant_id,
            "requested_by": requested_by,
            "record_count": 0,
            "total_cost": 0.0,
            "cloud_breakdown": [],
            "daily_trend": [],
            "error": str(exc),
        }
