from data.supabase_client import supabase
from scripts.generate_recommendations import generate_recommendations
from backend.services.tenant_scope import scoped_query


def get_recommendations(tenant_id: str, status: str | None = None):
    query = scoped_query(supabase, "recommendations", tenant_id).order("created_at", desc=True)
    if status:
        query = query.eq("status", status)
    response = query.execute()
    return response.data or []


def run_recommendation_engine(tenant_id: str) -> dict:
    generate_recommendations(org_id=tenant_id)
    return {"status": "queued", "engine": "rules+ai", "tenant_id": tenant_id}

