# data/queries.py

import re
from collections import defaultdict
from datetime import datetime

from data.supabase_client import supabase, supabase_admin
from config import DEFAULT_ORG_ID


def get_total_cost(organization_id=DEFAULT_ORG_ID):
    res = supabase.table("mart_total_cost") \
        .select("total_cost") \
        .eq("organization_id", organization_id) \
        .execute()

    return res.data


def get_optimization_data(organization_id=DEFAULT_ORG_ID):
    res = supabase.table("optimization_results") \
        .select("*") \
        .eq("organization_id", organization_id) \
        .execute()

    return res.data


def get_saas_cost(organization_id=DEFAULT_ORG_ID):
    res = supabase.table("saas_cost") \
        .select("*") \
        .eq("organization_id", organization_id) \
        .execute()

    return res.data


def get_usage_metrics(organization_id=DEFAULT_ORG_ID):
    res = supabase.table("usage_metrics") \
        .select("*") \
        .eq("organization_id", organization_id) \
        .execute()

    return res.data


def get_unallocated_cost(organization_id=DEFAULT_ORG_ID):
    res = supabase.table("unallocated_cost") \
        .select("*") \
        .eq("organization_id", organization_id) \
        .execute()

    return res.data


def get_organizations():
    res = supabase.table("organizations") \
        .select("*") \
        .execute()

    return res.data


def extract_savings(rec):
    savings = rec.get("estimated_savings")

    if savings and savings > 0:
        return savings

    # fallback -> extract from message
    msg = rec.get("message", "")
    match = re.search(r"(\d+)", msg)

    if match:
        return int(match.group(1))

    return 0


def get_recommendations(organization_id=DEFAULT_ORG_ID):
    res = supabase.table("recommendations").select("*").eq("organization_id", organization_id).execute()
    data = res.data or []

    best = {}

    for r in data:
        msg = r.get("message")
        savings = extract_savings(r)

        r["estimated_savings"] = savings  # normalize here
        r["service"] = r.get("service") or "Other"  # normalize null service

        if msg not in best:
            best[msg] = r
        else:
            if savings > best[msg].get("estimated_savings", 0):
                best[msg] = r

    return list(best.values())


def update_status(rec_id, status, organization_id=DEFAULT_ORG_ID):
    payload = {"status": status}

    if status == "done":
        payload["completed_at"] = datetime.utcnow().isoformat()

    return supabase_admin.table("recommendations") \
        .update(payload) \
        .eq("id", rec_id) \
        .eq("organization_id", organization_id) \
        .execute()


def get_realized_savings_trend(org_id):
    res = supabase.table("recommendations") \
        .select("*") \
        .eq("organization_id", org_id) \
        .eq("status", "done") \
        .execute()

    data = res.data or []

    trend = defaultdict(float)

    for r in data:
        if r.get("completed_at") and r.get("estimated_savings"):
            date = r["completed_at"][:10]
            trend[date] += r.get("estimated_savings") or 0

    return sorted(
        [{"date": k, "savings": v} for k, v in trend.items()],
        key=lambda x: x["date"]
    )

