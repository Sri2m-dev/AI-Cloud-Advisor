"""Runtime repository selection for Finance persona data."""

from __future__ import annotations

import os
from urllib.parse import urlparse

from repositories.technology_spend_repository import (
    SQLiteTechnologySpendRepository,
    SupabaseTechnologySpendRepository,
)
from services.runtime_configuration import is_valid_supabase_configuration
from services.supabase_client import supabase


class TechnologySpendConfigurationError(RuntimeError):
    pass


def _valid_supabase(url, key) -> bool:
    if not is_valid_supabase_configuration(url, key):
        return False
    hostname = (urlparse(str(url).strip()).hostname or "").casefold()
    return hostname == "supabase.co" or hostname.endswith(".supabase.co")


def technology_spend_repository(
    *, environment=None, supabase_url=None, supabase_key=None, client=None, connection_factory=None
):
    runtime = (
        str(
            environment or os.getenv("ENVIRONMENT") or os.getenv("CLOUD_ADVISOR_ENV", "development")
        )
        .strip()
        .lower()
    )
    url = os.getenv("SUPABASE_URL", "") if supabase_url is None else supabase_url
    key = (
        (
            os.getenv("SUPABASE_SERVICE_ROLE_KEY")
            or os.getenv("SUPABASE_SERVICE_KEY")
            or os.getenv("SUPABASE_KEY")
            or os.getenv("SUPABASE_ANON_KEY", "")
        )
        if supabase_key is None
        else supabase_key
    )
    if _valid_supabase(url, key):
        return SupabaseTechnologySpendRepository(client or supabase)
    if runtime == "production":
        raise TechnologySpendConfigurationError(
            "valid Supabase configuration is required for production technology spend"
        )
    kwargs = {"connection_factory": connection_factory} if connection_factory else {}
    return SQLiteTechnologySpendRepository(**kwargs)
