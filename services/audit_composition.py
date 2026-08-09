"""Automatic repository selection for central audit persistence."""

from __future__ import annotations

import os

from repositories.audit_repository import SQLiteAuditRepository, SupabaseAuditRepository
from services.runtime_configuration import is_valid_supabase_configuration
from services.supabase_client import supabase


class AuditConfigurationError(RuntimeError):
    """Raised when audit persistence cannot be safely composed."""


def audit_repository(
    *,
    environment: str | None = None,
    supabase_url: str | None = None,
    supabase_key: str | None = None,
    client=None,
    connection_factory=None,
):
    runtime_environment = (
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
    if is_valid_supabase_configuration(url, key):
        return SupabaseAuditRepository(client or supabase)
    if runtime_environment != "production":
        kwargs = {"connection_factory": connection_factory} if connection_factory else {}
        return SQLiteAuditRepository(**kwargs)
    raise AuditConfigurationError(
        "valid Supabase configuration is required for production audit persistence"
    )
