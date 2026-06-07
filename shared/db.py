import os

from supabase import create_client


DEFAULT_SUPABASE_URL = "https://iafrrtmvvqmuksvprrsj.supabase.co"
DEFAULT_SUPABASE_KEY = "sb_publishable_P8qKIdx-abXX6tbnO_72MQ_tuVyaEI8"


def _read_secret(name: str, default: str = "") -> str:
    value = os.getenv(name)
    if value:
        return value

    try:
        import streamlit as st

        secret_value = st.secrets.get(name)
        if secret_value:
            return str(secret_value)
    except Exception:
        pass

    return default


SUPABASE_URL = _read_secret("SUPABASE_URL", DEFAULT_SUPABASE_URL)
SUPABASE_KEY = _read_secret("SUPABASE_KEY", DEFAULT_SUPABASE_KEY)

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

