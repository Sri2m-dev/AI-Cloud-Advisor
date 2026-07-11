"""Configuration contract for the Supabase Data Fabric adapter."""

from __future__ import annotations

from dataclasses import dataclass

from data_fabric.adapters.supabase.exceptions import SupabaseAdapterConfigurationError


@dataclass(frozen=True, slots=True)
class DataFabricDatabaseConfig:
    """Server-side configuration for the Supabase PostgreSQL Data Fabric adapter."""

    supabase_url: str
    service_role_key: str
    schema_name: str = "data_fabric"
    request_timeout_seconds: float = 10.0
    max_retries: int = 2
    retry_backoff_seconds: float = 0.1
    enable_health_check: bool = True

    def __post_init__(self) -> None:
        if not self.supabase_url or not self.supabase_url.startswith(("http://", "https://")):
            raise SupabaseAdapterConfigurationError("supabase_url must be an http(s) URL")
        if not self.service_role_key:
            raise SupabaseAdapterConfigurationError("service_role_key is required for server-side adapter use")
        if self.service_role_key.lower() in {"replace-me", "changeme", "your-service-role-key"}:
            raise SupabaseAdapterConfigurationError("service_role_key cannot be a placeholder")
        if not self.schema_name or not self.schema_name.replace("_", "").isalnum():
            raise SupabaseAdapterConfigurationError("schema_name must be alphanumeric or underscore")
        if self.request_timeout_seconds <= 0:
            raise SupabaseAdapterConfigurationError("request_timeout_seconds must be positive")
        if self.max_retries < 0:
            raise SupabaseAdapterConfigurationError("max_retries cannot be negative")
        if self.retry_backoff_seconds < 0:
            raise SupabaseAdapterConfigurationError("retry_backoff_seconds cannot be negative")

    def __repr__(self) -> str:
        return (
            "DataFabricDatabaseConfig("
            f"supabase_url={self.supabase_url!r}, "
            "service_role_key='***REDACTED***', "
            f"schema_name={self.schema_name!r}, "
            f"request_timeout_seconds={self.request_timeout_seconds!r}, "
            f"max_retries={self.max_retries!r}, "
            f"retry_backoff_seconds={self.retry_backoff_seconds!r}, "
            f"enable_health_check={self.enable_health_check!r})"
        )
