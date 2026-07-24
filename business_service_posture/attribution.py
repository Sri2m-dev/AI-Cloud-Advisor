"""Deterministic domain-input attribution to canonical Business Services."""

from __future__ import annotations

from data_fabric.contracts import EntityType, RelationshipType
from data_fabric.foundation import TenantContext
from data_fabric.registry import EntityNotFoundError, EntityRegistry, RelationshipRegistry
from enterprise_registry import (
    BusinessService,
    BusinessServiceNotFoundError,
    BusinessServiceRegistry,
)

SUPPORTED_ATTRIBUTION_RELATIONSHIPS = frozenset(
    {
        RelationshipType.DEPENDS_ON,
        RelationshipType.RUNS_ON,
        RelationshipType.ASSOCIATED_WITH,
    }
)


class PostureAttributionError(ValueError):
    """Base error for deterministic Business Service attribution."""


class MissingPostureAttributionError(PostureAttributionError):
    """Raised when no supported Business Service path exists."""


class AmbiguousPostureAttributionError(PostureAttributionError):
    """Raised when an input resolves to multiple Business Services."""


class UnsupportedPostureAttributionError(PostureAttributionError):
    """Raised when only unsupported relationship paths are present."""


class BusinessServiceAttributionResolver:
    """Resolve Technology-owned domain inputs through canonical relationships."""

    def __init__(
        self,
        context: TenantContext,
        *,
        services: BusinessServiceRegistry,
        entities: EntityRegistry,
        relationships: RelationshipRegistry,
    ) -> None:
        context.assert_matches(services.context, "business service registry")
        self.context = context
        self.services = services
        self.entities = entities
        self.relationships = relationships

    def resolve_technology(self, technology_id: str) -> BusinessService:
        technology = self._resolve_entity(technology_id)
        if technology.entity_type is not EntityType.TECHNOLOGY:
            raise PostureAttributionError(
                "domain input identity is not a canonical Technology"
            )
        target_ids = {technology.id, technology.canonical_id}
        relationships = self.relationships.search_relationships(
            organization_id=self.context.organization_id,
            include_inactive=False,
        )
        matching = [
            item for item in relationships if item.target_entity_id in target_ids
        ]
        supported = []
        unsupported = []
        for item in matching:
            self.context.assert_record_matches(item, "attribution relationship")
            if item.relationship_type in SUPPORTED_ATTRIBUTION_RELATIONSHIPS:
                supported.append(item)
            else:
                unsupported.append(item)
        if not supported:
            if unsupported:
                raise UnsupportedPostureAttributionError(
                    "no supported Business Service relationship path"
                )
            raise MissingPostureAttributionError(
                "domain input has no Business Service attribution"
            )

        services: dict[str, BusinessService] = {}
        for item in supported:
            try:
                service = self.services.get_by_canonical_id(
                    item.source_entity_id,
                    include_inactive=True,
                )
            except BusinessServiceNotFoundError as exc:
                raise PostureAttributionError(
                    "attribution source is not a canonical Business Service"
                ) from exc
            self.context.assert_record_matches(service, "attributed business service")
            services[service.canonical_id] = service
        if len(services) > 1:
            raise AmbiguousPostureAttributionError(
                "domain input resolves to multiple Business Services"
            )
        return next(iter(services.values()))

    def _resolve_entity(self, identifier: str):
        try:
            entity = self.entities.get_entity(identifier)
        except EntityNotFoundError:
            entity = self.entities.find_entity_by_canonical_id(identifier)
            if entity is None:
                raise MissingPostureAttributionError(
                    "domain input Technology identity is not registered"
                ) from None
        self.context.assert_record_matches(entity, "domain input Technology")
        return entity
