"""Process-local activation audit sink and event vocabulary."""

from universal_evidence.activation.fingerprint import fingerprint
from universal_evidence.activation.models import ActivationAuditEvent

AUDIT_EVENT_TYPES = (
    "PUE_ACTIVATION_CHANGED",
    "PUE_KILL_SWITCH_CHANGED",
    "PUE_ROUTE_SELECTED",
    "PUE_ROUTE_FALLBACK",
    "PUE_MAPPING_CONFIRMED",
    "PUE_MAPPING_REJECTED",
    "PUE_MAPPING_OVERRIDDEN",
    "PUE_MAPPING_CANDIDATES_VIEWED",
    "PUE_EXECUTION_BLOCKED",
    "PUE_EXECUTION_COMPLETED",
    "PUE_ANSWER_SURFACED",
    "PUE_ROLLBACK_TRIGGERED",
    "PUE_EVIDENCE_SURFACED",
    "PUE_CAPABILITY_SURFACED",
    "PUE_VISIBILITY_SUPPRESSED",
    "PUE_SHADOW_FAILURE",
)


class InMemoryActivationAuditSink:
    def __init__(self) -> None:
        self._events = []

    def record(
        self,
        *,
        event_type,
        actor_id,
        timestamp,
        reason,
        scope_key=None,
        activation_id=None,
        routing_id=None,
    ):
        if event_type not in AUDIT_EVENT_TYPES:
            raise ValueError("unregistered activation audit event")
        identity = fingerprint(
            event_type,
            actor_id,
            timestamp,
            reason,
            scope_key,
            activation_id,
            routing_id,
        )
        event = ActivationAuditEvent(
            "activation-audit-" + identity[:24],
            event_type,
            actor_id,
            scope_key,
            activation_id,
            routing_id,
            reason,
            timestamp,
            identity,
        )
        self._events.append(event)
        return event

    @property
    def events(self):
        return tuple(self._events)
