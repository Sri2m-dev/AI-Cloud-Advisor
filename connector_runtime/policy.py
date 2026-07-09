"""Connector execution policies."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping


class ConnectorExecutionMode(str, Enum):
    """Supported connector execution modes."""

    FULL_SYNC = "full_sync"
    INCREMENTAL_SYNC = "incremental_sync"
    DISCOVERY_ONLY = "discovery_only"
    VALIDATE_ONLY = "validate_only"
    DRY_RUN = "dry_run"


@dataclass(frozen=True)
class ConnectorExecutionPolicy:
    """Execution policy used by the connector runtime engine."""

    mode: ConnectorExecutionMode = ConnectorExecutionMode.FULL_SYNC
    checkpoint: str | None = None
    publish_enabled: bool = True
    fail_fast: bool = True
    metadata: Mapping[str, Any] = field(default_factory=dict)

    @property
    def incremental(self) -> bool:
        return self.mode == ConnectorExecutionMode.INCREMENTAL_SYNC

    @property
    def discovery_only(self) -> bool:
        return self.mode == ConnectorExecutionMode.DISCOVERY_ONLY

    @property
    def validate_only(self) -> bool:
        return self.mode == ConnectorExecutionMode.VALIDATE_ONLY

    @property
    def dry_run(self) -> bool:
        return self.mode == ConnectorExecutionMode.DRY_RUN

    @property
    def should_publish(self) -> bool:
        return self.publish_enabled and not self.dry_run and not self.validate_only and not self.discovery_only
