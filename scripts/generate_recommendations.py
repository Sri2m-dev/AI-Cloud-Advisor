import argparse
import os
import sys
from uuid import UUID

from dotenv import load_dotenv

from supabase import create_client

load_dotenv()
_supabase_admin = None


def _get_supabase_source():
    """Load the source client only after the requested tenant has been validated."""
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
    from data.supabase_client import supabase

    return supabase


def _get_supabase_admin():
    """Create the service-role client only after a tenant scope has been validated."""
    global _supabase_admin
    if _supabase_admin is None:
        url = os.getenv("SUPABASE_URL")
        service_key = os.getenv("SUPABASE_SERVICE_KEY")
        _supabase_admin = create_client(url, service_key)
    return _supabase_admin


def generate_recommendations(org_id: str | None = None) -> None:
    if not isinstance(org_id, str) or not org_id.strip():
        raise ValueError("An explicit organization ID is required")

    try:
        target_org_id = str(UUID(org_id.strip()))
    except ValueError as exc:
        raise ValueError("Organization ID must be a valid UUID") from exc

    source = _get_supabase_source()
    usage = (
        source.table("usage_metrics")
        .select("*")
        .eq("organization_id", target_org_id)
        .execute()
        .data
    )
    unallocated = (
        source.table("unallocated_cost")
        .select("*")
        .eq("organization_id", target_org_id)
        .execute()
        .data
    )
    optimization = (
        source.table("optimization_results")
        .select("*")
        .eq("organization_id", target_org_id)
        .execute()
        .data
    )

    recommendations = []

    # Rule 1: High utilization
    for row in usage:
        if row.get("utilization", 0) > 80:
            recommendations.append(
                {
                    "organization_id": target_org_id,
                    "org_id": target_org_id,
                    "type": "OPTIMIZATION",
                    "message": "High utilization detected - consider autoscaling",
                    "impact": "HIGH",
                    "service": "Compute",
                    "description": "High utilization detected - consider autoscaling",
                    "estimated_savings": 0,
                    "status": "pending",
                }
            )

    # Rule 2: Unallocated cost
    for row in unallocated:
        if row.get("unallocated_percent", 0) > 20:
            recommendations.append(
                {
                    "organization_id": target_org_id,
                    "org_id": target_org_id,
                    "type": "GOVERNANCE",
                    "message": "Improve tagging for cost allocation",
                    "impact": "MEDIUM",
                    "service": "Billing",
                    "description": (
                        "Unallocated cost detected - improve tagging for cost allocation"
                    ),
                    "estimated_savings": 0,
                    "status": "pending",
                }
            )

    # Rule 3: Optimization savings
    for row in optimization:
        if row["baseline_cost"] > row["optimized_cost"]:
            savings_amount = row["baseline_cost"] - row["optimized_cost"]
            recommendations.append(
                {
                    "organization_id": target_org_id,
                    "org_id": target_org_id,
                    "type": "SAVINGS",
                    "message": f"Potential savings: {savings_amount}",
                    "impact": "HIGH",
                    "service": "Optimization",
                    "description": (
                        f"Potential savings of {savings_amount} identified from "
                        "optimization results"
                    ),
                    "estimated_savings": savings_amount,
                    "status": "pending",
                }
            )

    # Upsert into Supabase (service role bypasses RLS)
    if recommendations:
        try:
            _get_supabase_admin().table("recommendations").upsert(
                recommendations, on_conflict="org_id,message"
            ).execute()
        except Exception as exc:
            print("Upsert failed:", exc)

    print("Recommendations generated:", len(recommendations))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate recommendations for one organization")
    parser.add_argument("--org-id", required=True, help="Organization ID to process")
    generate_recommendations(org_id=parser.parse_args().org_id)
