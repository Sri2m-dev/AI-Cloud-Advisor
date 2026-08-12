"""Runtime composition for the read-only canonical Enterprise Registry projection."""

from __future__ import annotations

import os
from urllib.parse import urlparse

from classification_engine.repository import SupabaseClassificationRepository
from data_fabric.identity import InMemoryIdentityResolver
from data_fabric.registry import InMemoryEntityRegistry, InMemoryRelationshipRegistry
from data_fabric.versioning import InMemoryVersionStore
from enterprise_registry.canonical_service import EnterpriseRegistryService
from repositories.enterprise_registry_source import (
    SQLiteEnterpriseRegistrySource,
    SupabaseEnterpriseRegistrySource,
    SupabaseEntityFinancialContext,
)
from services.runtime_configuration import is_valid_supabase_configuration
from services.supabase_client import supabase


class EnterpriseRegistryConfigurationError(RuntimeError):
    pass


def _valid_supabase(url, key) -> bool:
    if not is_valid_supabase_configuration(url, key):
        return False
    hostname = (urlparse(str(url).strip()).hostname or "").casefold()
    return hostname == "supabase.co" or hostname.endswith(".supabase.co")


def enterprise_registry_service(
    context,
    *,
    role: str,
    environment=None,
    supabase_url=None,
    supabase_key=None,
    client=None,
    connection_factory=None,
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
    configured = _valid_supabase(url, key)
    if runtime == "production" and not configured:
        raise EnterpriseRegistryConfigurationError(
            "valid Supabase configuration is required for production enterprise registry"
        )
    selected_client = client or supabase
    if configured:
        source = SupabaseEnterpriseRegistrySource(selected_client)
        source_mode = "supabase"
        classifications = SupabaseClassificationRepository(selected_client)
        financial = SupabaseEntityFinancialContext(selected_client)
    else:
        kwargs = {"connection_factory": connection_factory} if connection_factory else {}
        source = SQLiteEnterpriseRegistrySource(**kwargs)
        source_mode = "sqlite"
        classifications = None
        financial = None

    entities = InMemoryEntityRegistry()
    identities = InMemoryIdentityResolver()
    relationships = InMemoryRelationshipRegistry()
    versions = InMemoryVersionStore()
    seen = set()
    for entity in source.entities(context):
        if entity.canonical_id in seen:
            continue
        seen.add(entity.canonical_id)
        registered = entities.register_entity(entity)
        identities.register_entity(registered)
        versions.create_entity_snapshot(
            registered,
            lineage_ref=registered.lineage_reference,
            provenance_ref=registered.provenance_reference,
        )
    return EnterpriseRegistryService(
        context,
        role=role,
        entities=entities,
        identities=identities,
        relationships=relationships,
        classifications=classifications,
        financial=financial,
        versions=versions,
        source_mode=source_mode,
    )
