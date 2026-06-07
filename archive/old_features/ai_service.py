from dotenv import load_dotenv
import os
import pandas as pd
from datetime import datetime
from supabase import create_client

load_dotenv()

# -----------------------
# CONFIG
# -----------------------
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

# fallback (temporary - OK for dev only)
if not SUPABASE_URL:
    SUPABASE_URL = "https://iafrrtmvvqmuksvprrsj.supabase.co"
    SUPABASE_KEY = "sb_publishable_P8qKIdx-abXX6tbnO_72MQ_tuVyaEI8"

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)


# -----------------------
# 🔐 DATA MASKING
# -----------------------
def mask_sensitive_data(df: pd.DataFrame):
    """
    Removes sensitive identifiers before exposing data
    """
    df_copy = df.copy()

    sensitive_cols = ["instance_id", "account_id", "resource_id"]

    for col in sensitive_cols:
        if col in df_copy.columns:
            df_copy.drop(columns=[col], inplace=True)

    return df_copy


# -----------------------
# 📜 AUDIT LOG
# -----------------------
def log_user_action(user_email: str, action: str):
    """
    Generic audit logger (Phase 1 safe)
    """
    try:
        supabase.table("audit_logs").insert({
            "user_email": user_email,
            "action": action,
            "timestamp": datetime.utcnow().isoformat()
        }).execute()
    except Exception as e:
        print("LOG ERROR:", e)


# -----------------------
# 🚫 AI DISABLED (PHASE 1)
# -----------------------
def generate_secure_response(*args, **kwargs):
    """
    Placeholder to avoid breaking imports
    """
    return "AI features are disabled in this demo version."

