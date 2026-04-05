import re
import pandas as pd
from shared.supabase_client import get_supabase_client

_UUID_RE = re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', re.I)


def get_usage_metrics(client_id):
    if not client_id or not _UUID_RE.match(str(client_id)):
        return pd.DataFrame()
    client = get_supabase_client()
    data = client.table("usage_metrics") \
        .select("*") \
        .eq("client_id", client_id) \
        .execute().data
    return pd.DataFrame(data)


def get_cloud_accounts():
    client = get_supabase_client()
    data = client.table("cloud_accounts").select("*").execute().data
    return pd.DataFrame(data)


def get_recommendations(client_id=None):
    client = get_supabase_client()
    query = client.table("recommendations").select("*")

    if client_id and _UUID_RE.match(str(client_id)):
        query = query.eq("client_id", client_id)

    data = query.execute().data
    return pd.DataFrame(data)


def update_recommendation_status(recommendation_id, status):
    if not recommendation_id:
        return {"status": False, "error": "Missing recommendation id"}

    client = get_supabase_client()

    try:
        client.table("recommendations").update({"status": status}).eq("id", recommendation_id).execute()
        return {"status": True, "id": recommendation_id, "new_status": status}
    except Exception as exc:
        return {"status": False, "error": str(exc)}
