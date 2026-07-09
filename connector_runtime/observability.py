"""Optional connector runtime observability hooks."""

from __future__ import annotations

from collections import defaultdict
from typing import Sequence

from connector_observability.audit import AuditEventType, ConnectorAuditLog
from connector_observability.events import ConnectorEventName, ConnectorObservabilityEventStore
from connector_observability.metrics import ConnectorMetricsCollector
from connector_observability.telemetry import ConnectorTelemetry, TelemetryEventType
from connector_observability.tracing import ConnectorTracer
from connector_runtime.hooks import ConnectorExecutionHooks
from connector_runtime.policy import ConnectorExecutionPolicy
from connector_sdk import ConnectorRecord, ConnectorRuntimeContext, ConnectorSyncState


class ConnectorObservabilityHooks(ConnectorExecutionHooks):
    """Lifecycle hooks that emit metrics, telemetry, traces, events, and audit records.

    These hooks are optional. They keep observability outside provider-specific
    connectors and outside the core execution engine, while still using the
    standard lifecycle extension points introduced in E8.1.3.
    """

    def __init__(
        self,
        *,
        metrics: ConnectorMetricsCollector | None = None,
        telemetry: ConnectorTelemetry | None = None,
        tracer: ConnectorTracer | None = None,
        event_store: ConnectorObservabilityEventStore | None = None,
        audit_log: ConnectorAuditLog | None = None,
    ) -> None:
        self.metrics = metrics or ConnectorMetricsCollector()
        self.telemetry = telemetry or ConnectorTelemetry()
        self.tracer = tracer or ConnectorTracer()
        self.event_store = event_store or ConnectorObservabilityEventStore()
        self.audit_log = audit_log or ConnectorAuditLog()
        self._spans: dict[str, dict[str, str]] = defaultdict(dict)

    def before_authenticate(self, context: ConnectorRuntimeContext, policy: ConnectorExecutionPolicy) -> None:
        connector_id = self._connector_id(context)
        execution_id = context.run_id
        correlation_id = self._correlation_id(context)
        self.metrics.record_execution_started(connector_id)
        self.tracer.start_trace(connector_id, execution_id=execution_id, correlation_id=correlation_id, metadata={"mode": policy.mode.value})
        self._start_span(correlation_id, "Authentication")
        self.telemetry.emit_event(connector_id, TelemetryEventType.CONNECTOR_STARTED, execution_id=execution_id, correlation_id=correlation_id)
        self.event_store.record_event(connector_id, ConnectorEventName.STARTED, execution_id=execution_id, correlation_id=correlation_id)

    def after_authenticate(self, context: ConnectorRuntimeContext, policy: ConnectorExecutionPolicy, authenticated: bool) -> None:
        connector_id = self._connector_id(context)
        correlation_id = self._correlation_id(context)
        self._finish_span(correlation_id, "Authentication", status="succeeded" if authenticated else "failed")
        self.telemetry.emit_event(
            connector_id,
            TelemetryEventType.AUTHENTICATION_COMPLETED,
            execution_id=context.run_id,
            correlation_id=correlation_id,
            metadata={"authenticated": authenticated},
        )
        self.event_store.record_event(connector_id, ConnectorEventName.AUTHENTICATED, execution_id=context.run_id, correlation_id=correlation_id, payload={"authenticated": authenticated})
        if not authenticated:
            self.audit_log.record_event(
                connector_id,
                AuditEventType.AUTHENTICATION_FAILURE,
                execution_id=context.run_id,
                correlation_id=correlation_id,
                message="Connector authentication failed.",
            )

    def before_extract(self, context: ConnectorRuntimeContext, policy: ConnectorExecutionPolicy) -> None:
        self._start_span(self._correlation_id(context), "Extraction")

    def after_extract(self, context: ConnectorRuntimeContext, policy: ConnectorExecutionPolicy, raw_count: int) -> None:
        connector_id = self._connector_id(context)
        correlation_id = self._correlation_id(context)
        self._finish_span(correlation_id, "Extraction")
        self.telemetry.emit_event(
            connector_id,
            TelemetryEventType.EXTRACTION_COMPLETED,
            execution_id=context.run_id,
            correlation_id=correlation_id,
            metadata={"records_extracted": raw_count},
        )
        self.event_store.record_event(connector_id, ConnectorEventName.EXTRACTED, execution_id=context.run_id, correlation_id=correlation_id, payload={"records_extracted": raw_count})

    def before_publish(self, context: ConnectorRuntimeContext, policy: ConnectorExecutionPolicy, records: Sequence[ConnectorRecord]) -> None:
        self._start_span(self._correlation_id(context), "Publish", metadata={"records": len(records)})

    def after_publish(self, context: ConnectorRuntimeContext, policy: ConnectorExecutionPolicy, published_count: int) -> None:
        connector_id = self._connector_id(context)
        correlation_id = self._correlation_id(context)
        self._finish_span(correlation_id, "Publish")
        self.telemetry.emit_event(
            connector_id,
            TelemetryEventType.PUBLISH_COMPLETED,
            execution_id=context.run_id,
            correlation_id=correlation_id,
            metadata={"records_published": published_count},
        )
        self.event_store.record_event(connector_id, ConnectorEventName.PUBLISHED, execution_id=context.run_id, correlation_id=correlation_id, payload={"records_published": published_count})

    def on_success(self, context: ConnectorRuntimeContext, policy: ConnectorExecutionPolicy) -> None:
        connector_id = self._connector_id(context)
        correlation_id = self._correlation_id(context)
        self.metrics.record_execution_completed(connector_id, state=ConnectorSyncState.SUCCEEDED)
        self.tracer.finish_trace(correlation_id)
        self.telemetry.emit_event(connector_id, TelemetryEventType.CONNECTOR_SUCCEEDED, execution_id=context.run_id, correlation_id=correlation_id)
        self.event_store.record_event(connector_id, ConnectorEventName.SUCCEEDED, execution_id=context.run_id, correlation_id=correlation_id)
        self.audit_log.record_event(connector_id, AuditEventType.EXECUTION_SUCCEEDED, execution_id=context.run_id, correlation_id=correlation_id)

    def on_failure(self, context: ConnectorRuntimeContext, policy: ConnectorExecutionPolicy, error: Exception) -> None:
        connector_id = self._connector_id(context)
        correlation_id = self._correlation_id(context)
        self.metrics.record_execution_completed(connector_id, state=ConnectorSyncState.FAILED)
        self.tracer.finish_trace(correlation_id)
        self.telemetry.emit_event(
            connector_id,
            TelemetryEventType.CONNECTOR_FAILED,
            execution_id=context.run_id,
            correlation_id=correlation_id,
            message=str(error),
        )
        self.event_store.record_event(connector_id, ConnectorEventName.FAILED, execution_id=context.run_id, correlation_id=correlation_id, payload={"error": str(error)})
        self.audit_log.record_event(connector_id, AuditEventType.EXECUTION_FAILURE, execution_id=context.run_id, correlation_id=correlation_id, message=str(error))

    def _connector_id(self, context: ConnectorRuntimeContext) -> str:
        value = context.metadata.get("connector_id") if context.metadata else None
        return str(value or "unknown")

    def _correlation_id(self, context: ConnectorRuntimeContext) -> str:
        return context.correlation_id or context.run_id or "unknown"

    def _start_span(self, correlation_id: str, name: str, *, metadata: dict[str, object] | None = None) -> None:
        span = self.tracer.start_span(correlation_id, name, metadata=metadata or {})
        self._spans[correlation_id][name] = span.span_id

    def _finish_span(self, correlation_id: str, name: str, *, status: str = "succeeded") -> None:
        span_id = self._spans.get(correlation_id, {}).get(name)
        if span_id:
            self.tracer.finish_span(correlation_id, span_id, status=status)
