"""Runtime repository composition for Leadership Dashboard data."""

from __future__ import annotations

import os
from urllib.parse import urlparse

from repositories.leadership_repository import (
    SQLiteLeadershipRepository,
    SupabaseLeadershipRepository,
)
from services.runtime_configuration import is_valid_supabase_configuration
from services.supabase_client import supabase


class LeadershipConfigurationError(RuntimeError):
    """Raised when production leadership persistence cannot be composed safely."""


def _valid_supabase(url: str | None, key: str | None) -> bool:
    if not is_valid_supabase_configuration(url, key):
        return False
    hostname = (urlparse(str(url).strip()).hostname or "").casefold()
    return hostname == "supabase.co" or hostname.endswith(".supabase.co")


def leadership_repository(
    *,
    environment: str | None = None,
    supabase_url: str | None = None,
    supabase_key: str | None = None,
    client=None,
    connection_factory=None,
):
    runtime_environment = str(
        environment
        or os.getenv("ENVIRONMENT")
        or os.getenv("CLOUD_ADVISOR_ENV", "development")
    ).strip().lower()
    url = os.getenv("SUPABASE_URL", "") if supabase_url is None else supabase_url
    key = (
        os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        or os.getenv("SUPABASE_SERVICE_KEY")
        or os.getenv("SUPABASE_KEY")
        or os.getenv("SUPABASE_ANON_KEY", "")
    ) if supabase_key is None else supabase_key
    if runtime_environment == "production":
        if _valid_supabase(url, key):
            return SupabaseLeadershipRepository(client or supabase)
        raise LeadershipConfigurationError(
            "valid Supabase configuration is required for production leadership metrics"
        )
    kwargs = {"connection_factory": connection_factory} if connection_factory else {}
    return SQLiteLeadershipRepository(**kwargs)
