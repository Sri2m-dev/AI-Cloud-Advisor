"""Connector execution lifecycle hooks."""

from __future__ import annotations

from typing import Sequence

from connector_sdk import ConnectorRecord, ConnectorRuntimeContext
from connector_runtime.policy import ConnectorExecutionPolicy


class ConnectorExecutionHooks:
    """No-op lifecycle hooks for metrics, tracing, audit, and governance."""

    def before_authenticate(self, context: ConnectorRuntimeContext, policy: ConnectorExecutionPolicy) -> None:
        pass

    def after_authenticate(self, context: ConnectorRuntimeContext, policy: ConnectorExecutionPolicy, authenticated: bool) -> None:
        pass

    def before_extract(self, context: ConnectorRuntimeContext, policy: ConnectorExecutionPolicy) -> None:
        pass

    def after_extract(self, context: ConnectorRuntimeContext, policy: ConnectorExecutionPolicy, raw_count: int) -> None:
        pass

    def before_publish(self, context: ConnectorRuntimeContext, policy: ConnectorExecutionPolicy, records: Sequence[ConnectorRecord]) -> None:
        pass

    def after_publish(self, context: ConnectorRuntimeContext, policy: ConnectorExecutionPolicy, published_count: int) -> None:
        pass

    def on_success(self, context: ConnectorRuntimeContext, policy: ConnectorExecutionPolicy) -> None:
        pass

    def on_failure(self, context: ConnectorRuntimeContext, policy: ConnectorExecutionPolicy, error: Exception) -> None:
        pass
