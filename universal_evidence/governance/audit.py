"""Isolated in-memory audit sink; stores no evidence samples."""

from universal_evidence.governance.models import AuditEvent


class InMemoryAuditSink:
    def __init__(self) -> None:
        self._events: list[AuditEvent] = []

    def emit(self, event: AuditEvent) -> AuditEvent:
        self._events.append(event)
        return event

    def events(self) -> tuple[AuditEvent, ...]:
        return tuple(self._events)
