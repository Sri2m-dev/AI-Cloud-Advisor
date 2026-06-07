from services.recommendation_engine import RecommendationEngine
from services.analytics_service import AnalyticsService
from services.supabase_client import supabase
from config import DEFAULT_ORG_ID
import pandas as pd
from datetime import datetime, timedelta

class GovernanceService:
    @staticmethod
    def get_idle_resource_count(org_id=DEFAULT_ORG_ID):
        # Count of idle resource recommendations
        response = supabase.table("recommendations").select("*").eq("organization_id", org_id).eq("recommendation_type", "Cost Optimization").eq("title", "Idle Resource Detected").execute()
        df = pd.DataFrame(response.data)
        return len(df) if not df.empty else 0

    @staticmethod
    def get_governance_violation_count(org_id=DEFAULT_ORG_ID):
        # Count of governance violation recommendations (e.g., missing tags, orphaned)
        response = supabase.table("recommendations").select("*").eq("organization_id", org_id).eq("recommendation_type", "Governance").execute()
        df = pd.DataFrame(response.data)
        return len(df) if not df.empty else 0

    @staticmethod
    def get_optimization_coverage(org_id=DEFAULT_ORG_ID):
        # Ratio of completed recommendations to total recommendations
        response = supabase.table("recommendations").select("status").eq("organization_id", org_id).execute()
        df = pd.DataFrame(response.data)
        if df.empty:
            return 0.0
        total = len(df)
        completed = len(df[df["status"] == "Completed"])
        return round(completed / total, 2) if total > 0 else 0.0

    @staticmethod
    def get_sla_compliance(org_id=DEFAULT_ORG_ID):
        # Ratio of approvals completed within SLA (e.g., 3 days)
        try:
            response = supabase.table("approval_queue").select("created_at,completed_at").eq("organization_id", org_id).execute()
            df = pd.DataFrame(response.data)
            if df.empty or "completed_at" not in df.columns:
                return 0.0
            df = df.dropna(subset=["completed_at"])
            if df.empty:
                return 0.0
            df["created_at"] = pd.to_datetime(df["created_at"])
            df["completed_at"] = pd.to_datetime(df["completed_at"])
            df["sla_met"] = (df["completed_at"] - df["created_at"]) <= timedelta(days=3)
            sla_met = df["sla_met"].sum()
            return round(sla_met / len(df), 2) if len(df) > 0 else 0.0
        except Exception:
            return 0.0

    @staticmethod
    def get_savings_realization(org_id=DEFAULT_ORG_ID):
        # Sum of estimated_savings for completed recommendations
        response = supabase.table("recommendations").select("estimated_savings,status").eq("organization_id", org_id).execute()
        df = pd.DataFrame(response.data)
        if df.empty or "estimated_savings" not in df.columns:
            return 0.0
        completed = df[df["status"] == "Completed"]
        return float(completed["estimated_savings"].sum()) if not completed.empty else 0.0

    @staticmethod
    def calculate_governance_score(org_id=DEFAULT_ORG_ID):
        # Each metric is normalized to a 0-1 scale, then averaged
        idle_count = GovernanceService.get_idle_resource_count(org_id)
        gov_violations = GovernanceService.get_governance_violation_count(org_id)
        optimization_coverage = GovernanceService.get_optimization_coverage(org_id)
        sla_compliance = GovernanceService.get_sla_compliance(org_id)
        savings_realization = GovernanceService.get_savings_realization(org_id)

        # Normalize: fewer idle/violations is better, higher coverage/savings/sla is better
        idle_score = max(0, 1 - idle_count / 10)  # Example: 10+ idle = 0
        gov_score = max(0, 1 - gov_violations / 10)  # Example: 10+ violations = 0
        opt_score = optimization_coverage  # Already 0-1
        sla_score = sla_compliance  # Already 0-1
        # Normalize savings: assume 10,000 is max for 1.0
        savings_score = min(1.0, savings_realization / 10000)

        final_score = round((idle_score + gov_score + opt_score + sla_score + savings_score) / 5, 2)

        return {
            "overall_score": final_score,
            "idle_score": idle_score,
            "governance_score": gov_score,
            "optimization_coverage": opt_score,
            "sla_compliance": sla_score,
            "savings_realization": savings_score,
            "raw": {
                "idle_count": idle_count,
                "governance_violations": gov_violations,
                "optimization_coverage": optimization_coverage,
                "sla_compliance": sla_compliance,
                "savings_realization": savings_realization
            }
        }

    @staticmethod
    def get_live_governance_report(org_id=DEFAULT_ORG_ID):
        return GovernanceService.calculate_governance_score(org_id)
"""
Governance service: business logic for compliance, policy, and governance workflows.
"""
from services.supabase_client import supabase

def get_governance_status(org_id):
    # TODO: Implement actual logic
    return {}

