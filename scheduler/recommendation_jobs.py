import os
import sys
import logging

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from dotenv import load_dotenv
load_dotenv()

from supabase import create_client
from data.supabase_client import supabase
from config import DEFAULT_ORG_ID

# ---------------------------------------------------
# Logging
# ---------------------------------------------------

logging.basicConfig(
    filename="logs/recommendation_jobs.log",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

# ---------------------------------------------------
# Supabase Admin Client
# ---------------------------------------------------

_url = os.getenv("SUPABASE_URL")
_service_key = os.getenv("SUPABASE_SERVICE_KEY")

supabase_admin = create_client(_url, _service_key)

# ---------------------------------------------------
# Recommendation Engine
# ---------------------------------------------------

def generate_recommendations(org_id: str | None = None):

    target_org_id = org_id or DEFAULT_ORG_ID

    logging.info(f"Starting recommendation generation for org: {target_org_id}")

    usage = supabase.table("usage_metrics").select("*").eq("organization_id", target_org_id).execute().data
    unallocated = supabase.table("unallocated_cost").select("*").eq("organization_id", target_org_id).execute().data
    optimization = supabase.table("optimization_results").select("*").eq("organization_id", target_org_id).execute().data

    recommendations = []

    # ---------------------------------------------------
    # Rule 1: High Utilization
    # ---------------------------------------------------

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

    # ---------------------------------------------------
    # Rule 2: Unallocated Cost
    # ---------------------------------------------------

    for row in unallocated:
        if row.get("unallocated_percent", 0) > 20:

            recommendations.append({
                "organization_id": target_org_id,
                "org_id": target_org_id,
                "type": "GOVERNANCE",
                "message": "Improve tagging for cost allocation",
                "impact": "MEDIUM",
                "service": "Billing",
                "description": "Unallocated cost detected - improve tagging",
                "estimated_savings": 0,
                "status": "pending"
            })

    # ---------------------------------------------------
    # Rule 3: Optimization Savings
    # ---------------------------------------------------

    for row in optimization:

        baseline = row.get("baseline_cost", 0)
        optimized = row.get("optimized_cost", 0)

        if baseline > optimized:

            savings_amount = baseline - optimized

            recommendations.append({
                "organization_id": target_org_id,
                "org_id": target_org_id,
                "type": "SAVINGS",
                "message": f"Potential savings: {savings_amount}",
                "impact": "HIGH",
                "service": "Optimization",
                "description": f"Potential savings of {savings_amount} identified",
                "estimated_savings": savings_amount,
                "status": "pending"
            })

    # ---------------------------------------------------
    # Upsert Recommendations
    # ---------------------------------------------------

    if recommendations:

        try:

            supabase_admin.table("recommendations").upsert(
                recommendations,
                on_conflict="org_id,message"
            ).execute()

            logging.info(f"Inserted/Updated {len(recommendations)} recommendations")

        except Exception as exc:

            logging.error(f"Recommendation upsert failed: {exc}")

    else:

        logging.info("No recommendations generated")

    print(f"Recommendations generated: {len(recommendations)}")


# ---------------------------------------------------
# APScheduler Wrapper
# ---------------------------------------------------

def run_recommendations():

    logging.info("Running scheduled recommendation job")

    try:

        generate_recommendations()

        logging.info("Recommendation job completed successfully")

    except Exception as exc:

        logging.error(f"Recommendation job failed: {exc}")


# ---------------------------------------------------
# Manual Execution
# ---------------------------------------------------

if __name__ == "__main__":
    run_recommendations()

