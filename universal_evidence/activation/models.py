"""Immutable PUE-ACT-001 activation and routing contracts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum, IntEnum

from universal_evidence.capability import CapabilityScope
from universal_evidence.planning import AnalyticalIntentType


class ActivationStage(IntEnum):
    SHADOW_ONLY = 0
    EVIDENCE_DISCOVERY_VISIBLE = 1
    CAPABILITY_VISIBLE = 2
    SELECTED_ANSWERS = 3
    ASK_NEXORA_SELECTED_ROUTING = 4
    BROADER_AUTHORITY_REVIEW = 5


class ScopeLevel(IntEnum):
    GLOBAL = 0
    ORGANIZATION = 1
    TENANT = 2
    PROSPECT = 3
    ANALYSIS = 4


class FallbackPolicy(str, Enum):
    LEGACY_AUTHORITATIVE = "LEGACY_AUTHORITATIVE"
    PUE_IF_CERTIFIED_ELSE_LEGACY = "PUE_IF_CERTIFIED_ELSE_LEGACY"
    PUE_IF_CERTIFIED_ELSE_BLOCKED = "PUE_IF_CERTIFIED_ELSE_BLOCKED"
    SHADOW_COMPARE_ONLY = "SHADOW_COMPARE_ONLY"


class RollbackPolicy(str, Enum):
    SHADOW_ONLY = "SHADOW_ONLY"
    PREVIOUS_EFFECTIVE = "PREVIOUS_EFFECTIVE"
    SPECIFIED_STAGE = "SPECIFIED_STAGE"


class ConfigState(str, Enum):
    ACTIVE = "ACTIVE"
    SUPERSEDED = "SUPERSEDED"
    EXPIRED = "EXPIRED"
    ROLLED_BACK = "ROLLED_BACK"


class ActivationPermission(str, Enum):
    VIEW_PUE_ACTIVATION = "VIEW_PUE_ACTIVATION"
    CHANGE_PUE_STAGE = "CHANGE_PUE_STAGE"
    TRIGGER_PUE_ROLLBACK = "TRIGGER_PUE_ROLLBACK"
    TRIGGER_PUE_KILL_SWITCH = "TRIGGER_PUE_KILL_SWITCH"


class Route(str, Enum):
    ROUTE_PUE = "ROUTE_PUE"
    ROUTE_LEGACY = "ROUTE_LEGACY"
    BLOCK = "BLOCK"
    SHADOW_ONLY = "SHADOW_ONLY"


class RoutingReason(str, Enum):
    PUE_DISABLED = "PUE_DISABLED"
    KILL_SWITCH_ACTIVE = "KILL_SWITCH_ACTIVE"
    SHADOW_ONLY = "SHADOW_ONLY"
    QUESTION_TYPE_NOT_ALLOWED = "QUESTION_TYPE_NOT_ALLOWED"
    PUE_CAPABILITY_BLOCKED = "PUE_CAPABILITY_BLOCKED"
    PUE_CAPABILITY_SUPPORTED = "PUE_CAPABILITY_SUPPORTED"
    PUE_INTERPRETATION_AMBIGUOUS = "PUE_INTERPRETATION_AMBIGUOUS"
    PUE_INTERPRETATION_UNSUPPORTED = "PUE_INTERPRETATION_UNSUPPORTED"
    PUE_FAILURE = "PUE_FAILURE"
    LEGACY_FALLBACK_SELECTED = "LEGACY_FALLBACK_SELECTED"
    PUE_ROUTE_SELECTED = "PUE_ROUTE_SELECTED"
    ROUTING_SCOPE_MISMATCH = "ROUTING_SCOPE_MISMATCH"
    ACTIVATION_EXPIRED = "ACTIVATION_EXPIRED"


class ActivationHealthState(str, Enum):
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    UNHEALTHY = "UNHEALTHY"
    PAUSED = "PAUSED"


class ReadinessState(str, Enum):
    NOT_READY = "NOT_READY"
    READY_FOR_STAGE_1_PILOT = "READY_FOR_STAGE_1_PILOT"
    READY_FOR_STAGE_2_PILOT = "READY_FOR_STAGE_2_PILOT"
    READY_FOR_SELECTED_STAGE_3_PILOT = "READY_FOR_SELECTED_STAGE_3_PILOT"
    NOT_READY_FOR_STAGE_4 = "NOT_READY_FOR_STAGE_4"


class ArtifactPersistenceClass(str, Enum):
    EPHEMERAL = "EPHEMERAL"
    RETENTION_BOUND = "RETENTION_BOUND"
    AUDIT_REQUIRED = "AUDIT_REQUIRED"
    CONFIGURATION = "CONFIGURATION"
    OPTIONAL_HISTORY = "OPTIONAL_HISTORY"


@dataclass(frozen=True, slots=True)
class ActivationScope:
    level: ScopeLevel
    organization_id: str | None = None
    tenant_id: str | None = None
    prospect_id: str | None = None
    analysis_id: str | None = None

    def __post_init__(self) -> None:
        required = {
            ScopeLevel.GLOBAL: (),
            ScopeLevel.ORGANIZATION: ("organization_id",),
            ScopeLevel.TENANT: ("tenant_id",),
            ScopeLevel.PROSPECT: ("prospect_id",),
            ScopeLevel.ANALYSIS: ("analysis_id",),
        }[self.level]
        if any(not getattr(self, name) for name in required):
            raise ValueError(f"{self.level.name} activation scope is incomplete")

    @property
    def key(self) -> tuple[object, ...]:
        return (
            self.level,
            self.organization_id,
            self.tenant_id,
            self.prospect_id,
            self.analysis_id,
        )

    def matches(self, scope: CapabilityScope) -> bool:
        checks = (
            self.organization_id is None or self.organization_id == scope.organization_id,
            self.tenant_id is None or self.tenant_id == scope.tenant_id,
            self.prospect_id is None or self.prospect_id == scope.prospect_id,
            self.analysis_id is None or self.analysis_id == scope.analysis_id,
        )
        return all(checks)


@dataclass(frozen=True, slots=True)
class ActivationActor:
    actor_id: str
    actor_role: str
    actor_type: str
    permissions: tuple[ActivationPermission, ...]


@dataclass(frozen=True, slots=True)
class PueActivationConfig:
    activation_id: str
    scope: ActivationScope
    activation_stage: ActivationStage
    enabled_capabilities: tuple[str, ...]
    visible_surfaces: tuple[str, ...]
    allowed_question_types: tuple[AnalyticalIntentType, ...]
    fallback_policy: FallbackPolicy
    rollback_policy: RollbackPolicy
    effective_from: datetime
    expires_at: datetime | None
    configured_by: ActivationActor
    configured_at: datetime
    reason: str
    policy_version: str
    state: ConfigState
    supersedes_activation_id: str | None
    fingerprint: str


@dataclass(frozen=True, slots=True)
class KillSwitchConfig:
    kill_switch_id: str
    enabled: bool
    allow_shadow_execution: bool
    fallback_policy: FallbackPolicy
    actor: ActivationActor
    reason: str
    configured_at: datetime
    policy_version: str
    fingerprint: str


@dataclass(frozen=True, slots=True)
class ActivationFeatureSet:
    show_evidence_discovery: bool
    show_capability_matrix: bool
    allow_selected_answers: bool
    route_selected_questions: bool
    enable_confirmation_ui: bool


@dataclass(frozen=True, slots=True)
class ActivationResolution:
    scope: CapabilityScope
    config: PueActivationConfig | None
    stage: ActivationStage
    features: ActivationFeatureSet
    kill_switch: KillSwitchConfig | None
    fallback_policy: FallbackPolicy
    reason_codes: tuple[RoutingReason, ...]
    fingerprint: str


@dataclass(frozen=True, slots=True)
class RoutingDecision:
    routing_id: str
    question_id: str
    scope: CapabilityScope
    activation_stage: ActivationStage
    question_type: AnalyticalIntentType | None
    pue_eligible: bool
    legacy_eligible: bool
    route: Route
    reason_codes: tuple[RoutingReason, ...]
    activation_config_id: str | None
    policy_version: str
    fingerprint: str


@dataclass(frozen=True, slots=True)
class ActivationAuditEvent:
    event_id: str
    event_type: str
    actor_id: str
    scope_key: tuple[object, ...] | None
    activation_id: str | None
    routing_id: str | None
    reason: str
    timestamp: datetime
    fingerprint: str


@dataclass(frozen=True, slots=True)
class ActivationMetrics:
    total_routes: int
    pue_routes: int
    fallbacks: int
    blocked_queries: int
    ambiguous_interpretations: int
    stage_failures: int
    error_rate: float
    fallback_rate: float
    p95_latency_ms: float


@dataclass(frozen=True, slots=True)
class PueActivationHealth:
    state: ActivationHealthState
    metrics: ActivationMetrics
    reasons: tuple[str, ...]
    evaluated_at: datetime
    policy_version: str


@dataclass(frozen=True, slots=True)
class ActivationReadinessReport:
    certification_chain: tuple[str, ...]
    readiness: ReadinessState
    pilot_scope_recommendation: str
    question_allowlist_recommendation: tuple[AnalyticalIntentType, ...]
    persistence_classification: tuple[tuple[str, ArtifactPersistenceClass], ...]
    audit_events: tuple[str, ...]
    observability_metrics: tuple[str, ...]
    blockers: tuple[str, ...]
    recommendation: str
