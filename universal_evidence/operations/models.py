"""Bounded ACT-011 event taxonomy and privacy-safe event contracts."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from types import MappingProxyType
from typing import Any, Mapping
from uuid import uuid4


class GovernedEventType(str, Enum):
    EVIDENCE_ADMITTED = "EVIDENCE_ADMITTED"
    EVIDENCE_REJECTED = "EVIDENCE_REJECTED"
    EVIDENCE_PROFILED = "EVIDENCE_PROFILED"
    MAPPING_CANDIDATES_VIEWED = "MAPPING_CANDIDATES_VIEWED"
    MAPPING_CONFIRMED = "MAPPING_CONFIRMED"
    MAPPING_REJECTED = "MAPPING_REJECTED"
    MAPPING_OVERRIDDEN = "MAPPING_OVERRIDDEN"
    NORMALIZATION_STARTED = "NORMALIZATION_STARTED"
    NORMALIZATION_COMPLETED = "NORMALIZATION_COMPLETED"
    NORMALIZATION_BLOCKED = "NORMALIZATION_BLOCKED"
    NORMALIZATION_FAILED = "NORMALIZATION_FAILED"
    CAPABILITY_EVALUATED = "CAPABILITY_EVALUATED"
    CAPABILITY_BLOCKED = "CAPABILITY_BLOCKED"
    EXECUTION_AUTHORIZED = "EXECUTION_AUTHORIZED"
    EXECUTION_REJECTED = "EXECUTION_REJECTED"
    EXECUTION_EXPIRED = "EXECUTION_EXPIRED"
    EXECUTION_STALE = "EXECUTION_STALE"
    PLAN_CREATED = "PLAN_CREATED"
    EXECUTION_STARTED = "EXECUTION_STARTED"
    EXECUTION_COMPLETED = "EXECUTION_COMPLETED"
    EXECUTION_BLOCKED = "EXECUTION_BLOCKED"
    EXECUTION_FAILED = "EXECUTION_FAILED"
    RESULT_STALE = "RESULT_STALE"
    ENTITY_PROPOSED = "ENTITY_PROPOSED"
    ENTITY_MATERIALIZED = "ENTITY_MATERIALIZED"
    ENTITY_CONFLICT = "ENTITY_CONFLICT"
    MATCH_PROPOSED = "MATCH_PROPOSED"
    MATCH_CONFIRMED = "MATCH_CONFIRMED"
    MATCH_REJECTED = "MATCH_REJECTED"
    MATCH_CONFLICT = "MATCH_CONFLICT"
    BINDING_CREATED = "BINDING_CREATED"
    ASK_RECEIVED = "ASK_RECEIVED"
    ASK_INTERPRETED = "ASK_INTERPRETED"
    ASK_AUTHORIZED = "ASK_AUTHORIZED"
    ASK_BLOCKED = "ASK_BLOCKED"
    ASK_EXECUTED = "ASK_EXECUTED"
    ASK_ANSWER_COMPOSED = "ASK_ANSWER_COMPOSED"
    ASK_UNSUPPORTED = "ASK_UNSUPPORTED"
    STATE_EXPIRED = "STATE_EXPIRED"
    PURGE_REQUESTED = "PURGE_REQUESTED"
    PURGE_COMPLETED = "PURGE_COMPLETED"
    PURGE_FAILED = "PURGE_FAILED"
    PERSISTENCE_INITIALIZED = "PERSISTENCE_INITIALIZED"
    PERSISTENCE_FAILED = "PERSISTENCE_FAILED"
    MIGRATION_COMPLETED = "MIGRATION_COMPLETED"
    MIGRATION_FAILED = "MIGRATION_FAILED"
    KILL_SWITCH_ENABLED = "KILL_SWITCH_ENABLED"
    KILL_SWITCH_DISABLED = "KILL_SWITCH_DISABLED"
    ACTIVATION_CHANGED = "ACTIVATION_CHANGED"
    SCOPE_ACCESS_REJECTED = "SCOPE_ACCESS_REJECTED"
    UNAUTHORIZED_ACTION = "UNAUTHORIZED_ACTION"
    POTENTIAL_INJECTION_BLOCKED = "POTENTIAL_INJECTION_BLOCKED"


EVENT_TAXONOMY = frozenset(GovernedEventType)


class Severity(str, Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    SECURITY = "SECURITY"


class FailureClass(str, Enum):
    EXPECTED_BLOCK = "EXPECTED_BLOCK"
    USER_GOVERNANCE_REQUIRED = "USER_GOVERNANCE_REQUIRED"
    SECURITY_REJECTION = "SECURITY_REJECTION"
    DEPENDENCY_FAILURE = "DEPENDENCY_FAILURE"
    PERSISTENCE_FAILURE = "PERSISTENCE_FAILURE"
    MIGRATION_FAILURE = "MIGRATION_FAILURE"
    INTERNAL_ERROR = "INTERNAL_ERROR"
    UNSUPPORTED = "UNSUPPORTED"


class ReasonCode(str, Enum):
    MISSING_GOVERNED_CURRENCY = "MISSING_GOVERNED_CURRENCY"
    AMBIGUOUS_MEASURE = "AMBIGUOUS_MEASURE"
    MAPPING_CONFIRMATION_REQUIRED = "MAPPING_CONFIRMATION_REQUIRED"
    EXECUTION_NOT_AUTHORIZED = "EXECUTION_NOT_AUTHORIZED"
    AUTHORIZATION_STALE = "AUTHORIZATION_STALE"
    CROSS_SCOPE_ACCESS = "CROSS_SCOPE_ACCESS"
    KILL_SWITCH_ACTIVE = "KILL_SWITCH_ACTIVE"
    UNSUPPORTED_QUESTION = "UNSUPPORTED_QUESTION"
    PERSISTENCE_UNAVAILABLE = "PERSISTENCE_UNAVAILABLE"
    MIGRATION_FAILURE = "MIGRATION_FAILURE"
    AUDIT_UNAVAILABLE = "AUDIT_UNAVAILABLE"
    POTENTIAL_INJECTION = "POTENTIAL_INJECTION"


@dataclass(frozen=True, slots=True)
class OperationContext:
    organization_id: str
    tenant_id: str
    prospect_id: str | None = None
    analysis_id: str | None = None
    actor_id: str | None = None
    actor_role: str | None = None
    correlation_id: str = field(default_factory=lambda: new_correlation_id())
    mode: str = "PRODUCTION"

    def __post_init__(self):
        if not self.organization_id or not self.tenant_id:
            raise ValueError("organization_id and tenant_id are required")
        if not self.correlation_id:
            raise ValueError("correlation_id is required")


@dataclass(frozen=True, slots=True)
class GovernedEvent:
    event_id: str
    event_type: GovernedEventType
    timestamp: datetime
    severity: Severity
    context: OperationContext
    outcome: str
    failure_class: FailureClass | None = None
    reason_code: ReasonCode | None = None
    duration_ms: float | None = None
    references: Mapping[str, str] = field(default_factory=dict)
    attributes: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        object.__setattr__(self, "references", MappingProxyType(dict(self.references)))
        object.__setattr__(self, "attributes", MappingProxyType(dict(self.attributes)))

    def payload(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type.value,
            "timestamp": self.timestamp.isoformat(),
            "severity": self.severity.value,
            "organization_id": self.context.organization_id,
            "tenant_id": self.context.tenant_id,
            "prospect_id": self.context.prospect_id,
            "analysis_id": self.context.analysis_id,
            "actor_id": self.context.actor_id,
            "actor_role": self.context.actor_role,
            "correlation_id": self.context.correlation_id,
            "mode": self.context.mode,
            "outcome": self.outcome,
            "failure_class": self.failure_class.value if self.failure_class else None,
            "reason_code": self.reason_code.value if self.reason_code else None,
            "duration_ms": self.duration_ms,
            "references": dict(self.references),
            "attributes": redact(self.attributes),
        }


SENSITIVE_KEYS = re.compile(
    r"(password|secret|token|credential|api.?key|encryption.?key|connection.?string|raw.?row|prompt|payload)",
    re.IGNORECASE,
)
SECRET_VALUES = re.compile(
    r"(postgres(?:ql)?://\S+|https?://[^\s/@]+:[^\s/@]+@\S+|bearer\s+\S+|sk-[A-Za-z0-9_-]+)",
    re.IGNORECASE,
)


def redact(value: Any, *, key: str = "") -> Any:
    if SENSITIVE_KEYS.search(str(key)):
        return "[REDACTED]"
    if isinstance(value, Mapping):
        return {str(item): redact(nested, key=str(item)) for item, nested in value.items()}
    if isinstance(value, (tuple, list, set, frozenset)):
        return [redact(item) for item in value]
    if isinstance(value, bytes):
        return "[REDACTED_BYTES]"
    if isinstance(value, str):
        return SECRET_VALUES.sub("[REDACTED]", value)[:512]
    return value


def new_correlation_id() -> str:
    return "NX-COR-" + uuid4().hex[:20].upper()


def support_id(correlation_id: str) -> str:
    suffix = re.sub(r"[^A-Za-z0-9]", "", correlation_id)[-12:].upper()
    return "NX-" + suffix


def new_event(
    event_type: GovernedEventType,
    context: OperationContext,
    *,
    severity: Severity = Severity.INFO,
    outcome: str = "SUCCESS",
    failure_class: FailureClass | None = None,
    reason_code: ReasonCode | None = None,
    duration_ms: float | None = None,
    references: Mapping[str, str] | None = None,
    attributes: Mapping[str, Any] | None = None,
    clock=None,
) -> GovernedEvent:
    now = clock() if clock else datetime.now(timezone.utc)
    return GovernedEvent(
        "nx-event-" + uuid4().hex,
        event_type,
        now,
        severity,
        context,
        outcome,
        failure_class,
        reason_code,
        duration_ms,
        references or {},
        redact(attributes or {}),
    )
