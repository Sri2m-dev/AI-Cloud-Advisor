"""Automatic runtime composition for the cloud account registry."""

from __future__ import annotations

from config.settings import SUPABASE_URL
from repositories.cloud_account_registry_repository import (
    CloudAccountRegistryRepository,
    LocalCloudAccountRegistryRepository,
)
from services.cloud_account_registry_service import CloudAccountRegistryService
from services.enterprise_spend_composition import enterprise_spend_service
from services.supabase_client import supabase


def cloud_account_registry_repository(*, supabase_url: str | None = None, client=None):
    configured_url = SUPABASE_URL if supabase_url is None else supabase_url
    if str(configured_url or "").strip():
        return CloudAccountRegistryRepository(client or supabase)
    return LocalCloudAccountRegistryRepository()


def cloud_account_registry_service() -> CloudAccountRegistryService:
    return CloudAccountRegistryService(
        cloud_account_registry_repository(), enterprise_spend_service()
    )
