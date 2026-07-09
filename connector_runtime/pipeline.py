"""Connector execution pipeline."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping, Sequence

from connector_sdk import BaseConnector, ConnectorRecord, ConnectorRuntimeContext, ConnectorSyncState
from connector_runtime.exceptions import (
    ConnectorAuthenticationError,
    ConnectorDiscoveryError,
    ConnectorExtractionError,
    ConnectorPublishError,
    ConnectorValidationError,
)
from connector_runtime.hooks import ConnectorExecutionHooks
from connector_runtime.policy import ConnectorExecutionPolicy


class ConnectorExecutionPipeline:
    """Executes a connector through the standard Nexora lifecycle."""

    def __init__(self, hooks: ConnectorExecutionHooks | None = None) -> None:
        self.hooks = hooks or ConnectorExecutionHooks()

    def authenticate(self, connector: BaseConnector, context: ConnectorRuntimeContext, policy: ConnectorExecutionPolicy) -> bool:
        self.hooks.before_authenticate(context, policy)
        try:
            authenticated = connector.authenticate()
        except Exception as exc:  # pragma: no cover - defensive runtime envelope
            raise ConnectorAuthenticationError(str(exc)) from exc
        self.hooks.after_authenticate(context, policy, authenticated)
        if not authenticated:
            raise ConnectorAuthenticationError("Connector authentication failed.")
        return authenticated

    def discover(self, connector: BaseConnector) -> Mapping[str, Any]:
        try:
            return connector.discover()
        except Exception as exc:  # pragma: no cover
            raise ConnectorDiscoveryError(str(exc)) from exc

    def extract(self, connector: BaseConnector, context: ConnectorRuntimeContext, policy: ConnectorExecutionPolicy) -> Sequence[Mapping[str, Any]]:
        self.hooks.before_extract(context, policy)
        try:
            records = connector.extract(incremental=policy.incremental, checkpoint=policy.checkpoint)
        except Exception as exc:  # pragma: no cover
            raise ConnectorExtractionError(str(exc)) from exc
        self.hooks.after_extract(context, policy, len(records))
        return records

    def normalize(self, connector: BaseConnector, raw_records: Sequence[Mapping[str, Any]]) -> Sequence[ConnectorRecord]:
        return connector.normalize(raw_records)

    def validate(self, connector: BaseConnector, records: Sequence[ConnectorRecord]) -> tuple[bool, tuple[str, ...]]:
        try:
            is_valid, validation_errors = connector.validate(records)
        except Exception as exc:  # pragma: no cover
            raise ConnectorValidationError(str(exc)) from exc
        if not is_valid:
            raise ConnectorValidationError("; ".join(validation_errors) or "Connector validation failed.")
        return is_valid, validation_errors

    def publish(self, connector: BaseConnector, context: ConnectorRuntimeContext, policy: ConnectorExecutionPolicy, records: Sequence[ConnectorRecord]) -> int:
        if not policy.should_publish:
            return 0
        self.hooks.before_publish(context, policy, records)
        try:
            published_count = connector.publish(records)
        except Exception as exc:  # pragma: no cover
            raise ConnectorPublishError(str(exc)) from exc
        self.hooks.after_publish(context, policy, published_count)
        return published_count

    def run(self, connector: BaseConnector, context: ConnectorRuntimeContext, policy: ConnectorExecutionPolicy) -> dict[str, Any]:
        """Run lifecycle steps and return raw execution counters."""

        warnings: list[str] = []
        self.authenticate(connector, context, policy)
        discovery = self.discover(connector)
        if policy.discovery_only:
            return {
                "state": ConnectorSyncState.SUCCEEDED,
                "discovery": discovery,
                "records_extracted": 0,
                "records_normalized": 0,
                "records_published": 0,
                "warnings": tuple(warnings),
                "checkpoint": policy.checkpoint,
            }

        raw_records = self.extract(connector, context, policy)
        normalized = self.normalize(connector, raw_records)
        self.validate(connector, normalized)
        published_count = self.publish(connector, context, policy, normalized)

        state = ConnectorSyncState.SUCCEEDED
        if policy.should_publish and published_count != len(normalized):
            state = ConnectorSyncState.PARTIAL
            warnings.append("Published record count differs from normalized record count.")

        return {
            "state": state,
            "discovery": discovery,
            "records_extracted": len(raw_records),
            "records_normalized": len(normalized),
            "records_published": published_count,
            "warnings": tuple(warnings),
            "checkpoint": policy.checkpoint,
            "observed_at": datetime.now(timezone.utc),
        }
