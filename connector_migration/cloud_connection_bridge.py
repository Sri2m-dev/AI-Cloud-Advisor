"""Bridge legacy cloud_connections rows to connector_registry payloads."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping, Protocol

from connector_migration.auth_config_mapper import AuthConfigMapper
from connector_migration.registry_mapper import ConnectorRegistryMapper
from connector_sdk import ConnectorAuthConfig


class CloudConnectionSource(Protocol):
    """Minimal source protocol for reading legacy cloud connection rows."""

    def list_cloud_connections(self) -> list[Mapping[str, Any]]:
        """Return legacy cloud connection rows."""


@dataclass(frozen=True)
class CloudConnectionBridgeResult:
    """Result of mapping legacy cloud connections into registry payloads."""

    registry_payloads: tuple[dict[str, Any], ...] = field(default_factory=tuple)
    auth_configs: tuple[ConnectorAuthConfig, ...] = field(default_factory=tuple)
    skipped: tuple[Mapping[str, Any], ...] = field(default_factory=tuple)

    @property
    def migrated_count(self) -> int:
        return len(self.registry_payloads)


class CloudConnectionBridge:
    """Bridge layer between legacy cloud_connections and connector_registry.

    The bridge is intentionally persistence-agnostic. Callers can provide rows
    directly or a source that implements list_cloud_connections(). This keeps
    E8.1.11 migration logic safe and testable without changing existing pages or
    production connector services.
    """

    def __init__(self, source: CloudConnectionSource | None = None) -> None:
        self.source = source
        self.registry_mapper = ConnectorRegistryMapper()
        self.auth_mapper = AuthConfigMapper()

    def read_legacy_connections(self) -> list[Mapping[str, Any]]:
        if self.source is None:
            return []
        return self.source.list_cloud_connections()

    def bridge(
        self,
        records: Iterable[Mapping[str, Any]] | None = None,
        *,
        organization_id: str | None = None,
        configured_by: str | None = None,
    ) -> CloudConnectionBridgeResult:
        records = list(records if records is not None else self.read_legacy_connections())
        registry_payloads: list[dict[str, Any]] = []
        auth_configs: list[ConnectorAuthConfig] = []
        skipped: list[Mapping[str, Any]] = []

        for record in records:
            provider = str(record.get("provider") or record.get("cloud_provider") or record.get("cloud") or "").upper()
            if provider not in {"AWS", "AZURE", "GCP"}:
                skipped.append(record)
                continue
            registry_payloads.append(
                self.registry_mapper.from_cloud_connection(record, organization_id=organization_id, configured_by=configured_by)
            )
            auth_configs.append(self.auth_mapper.from_cloud_connection(record))

        return CloudConnectionBridgeResult(
            registry_payloads=tuple(registry_payloads),
            auth_configs=tuple(auth_configs),
            skipped=tuple(skipped),
        )

    def registry_payload_for(self, record: Mapping[str, Any], *, organization_id: str | None = None, configured_by: str | None = None) -> dict[str, Any]:
        return self.registry_mapper.from_cloud_connection(record, organization_id=organization_id, configured_by=configured_by)

    def auth_config_for(self, record: Mapping[str, Any]) -> ConnectorAuthConfig:
        return self.auth_mapper.from_cloud_connection(record)
