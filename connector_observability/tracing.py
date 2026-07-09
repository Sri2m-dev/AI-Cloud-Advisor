"""Connector tracing contracts."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Mapping
from uuid import uuid4


@dataclass(frozen=True)
class TraceSpan:
    """A single connector lifecycle span."""

    span_id: str
    name: str
    started_at: datetime
    finished_at: datetime | None = None
    status: str = "running"
    metadata: Mapping[str, Any] = field(default_factory=dict)

    @property
    def duration_ms(self) -> int | None:
        if self.finished_at is None:
            return None
        return int((self.finished_at - self.started_at).total_seconds() * 1000)


@dataclass(frozen=True)
class ConnectorTrace:
    """Correlation envelope for a connector execution."""

    correlation_id: str
    connector_id: str
    execution_id: str | None = None
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    finished_at: datetime | None = None
    spans: tuple[TraceSpan, ...] = field(default_factory=tuple)
    metadata: Mapping[str, Any] = field(default_factory=dict)

    @property
    def duration_ms(self) -> int | None:
        if self.finished_at is None:
            return None
        return int((self.finished_at - self.started_at).total_seconds() * 1000)


class ConnectorTracer:
    """In-memory trace collector with correlation ID support."""

    def __init__(self) -> None:
        self._traces: dict[str, ConnectorTrace] = {}
        self._open_spans: dict[str, list[TraceSpan]] = {}

    def start_trace(
        self,
        connector_id: str,
        *,
        execution_id: str | None = None,
        correlation_id: str | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> ConnectorTrace:
        correlation_id = correlation_id or str(uuid4())
        trace = ConnectorTrace(
            correlation_id=correlation_id,
            connector_id=connector_id,
            execution_id=execution_id,
            metadata=metadata or {},
        )
        self._traces[correlation_id] = trace
        self._open_spans[correlation_id] = []
        return trace

    def start_span(self, correlation_id: str, name: str, *, metadata: Mapping[str, Any] | None = None) -> TraceSpan:
        span = TraceSpan(span_id=str(uuid4()), name=name, started_at=datetime.now(timezone.utc), metadata=metadata or {})
        self._open_spans.setdefault(correlation_id, []).append(span)
        self._persist_spans(correlation_id)
        return span

    def finish_span(self, correlation_id: str, span_id: str, *, status: str = "succeeded") -> TraceSpan | None:
        spans = self._open_spans.get(correlation_id, [])
        for index, span in enumerate(spans):
            if span.span_id == span_id:
                finished = TraceSpan(
                    span_id=span.span_id,
                    name=span.name,
                    started_at=span.started_at,
                    finished_at=datetime.now(timezone.utc),
                    status=status,
                    metadata=span.metadata,
                )
                spans[index] = finished
                self._persist_spans(correlation_id)
                return finished
        return None

    def finish_trace(self, correlation_id: str) -> ConnectorTrace | None:
        trace = self._traces.get(correlation_id)
        if trace is None:
            return None
        finished = ConnectorTrace(
            correlation_id=trace.correlation_id,
            connector_id=trace.connector_id,
            execution_id=trace.execution_id,
            started_at=trace.started_at,
            finished_at=datetime.now(timezone.utc),
            spans=trace.spans,
            metadata=trace.metadata,
        )
        self._traces[correlation_id] = finished
        return finished

    def get_trace(self, correlation_id: str) -> ConnectorTrace | None:
        return self._traces.get(correlation_id)

    def list_traces(self, connector_id: str | None = None) -> list[ConnectorTrace]:
        traces = list(self._traces.values())
        if connector_id is not None:
            traces = [trace for trace in traces if trace.connector_id == connector_id]
        return traces

    def clear(self) -> None:
        self._traces.clear()
        self._open_spans.clear()

    def _persist_spans(self, correlation_id: str) -> None:
        trace = self._traces.get(correlation_id)
        if trace is None:
            return
        self._traces[correlation_id] = ConnectorTrace(
            correlation_id=trace.correlation_id,
            connector_id=trace.connector_id,
            execution_id=trace.execution_id,
            started_at=trace.started_at,
            finished_at=trace.finished_at,
            spans=tuple(self._open_spans.get(correlation_id, ())),
            metadata=trace.metadata,
        )


tracer = ConnectorTracer()
