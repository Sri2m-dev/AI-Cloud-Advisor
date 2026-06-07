# Legacy auth/login compatibility shim (minimal, non-production)

import streamlit as st

# Minimal legacy users mapping used by a few legacy scripts. Do not use for production.
users = {
    "admin": {"password": "admin"},
}


def verify_user(username: str, password: str) -> bool:
    entry = users.get(username)
    return bool(entry and entry.get("password") == password)
# Note: All authentication now uses Supabase Auth (see pages/0_Login.py).

