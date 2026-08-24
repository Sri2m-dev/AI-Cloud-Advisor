from data.supabase_client import supabase


def get_recommendations(tenant_id: str, status: str | None = None):
    query = (
        supabase.table("recommendations")
        .select("*")
        .eq("org_id", tenant_id)
        .order("created_at", desc=True)
    )
    if status:
        query = query.eq("status", status)
    response = query.execute()
    return response.data or []


def run_recommendation_engine(tenant_id: str) -> dict:
    from scripts.generate_recommendations import generate_recommendations

    generate_recommendations(org_id=tenant_id)
    return {"status": "queued", "engine": "rules+ai", "tenant_id": tenant_id}
