"""
Operations Workspace Repository
"""

from services.supabase_client import supabase


class OperationsWorkspaceRepository:

    @staticmethod
    def get_approval_requests():
        return (
            supabase.table("approval_requests")
            .select("*")
            .order("created_at", desc=True)
            .limit(50)
            .execute()
            .data
        )

    @staticmethod
    def get_recommendations():
        return (
            supabase.table("recommendations")
            .select("*")
            .order("created_at", desc=True)
            .limit(50)
            .execute()
            .data
        )

    @staticmethod
    def get_audit_events():
        return (
            supabase.table("audit_events")
            .select("*")
            .order("created_at", desc=True)
            .limit(50)
            .execute()
            .data
        )

    @staticmethod
    def get_cost_anomalies():
        return (
            supabase.table("cost_anomaly_org_view")
            .select("*")
            .limit(100)
            .execute()
            .data
        )

    @staticmethod
    def get_cloud_costs():
        return (
            supabase.table("unified_cloud_costs")
            .select("*")
            .limit(1000)
            .execute()
            .data
        )

    @staticmethod
    def get_summary():

        approvals = (
            supabase.table("approval_requests")
            .select("*")
            .execute()
            .data
        )

        recommendations = (
            supabase.table("recommendations")
            .select("*")
            .execute()
            .data
        )

        anomalies = (
            supabase.table("cost_anomaly_org_view")
            .select("*")
            .execute()
            .data
        )

        audit = (
            supabase.table("audit_events")
            .select("*")
            .execute()
            .data
        )

        return {
            "approvals": len(approvals),
            "recommendations": len(recommendations),
            "anomalies": len(anomalies),
            "audit_events": len(audit),
        }
