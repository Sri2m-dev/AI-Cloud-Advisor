"""Runtime composition for the read-only canonical Enterprise Registry projection."""

from __future__ import annotations

import os
from urllib.parse import urlparse

from classification_engine.repository import SupabaseClassificationRepository
from data_fabric.foundation import TenantContext
from data_fabric.identity import InMemoryIdentityResolver
from data_fabric.registry import InMemoryEntityRegistry, InMemoryRelationshipRegistry
from data_fabric.versioning import InMemoryVersionStore
from enterprise_registry.canonical_service import EnterpriseRegistryService
from repositories.enterprise_registry_source import (
    CanonicalDataFabricRegistrySource,
    SQLiteEnterpriseRegistrySource,
    SupabaseEnterpriseRegistrySource,
    SupabaseEntityFinancialContext,
)
from services.demo_enterprise_topology import demo_enterprise_topology
from services.runtime_configuration import is_valid_supabase_configuration
from services.supabase_client import supabase


class EnterpriseRegistryConfigurationError(RuntimeError):
    pass


def _source_identity_key(entity):
    source_system = entity.source_system.strip().casefold()
    for suffix in (" connector", "_connector", ".live_cost"):
        if source_system.endswith(suffix):
            source_system = source_system[: -len(suffix)]
            break
    return source_system, entity.source_identifier.strip().casefold()


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
    canonical_source=None,
):
    if not isinstance(context, TenantContext):
        raise PermissionError("Explicit tenant context is required for Enterprise Registry.")
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
        service_role_key = (
            os.getenv("SUPABASE_SERVICE_ROLE_KEY")
            or os.getenv("SUPABASE_SERVICE_KEY")
            or ""
        ).strip()
        if canonical_source is None and service_role_key:
            canonical_source = CanonicalDataFabricRegistrySource.from_supabase(
                url,
                service_role_key,
            )
        if runtime == "production" and canonical_source is None:
            raise EnterpriseRegistryConfigurationError(
                "server-side Data Fabric reader credentials are required in production"
            )
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
    demo_entities, _ = demo_enterprise_topology(context)

    canonical_entities = canonical_source.entities(context) if canonical_source else ()
    compatibility_entities = source.entities(context)
    canonical_relationships = canonical_source.relationships(context) if canonical_source else ()

    seen_canonical_ids = set()
    seen_source_identities = set()
    for entity in (*canonical_entities, *compatibility_entities, *demo_entities):
        context.assert_record_matches(entity, "enterprise registry source entity")
        source_identity = _source_identity_key(entity)
        if (
            entity.canonical_id in seen_canonical_ids
            or source_identity in seen_source_identities
        ):
            continue
        seen_canonical_ids.add(entity.canonical_id)
        seen_source_identities.add(source_identity)
        registered = entities.register_entity(entity)
        identities.register_entity(registered)
        versions.create_entity_snapshot(
            registered,
            lineage_ref=registered.lineage_reference,
            provenance_ref=registered.provenance_reference,
        )
    seen_relationships = set()
    for relationship in canonical_relationships:
        context.assert_record_matches(relationship, "canonical relationship source")
        identity = (
            relationship.source_entity_id,
            relationship.relationship_type.value,
            relationship.target_entity_id,
        )
        if relationship.id in seen_relationships or identity in seen_relationships:
            continue
        seen_relationships.add(relationship.id)
        seen_relationships.add(identity)
        relationships.register_relationship(relationship)
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
