"""Backward-compatible Supabase client import.

Frontend Streamlit code should use services.supabase_client directly. This
module remains so older imports continue to resolve to the same safe client.
"""

from services.supabase_client import supabase

