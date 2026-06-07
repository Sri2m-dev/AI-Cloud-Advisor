import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from dotenv import load_dotenv
load_dotenv()

from supabase import create_client
from data.supabase_client import supabase  # for reads
from config import DEFAULT_ORG_ID

# Service role client — bypasses RLS for writes
_url = os.getenv("SUPABASE_URL")
_service_key = os.getenv("SUPABASE_SERVICE_KEY")
supabase_admin = create_client(_url, _service_key)


def generate_recommendations(org_id: str | None = None):
    target_org_id = org_id or DEFAULT_ORG_ID
    usage = supabase.table("usage_metrics").select("*").eq("organization_id", target_org_id).execute().data
    unallocated = supabase.table("unallocated_cost").select("*").eq("organization_id", target_org_id).execute().data
    optimization = supabase.table("optimization_results").select("*").eq("organization_id", target_org_id).execute().data

    recommendations = []

    # Rule 1: High utilization
    for row in usage:
        if row.get("utilization", 0) > 80:
            recommendations.append({
                "organization_id": target_org_id,
                "org_id": target_org_id,
                "type": "OPTIMIZATION",
                "message": "High utilization detected - consider autoscaling",
                "impact": "HIGH",
                "service": "Compute",
                "description": "High utilization detected - consider autoscaling",
                "estimated_savings": 0,
                "status": "pending"
            })

    # Rule 2: Unallocated cost
    for row in unallocated:
        if row.get("unallocated_percent", 0) > 20:
            recommendations.append({
                "organization_id": target_org_id,
                "org_id": target_org_id,
                "type": "GOVERNANCE",
                "message": "Improve tagging for cost allocation",
                "impact": "MEDIUM",
                "service": "Billing",
                "description": "Unallocated cost detected - improve tagging for cost allocation",
                "estimated_savings": 0,
                "status": "pending"
            })

    # Rule 3: Optimization savings
    for row in optimization:
        if row["baseline_cost"] > row["optimized_cost"]:
            savings_amount = row['baseline_cost'] - row['optimized_cost']
            recommendations.append({
                "organization_id": target_org_id,
                "org_id": target_org_id,
                "type": "SAVINGS",
                "message": f"Potential savings: {savings_amount}",
                "impact": "HIGH",
                "service": "Optimization",
                "description": f"Potential savings of {savings_amount} identified from optimization results",
                "estimated_savings": savings_amount,
                "status": "pending"
            })

    # Upsert into Supabase (service role bypasses RLS)
    if recommendations:
        try:
            data = recommendations
            supabase_admin.table("recommendations").upsert(
                data,
                on_conflict="org_id,message"
            ).execute()
        except Exception as exc:
            print("Upsert failed:", exc)

    print("Recommendations generated:", len(recommendations))


if __name__ == "__main__":
    generate_recommendations()

