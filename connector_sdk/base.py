"""Base connector lifecycle contract for Nexora integrations."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence

from connector_sdk.models import (
    ConnectorAuthConfig,
    ConnectorHealthStatus,
    ConnectorMetadata,
    ConnectorRecord,
    ConnectorSyncResult,
    ConnectorSyncState,
)


class BaseConnector(ABC):
    """Base class for all enterprise connectors.

    Concrete connectors should implement the lifecycle in this order:

    authenticate -> discover -> extract -> normalize -> validate -> publish

    sync_full and sync_incremental provide standard orchestration hooks while
    allowing provider-specific implementations to override behavior where
    needed.
    """

    metadata: ConnectorMetadata

    def __init__(self, auth_config: ConnectorAuthConfig | None = None) -> None:
        self.auth_config = auth_config

    @abstractmethod
    def authenticate(self) -> bool:
        """Authenticate against the source system."""

    @abstractmethod
    def discover(self) -> Mapping[str, Any]:
        """Discover source accounts, scopes, entities, or capabilities."""

    @abstractmethod
    def extract(self, *, incremental: bool = False, checkpoint: str | None = None) -> Sequence[Mapping[str, Any]]:
        """Extract raw records from the source system."""

    @abstractmethod
    def normalize(self, records: Sequence[Mapping[str, Any]]) -> Sequence[ConnectorRecord]:
        """Normalize raw records into Nexora connector envelopes."""

    @abstractmethod
    def validate(self, records: Sequence[ConnectorRecord]) -> tuple[bool, tuple[str, ...]]:
        """Validate normalized records before publishing."""

    @abstractmethod
    def publish(self, records: Sequence[ConnectorRecord]) -> int:
        """Publish normalized records to the canonical ingestion target."""

    def health(self) -> ConnectorHealthStatus:
        """Return a default health status for the connector."""

        return ConnectorHealthStatus(
            connector_id=self.metadata.connector_id,
            status="unknown",
            message="Connector health has not been implemented.",
        )

    def sync_full(self) -> ConnectorSyncResult:
        """Run a standard full sync lifecycle."""

        return self._sync(incremental=False, checkpoint=None)

    def sync_incremental(self, checkpoint: str | None = None) -> ConnectorSyncResult:
        """Run a standard incremental sync lifecycle."""

        if not self.metadata.supports_incremental_sync:
            return ConnectorSyncResult.skipped(
                self.metadata.connector_id,
                "Connector does not support incremental sync.",
            )
        return self._sync(incremental=True, checkpoint=checkpoint)

    def _sync(self, *, incremental: bool, checkpoint: str | None) -> ConnectorSyncResult:
        started_at = datetime.now(timezone.utc)
        errors: list[str] = []
        warnings: list[str] = []
        extracted_count = 0
        normalized_count = 0
        published_count = 0
        state = ConnectorSyncState.SUCCEEDED

        try:
            if not self.authenticate():
                raise RuntimeError("Connector authentication failed.")

            raw_records = self.extract(incremental=incremental, checkpoint=checkpoint)
            extracted_count = len(raw_records)

            normalized = self.normalize(raw_records)
            normalized_count = len(normalized)

            is_valid, validation_errors = self.validate(normalized)
            if not is_valid:
                errors.extend(validation_errors)
                state = ConnectorSyncState.FAILED
            else:
                published_count = self.publish(normalized)
                if published_count != normalized_count:
                    warnings.append("Published record count differs from normalized record count.")
                    state = ConnectorSyncState.PARTIAL
        except Exception as exc:  # pragma: no cover - safety envelope for connector implementations
            errors.append(str(exc))
            state = ConnectorSyncState.FAILED

        finished_at = datetime.now(timezone.utc)
        return ConnectorSyncResult(
            connector_id=self.metadata.connector_id,
            state=state,
            started_at=started_at,
            finished_at=finished_at,
            records_extracted=extracted_count,
            records_normalized=normalized_count,
            records_published=published_count,
            errors=tuple(errors),
            warnings=tuple(warnings),
            checkpoint=checkpoint,
        )
