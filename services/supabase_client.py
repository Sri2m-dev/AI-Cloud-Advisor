"""
Central Supabase client initialization for the entire app.
"""

from supabase import create_client

from config.settings import (
    SUPABASE_URL,
    SUPABASE_KEY,
)


class _SupabaseProxy:
    def __init__(self) -> None:
        self._client = None

    def _initialize(self):
        if self._client is None:

            print("\n" + "=" * 80)
            print("SUPABASE CLIENT INITIALIZATION")
            print(f"SUPABASE_URL: {SUPABASE_URL}")
            print(f"SUPABASE_KEY PRESENT: {bool(SUPABASE_KEY)}")

            if not SUPABASE_URL:
                raise RuntimeError(
                    "SUPABASE_URL is required to initialize the Supabase client"
                )

            if not SUPABASE_KEY:
                raise RuntimeError(
                    "SUPABASE_KEY is required to initialize the Supabase client"
                )

            self._client = create_client(
                SUPABASE_URL,
                SUPABASE_KEY,
            )

            print("Supabase client initialized successfully.")
            print("=" * 80 + "\n")

        return self._client

    def __getattr__(self, name):
        client = self._initialize()
        return getattr(client, name)


supabase = _SupabaseProxy()