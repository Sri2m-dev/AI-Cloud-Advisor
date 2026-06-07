from services.supabase_client import supabase
import pandas as pd
import uuid
from datetime import datetime
from config import DEFAULT_ORG_ID

class RecommendationEngine:
    @staticmethod
    def generate_idle_resource_recommendations(org_id=DEFAULT_ORG_ID):
        response = supabase.table(
            "unified_cloud_costs"
        ).select("*").eq("organization_id", org_id).execute()
        df = pd.DataFrame(response.data)
        if df.empty or "utilization" not in df.columns:
            return []
        recommendations = []
        idle_resources = df[df["utilization"] < 10]
        for _, row in idle_resources.iterrows():
            resource_id = row.get("resource_id") or "Unknown Resource"
            service_name = row.get("service_name") or "Unknown Service"
            cloud = row.get("cloud") or "Unknown Cloud"
            utilization = row.get("utilization", 0)
            recommendations.append({
                "id": str(uuid.uuid4()),
                "organization_id": org_id,
                "title": "Idle Resource Detected",
                "recommendation_type": "Cost Optimization",
                "description": (
                    f"""
{service_name} resource
in {cloud} appears underutilized.\n\nCurrent utilization:\n{utilization}%\n"""
                ),
                "priority": "High",
                "status": "Pending",
                "estimated_savings": float(row.get("cost", 0)) * 0.7,
                "service": service_name,
                "owner": row.get("owner"),
                "resource_id": resource_id,
                "created_at": datetime.utcnow().isoformat()
            })
        return recommendations

    @staticmethod
    def generate_untagged_resource_recommendations(org_id=DEFAULT_ORG_ID):
        response = supabase.table(
            "unified_cloud_costs"
        ).select("*").eq("organization_id", org_id).execute()
        df = pd.DataFrame(response.data)
        if df.empty or "tags" not in df.columns:
            return []
        recommendations = []
        untagged = df[df["tags"].isnull()]
        for _, row in untagged.iterrows():
            resource_id = row.get("resource_id") or "Unknown Resource"
            service_name = row.get("service_name") or "Unknown Service"
            recommendations.append({
                "id": str(uuid.uuid4()),
                "organization_id": org_id,
                "title": "Missing Mandatory Tags",
                "recommendation_type": "Governance",
                "description": (
                    f"Resource {resource_id} ({service_name}) is missing governance tags."
                ),
                "priority": "Medium",
                "status": "Pending",
                "estimated_savings": 0,
                "service": service_name,
                "owner": row.get("owner"),
                "resource_id": resource_id,
                "created_at": datetime.utcnow().isoformat()
            })
        return recommendations

    @staticmethod
    def generate_orphaned_resource_recommendations(org_id=DEFAULT_ORG_ID):
        response = supabase.table(
            "unified_cloud_costs"
        ).select("*").eq("organization_id", org_id).execute()
        df = pd.DataFrame(response.data)
        if df.empty or "owner" not in df.columns:
            return []
        recommendations = []
        orphaned = df[df["owner"].isnull()]
        for _, row in orphaned.iterrows():
            recommendations.append({
                "id": str(uuid.uuid4()),
                "organization_id": org_id,
                "title": "Orphaned Resource",
                "recommendation_type": "Governance",
                "description": (
                    f"Resource {row['resource_id']} has no assigned owner."
                ),
                "priority": "High",
                "status": "Pending",
                "estimated_savings": 0,
                "service": row.get("service_name"),
                "owner": None,
                "created_at": datetime.utcnow().isoformat()
            })
        return recommendations

    @staticmethod
    def generate_cost_anomaly_recommendations():
        # Placeholder: implement cost anomaly logic as needed
        return []

    @staticmethod
    def save_recommendations(recommendations):
        if not recommendations:
            return
        supabase.table(
            "recommendations"
        ).insert(recommendations).execute()

    @staticmethod
    def run_all_recommendation_jobs(org_id=DEFAULT_ORG_ID):
        idle = (
            RecommendationEngine
            .generate_idle_resource_recommendations(org_id)
        )
        untagged = (
            RecommendationEngine
            .generate_untagged_resource_recommendations(org_id)
        )
        orphaned = (
            RecommendationEngine
            .generate_orphaned_resource_recommendations(org_id)
        )
        all_recommendations = (
            idle +
            untagged +
            orphaned
        )
        RecommendationEngine.save_recommendations(
            all_recommendations
        )
        return {
            "generated": len(all_recommendations)
        }

