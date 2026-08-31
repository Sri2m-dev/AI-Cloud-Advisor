"""Durable audit and non-authoritative telemetry for governed workflows."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from typing import Iterable

from universal_evidence.operations.models import (
    FailureClass,
    GovernedEvent,
    GovernedEventType,
    OperationContext,
    ReasonCode,
    Severity,
    new_event,
)
from universal_evidence.persistence import LifecyclePersistenceError, LifecycleScope

REQUIRED_DURABLE_AUDIT_EVENTS = frozenset(
    {
        GovernedEventType.MAPPING_OVERRIDDEN,
        GovernedEventType.MAPPING_CONFIRMED,
        GovernedEventType.MAPPING_REJECTED,
        GovernedEventType.MATCH_CONFIRMED,
        GovernedEventType.MATCH_REJECTED,
        GovernedEventType.EXECUTION_AUTHORIZED,
        GovernedEventType.PURGE_REQUESTED,
        GovernedEventType.PURGE_COMPLETED,
        GovernedEventType.KILL_SWITCH_ENABLED,
        GovernedEventType.KILL_SWITCH_DISABLED,
        GovernedEventType.ACTIVATION_CHANGED,
        GovernedEventType.SCOPE_ACCESS_REJECTED,
        GovernedEventType.UNAUTHORIZED_ACTION,
    }
)

AUDIT_ROLES = frozenset({"super_admin", "client_admin", "operations", "auditor"})


@dataclass(frozen=True, slots=True)
class OperationsRetentionPolicy:
    """Deployment-enforced retention contract; no destructive scheduler is installed."""

    audit_days: int = 2555
    telemetry_max_events: int = 1000

    def __post_init__(self):
        if self.audit_days < 1 or self.telemetry_max_events < 1:
            raise ValueError("retention values must be positive")


@dataclass(frozen=True, slots=True)
class SafeOperationalError:
    category: str
    message: str
    reference: str | None = None


def present_operational_error(failure_class, correlation_id):
    """Map an internal classification to bounded client-safe presentation."""
    from universal_evidence.operations.models import support_id

    failure_class = FailureClass(failure_class)
    if failure_class in {FailureClass.EXPECTED_BLOCK, FailureClass.USER_GOVERNANCE_REQUIRED}:
        return SafeOperationalError("GOVERNANCE", "A governed prerequisite requires attention.")
    if failure_class is FailureClass.SECURITY_REJECTION:
        return SafeOperationalError("PERMISSION", "You do not have permission for this action.")
    if failure_class in {
        FailureClass.DEPENDENCY_FAILURE,
        FailureClass.PERSISTENCE_FAILURE,
        FailureClass.MIGRATION_FAILURE,
    }:
        return SafeOperationalError(
            "UNAVAILABLE",
            "The governed workflow is temporarily unavailable.",
            support_id(correlation_id),
        )
    return SafeOperationalError(
        "INTERNAL", "Nexora could not complete this request.", support_id(correlation_id)
    )


class InMemoryOperationalTelemetry:
    """Bounded telemetry suitable for future export; never audit authority."""

    def __init__(self, *, max_events: int = 1000):
        self.max_events = max(1, int(max_events))
        self.events: list[GovernedEvent] = []
        self.counters: Counter[tuple[str, tuple[str, str, str | None, str | None]]] = Counter()

    def record(self, event: GovernedEvent) -> None:
        self.events.append(event)
        del self.events[:-self.max_events]
        scope = event.context
        self.counters[
            (
                event.event_type.value,
                (scope.organization_id, scope.tenant_id, scope.prospect_id, scope.analysis_id),
            )
        ] += 1

    def count(self, event_type, context: OperationContext) -> int:
        key = (
            GovernedEventType(event_type).value,
            (
                context.organization_id,
                context.tenant_id,
                context.prospect_id,
                context.analysis_id,
            ),
        )
        return self.counters[key]


@dataclass(frozen=True, slots=True)
class AuditQuery:
    context: OperationContext
    requester_role: str
    event_type: GovernedEventType | None = None
    actor_id: str | None = None
    evidence_reference: str | None = None
    correlation_id: str | None = None
    start: datetime | None = None
    end: datetime | None = None
    limit: int = 100


class GovernedOperationsService:
    def __init__(self, lifecycle, *, telemetry=None, clock=None):
        self.lifecycle = lifecycle
        self.telemetry = telemetry or InMemoryOperationalTelemetry()
        self.clock = clock

    def emit(
        self,
        event_type,
        context,
        *,
        audit: bool | None = None,
        severity=Severity.INFO,
        outcome="SUCCESS",
        failure_class=None,
        reason_code=None,
        duration_ms=None,
        references=None,
        attributes=None,
    ) -> GovernedEvent:
        event_type = GovernedEventType(event_type)
        event = new_event(
            event_type,
            context,
            severity=Severity(severity),
            outcome=outcome,
            failure_class=FailureClass(failure_class) if failure_class else None,
            reason_code=ReasonCode(reason_code) if reason_code else None,
            duration_ms=duration_ms,
            references=references,
            attributes=attributes,
            clock=self.clock,
        )
        requires_audit = event_type in REQUIRED_DURABLE_AUDIT_EVENTS
        should_audit = requires_audit if audit is None else bool(audit)
        if should_audit:
            try:
                self.lifecycle.put(
                    "governed_operation_event",
                    event.event_id,
                    _scope(context),
                    payload=event.payload(),
                    fingerprint_value=event.event_id,
                    actor_id=context.actor_id or "SYSTEM",
                    reason=event_type.value,
                )
            except Exception as exc:
                if requires_audit:
                    raise LifecyclePersistenceError(
                        "required durable audit write failed"
                    ) from exc
        try:
            self.telemetry.record(event)
        except Exception:
            # Operational export is deliberately non-authoritative. Domain reads and
            # successful durable mutations must not depend on a metrics sink.
            pass
        return event

    def query(self, query: AuditQuery) -> tuple[GovernedEvent, ...]:
        if query.requester_role not in AUDIT_ROLES:
            raise PermissionError("governed audit query denied")
        rows = self.lifecycle.list_scope(_scope(query.context), include_purged=True)
        events = tuple(
            _event_from_payload(row.payload)
            for row in rows
            if row.object_type == "governed_operation_event" and row.payload
        )
        filtered: Iterable[GovernedEvent] = events
        if query.event_type:
            filtered = (item for item in filtered if item.event_type is query.event_type)
        if query.actor_id:
            filtered = (item for item in filtered if item.context.actor_id == query.actor_id)
        if query.evidence_reference:
            filtered = (
                item
                for item in filtered
                if item.references.get("evidence") == query.evidence_reference
            )
        if query.correlation_id:
            filtered = (
                item
                for item in filtered
                if item.context.correlation_id == query.correlation_id
            )
        if query.start:
            filtered = (item for item in filtered if item.timestamp >= query.start)
        if query.end:
            filtered = (item for item in filtered if item.timestamp <= query.end)
        return tuple(sorted(filtered, key=lambda item: item.timestamp, reverse=True))[
            : max(0, min(int(query.limit), 1000))
        ]

    def query_authorized(self, authorization, **filters) -> tuple[GovernedEvent, ...]:
        """Query only the complete lifecycle scope carried by trusted authority."""
        from universal_evidence.operations.models import OperationContext

        context = OperationContext(
            authorization.tenant.organization_id,
            authorization.tenant.tenant_id,
            authorization.prospect_id,
            authorization.analysis_id,
            authorization.actor_id,
            authorization.role,
            authorization.tenant.correlation_id or "NX-COR-AUTHORIZED-AUDIT",
        )
        return self.query(AuditQuery(context, authorization.role, **filters))


def _scope(context):
    return LifecycleScope(
        context.organization_id,
        context.tenant_id,
        context.prospect_id,
        context.analysis_id,
    )


def _event_from_payload(payload):
    context = OperationContext(
        payload["organization_id"],
        payload["tenant_id"],
        payload.get("prospect_id"),
        payload.get("analysis_id"),
        payload.get("actor_id"),
        payload.get("actor_role"),
        payload["correlation_id"],
        payload.get("mode", "PRODUCTION"),
    )
    return GovernedEvent(
        payload["event_id"],
        GovernedEventType(payload["event_type"]),
        datetime.fromisoformat(payload["timestamp"]),
        Severity(payload["severity"]),
        context,
        payload["outcome"],
        FailureClass(payload["failure_class"]) if payload.get("failure_class") else None,
        ReasonCode(payload["reason_code"]) if payload.get("reason_code") else None,
        payload.get("duration_ms"),
        payload.get("references") or {},
        payload.get("attributes") or {},
    )
