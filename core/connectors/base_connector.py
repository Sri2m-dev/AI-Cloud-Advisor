from __future__ import annotations

from abc import ABC, abstractmethod

from core.connectors.connector_context import ConnectorContext
from core.connectors.connector_health import ConnectorHealth, ConnectorHealthStatus
from core.connectors.connector_result import ConnectorResult, ConnectorRunStatus
from core.entities.entity import EnterpriseEntity, EntityRelationship


class BaseConnector(ABC):
    capabilities = [
        "connect",
        "discover",
        "sync_entities",
        "sync_relationships",
        "sync_metadata",
        "health_check",
    ]

    def __init__(self, context: ConnectorContext):
        self.context = context

    @property
    def connector_id(self):
        return self.context.config.id

    @abstractmethod
    def connect(self) -> ConnectorResult:
        raise NotImplementedError

    @abstractmethod
    def discover(self) -> ConnectorResult:
        raise NotImplementedError

    def sync_entities(self) -> ConnectorResult:
        entities = self.fetch_entities()
        entity_service = self.context.service("entity_service")
        synced = 0
        if entity_service:
            for entity in entities:
                entity_service.save(entity)
                synced += 1
        return ConnectorResult(
            connector_id=self.connector_id,
            operation="sync_entities",
            status=ConnectorRunStatus.SUCCESS.value,
            entities_synced=synced,
            data={"discovered_entities": len(entities)},
        )

    def sync_relationships(self) -> ConnectorResult:
        relationships = self.fetch_relationships()
        entity_service = self.context.service("entity_service")
        synced = 0
        errors = []
        if entity_service:
            for relationship in relationships:
                try:
                    entity_service.add_relationship(
                        relationship.source_entity_id,
                        relationship.relationship_type,
                        relationship.target_entity_id,
                        confidence=relationship.confidence_score,
                        source_system=self.context.connector_name,
                        metadata=relationship.metadata,
                    )
                    synced += 1
                except Exception as exc:  # pragma: no cover - provider adapters decide retry strategy
                    errors.append(str(exc))
        return ConnectorResult(
            connector_id=self.connector_id,
            operation="sync_relationships",
            status=ConnectorRunStatus.PARTIAL.value if errors else ConnectorRunStatus.SUCCESS.value,
            relationships_synced=synced,
            errors=errors,
            data={"discovered_relationships": len(relationships)},
        )

    def sync_metadata(self) -> ConnectorResult:
        metadata_service = self.context.service("metadata_service")
        entity_service = self.context.service("entity_service")
        records = 0
        if metadata_service and entity_service:
            for entity in entity_service.repository.get_entities():
                if any(reference.system == self.context.config.provider for reference in entity.source_systems):
                    metadata_service.register_source_metadata(
                        entity.id,
                        self.context.config.provider,
                        entity.updated_at,
                        metadata={"connector_id": str(self.connector_id)},
                    )
                    records += 1
        return ConnectorResult(
            connector_id=self.connector_id,
            operation="sync_metadata",
            status=ConnectorRunStatus.SUCCESS.value,
            metadata_records=records,
        )

    def health_check(self) -> ConnectorHealth:
        return ConnectorHealth(
            connector_id=self.connector_id,
            status=ConnectorHealthStatus.HEALTHY.value,
            score=100.0,
            message=f"{self.context.connector_name} connector is reachable.",
        )

    def fetch_entities(self) -> list[EnterpriseEntity]:
        return []

    def fetch_relationships(self) -> list[EntityRelationship]:
        return []
