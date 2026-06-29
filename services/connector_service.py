from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from core.connectors.base_connector import BaseConnector
from core.connectors.connector_config import ConnectorConfig
from core.connectors.connector_context import ConnectorContext
from core.connectors.connector_health import ConnectorHealth
from core.connectors.connector_registry import ConnectorRegistryEntry, ConnectorRegistryStatus
from core.connectors.connector_result import ConnectorResult, ConnectorRunStatus
from core.connectors.connector_scheduler import ConnectorSchedule
from repositories.connector_repository import ConnectorRepository
from repositories.entity_repository import EntityRepository
from repositories.metadata_catalog_repository import MetadataCatalogRepository
from services.correlation_service import CorrelationService
from services.entity_service import EntityService
from services.metadata_catalog_service import MetadataCatalogService


class ConnectorService:
    def __init__(
        self,
        repository: ConnectorRepository | None = None,
        entity_service: EntityService | None = None,
        metadata_service: MetadataCatalogService | None = None,
        correlation_service: CorrelationService | None = None,
    ):
        entity_repository = EntityRepository()
        self.repository = repository or ConnectorRepository()
        self.entity_service = entity_service or EntityService(entity_repository)
        self.metadata_service = metadata_service or MetadataCatalogService(MetadataCatalogRepository(), entity_repository)
        self.correlation_service = correlation_service or CorrelationService(entity_repository=entity_repository)

    def register_connector(
        self,
        config: ConnectorConfig,
        capabilities: list[str] | None = None,
        metadata: dict | None = None,
    ) -> ConnectorRegistryEntry:
        entry = ConnectorRegistryEntry(
            config=config,
            status=ConnectorRegistryStatus.REGISTERED.value if config.enabled else ConnectorRegistryStatus.DISABLED.value,
            capabilities=capabilities or list(BaseConnector.capabilities),
            metadata=metadata or {},
        )
        return self.repository.register(entry)

    def create_context(
        self,
        config: ConnectorConfig,
        actor_id: UUID | str | None = None,
        dry_run: bool = False,
        metadata: dict | None = None,
    ) -> ConnectorContext:
        return ConnectorContext(
            config=config,
            actor_id=UUID(str(actor_id)) if actor_id else None,
            dry_run=dry_run,
            services={
                "entity_service": self.entity_service,
                "metadata_service": self.metadata_service,
                "correlation_service": self.correlation_service,
            },
            metadata=metadata or {},
        )

    def run_discover(self, connector: BaseConnector) -> ConnectorResult:
        result = connector.discover()
        self.repository.save_result(result)
        entry = self._entry_for(connector.context.config)
        entry.last_discovered_at = self._now()
        entry.status = ConnectorRegistryStatus.ACTIVE.value if result.ok else ConnectorRegistryStatus.ERROR.value
        self.repository.register(entry)
        return result

    def sync_entities(self, connector: BaseConnector) -> ConnectorResult:
        result = connector.sync_entities()
        self.repository.save_result(result)
        entry = self._entry_for(connector.context.config)
        entry.last_synced_at = self._now()
        entry.status = ConnectorRegistryStatus.ACTIVE.value if result.ok else ConnectorRegistryStatus.ERROR.value
        self.repository.register(entry)
        return result

    def sync_relationships(self, connector: BaseConnector) -> ConnectorResult:
        result = connector.sync_relationships()
        self.repository.save_result(result)
        return result

    def sync_metadata(self, connector: BaseConnector) -> ConnectorResult:
        result = connector.sync_metadata()
        self.repository.save_result(result)
        return result

    def publish_health(self, connector: BaseConnector) -> ConnectorHealth:
        health = connector.health_check()
        self.repository.save_health(health)
        entry = self._entry_for(connector.context.config)
        entry.last_health_status = health.status
        self.repository.register(entry)
        return health

    def health_check(self, connector: BaseConnector) -> ConnectorHealth:
        return self.publish_health(connector)

    def schedule_connector(
        self,
        connector_id: UUID | str,
        operation: str,
        interval_minutes: int,
    ) -> ConnectorSchedule:
        return self.repository.save_schedule(
            ConnectorSchedule(
                connector_id=UUID(str(connector_id)),
                operation=operation,
                interval_minutes=interval_minutes,
            )
        )

    def run_lifecycle(self, connector: BaseConnector) -> list[ConnectorResult | ConnectorHealth]:
        outputs: list[ConnectorResult | ConnectorHealth] = []
        connect_result = connector.connect()
        self.repository.save_result(connect_result)
        if connect_result.status == ConnectorRunStatus.FAILED.value:
            return outputs + [connect_result]
        outputs.append(connect_result)
        outputs.append(self.run_discover(connector))
        outputs.append(self.sync_entities(connector))
        outputs.append(self.sync_relationships(connector))
        outputs.append(self.sync_metadata(connector))
        outputs.append(self.publish_health(connector))
        return outputs

    def _entry_for(self, config: ConnectorConfig) -> ConnectorRegistryEntry:
        return self.repository.get_connector(config.id) or self.register_connector(config)

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat(timespec="seconds")
