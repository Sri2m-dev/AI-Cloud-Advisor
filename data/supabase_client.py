import os

from dotenv import load_dotenv

from supabase import create_client

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")


class _SupabaseProxy:
    def __init__(self):
        self._client = None

    def _initialize(self):
        if self._client is None:
            if not SUPABASE_URL:
                raise ValueError("SUPABASE_URL is missing")

            if not SUPABASE_SERVICE_KEY:
                raise ValueError("SUPABASE_SERVICE_KEY is missing")

            self._client = create_client(
                SUPABASE_URL,
                SUPABASE_SERVICE_KEY,
            )

        return self._client

    def __getattr__(self, name):
        return getattr(self._initialize(), name)


supabase = _SupabaseProxy()
supabase_admin = supabase
