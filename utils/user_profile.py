from services.supabase_client import supabase

def get_user_profile(user_id=None, email=None):
    """
    Fetch user profile (role, org, tenant, permissions) from public.users by id or email.
    Returns dict with keys: id, email, role, org, tenant, permissions
    """
    if not user_id and not email:
        raise ValueError("Must provide user_id or email")
    query = supabase.table("users").select("id, email, role, org_id, tenant, permissions")
    if user_id:
        query = query.eq("id", user_id)
    elif email:
        query = query.eq("email", email)
    resp = query.limit(1).execute()
    if resp.data:
        return resp.data[0]
    return None

