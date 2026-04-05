import os

from shared.supabase_client import get_supabase_client


def _get_role_data(client, email):
    try:
        return client.table("user_roles") \
            .select("id,role,client_id") \
            .eq("email", email) \
            .execute().data
    except Exception:
        # Fallback for deployments where user_roles does not have client_id.
        return client.table("user_roles") \
            .select("id,role") \
            .eq("email", email) \
            .execute().data


def login_user(email, password):
    try:
        client = get_supabase_client()

        # Supabase Auth
        res = client.auth.sign_in_with_password({
            "email": email,
            "password": password
        })

        if res.user:
            role_data = _get_role_data(client, email)
            role = role_data[0]["role"] if role_data else "User"
            # Use the row's primary key UUID as client_id — user_roles.id is always a valid UUID
            client_id = role_data[0].get("client_id") or role_data[0].get("id") if role_data else None

            return {"status": True, "role": role, "client_id": client_id}

        return {"status": False, "error": "Invalid credentials"}
    except Exception as e:
        error_text = str(e)

        if "Email not confirmed" in error_text and os.getenv("DEV_AUTH_BYPASS", "false").lower() == "true":
            role_data = _get_role_data(client, email)
            if role_data:
                role = role_data[0]["role"]
                client_id = role_data[0].get("client_id") or role_data[0].get("id")
                return {"status": True, "role": role, "client_id": client_id}

        return {"status": False, "error": str(e)}
