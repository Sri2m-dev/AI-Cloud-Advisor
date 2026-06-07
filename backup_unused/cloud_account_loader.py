from shared.db import supabase


def list_cloud_accounts_by_client(client_id):
    response = supabase.table("cloud_accounts") \
        .select("*") \
        .eq("client_id", client_id) \
        .execute()

    return response.data or []

