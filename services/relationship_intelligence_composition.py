"""Automatic relationship intelligence composition over existing P3 stores."""

from __future__ import annotations

import os

from enterprise_registry.relationship_intelligence import RelationshipIntelligenceService
from repositories.relationship_intelligence_repository import (
    SQLiteRelationshipIntelligenceRepository,
    SupabaseRelationshipIntelligenceRepository,
)
from services.enterprise_registry_composition import enterprise_registry_service
from services.runtime_configuration import is_valid_supabase_configuration
from services.supabase_client import supabase


class RelationshipIntelligenceConfigurationError(RuntimeError):
    pass


def relationship_intelligence_service(
    context,
    *,
    role,
    environment=None,
    supabase_url=None,
    supabase_key=None,
    client=None,
    connection_factory=None,
):
    runtime = str(environment or os.getenv("ENVIRONMENT", "development")).strip().lower()
    url = os.getenv("SUPABASE_URL", "") if supabase_url is None else supabase_url
    key = (
        os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        or os.getenv("SUPABASE_SERVICE_KEY")
        or os.getenv("SUPABASE_KEY", "")
        if supabase_key is None
        else supabase_key
    )
    configured = is_valid_supabase_configuration(url, key)
    if runtime == "production" and not configured:
        raise RelationshipIntelligenceConfigurationError(
            "valid Supabase configuration is required for production relationship intelligence"
        )
    selected_client = client or supabase
    registry = enterprise_registry_service(
        context,
        role=role,
        environment=runtime,
        supabase_url=url,
        supabase_key=key,
        client=selected_client,
        connection_factory=connection_factory,
    )
    if configured:
        repository = SupabaseRelationshipIntelligenceRepository(selected_client)
    else:
        kwargs = {"connection_factory": connection_factory} if connection_factory else {}
        repository = SQLiteRelationshipIntelligenceRepository(**kwargs)
    return RelationshipIntelligenceService(
        context,
        role=role,
        entities=registry.list_entities(),
        relationships=repository.list_relationships(context),
    )
