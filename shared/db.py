"""Backward-compatible Supabase client import.

The canonical Streamlit/frontend client lives in services.supabase_client.
This module intentionally contains no fallback credentials.
"""

from config.settings import SUPABASE_KEY, SUPABASE_URL
from services.supabase_client import supabase

