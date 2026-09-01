"""Default-deny pilot wiring with configured ACT-009 durability."""

import os
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import lru_cache

from universal_evidence.activation import (
    InMemoryActivationAuditSink,
    InMemoryPueActivationRepository,
    PueActivationResolver,
    PueActivationService,
)
from universal_evidence.governance import ConfirmationService
from universal_evidence.pilot.measurement_service import PilotGovernedMeasurementService
from universal_evidence.pilot.normalization_service import PilotGovernedNormalizationService
from universal_evidence.pilot.semantic_service import PilotSemanticGovernanceService
from universal_evidence.pilot.service import PueStage12PilotService
from universal_evidence.shadow import ShadowOrchestrator


def _clock():
    return datetime.now(timezone.utc)


ACTIVATION_REPOSITORY = InMemoryPueActivationRepository()
ACTIVATION_AUDIT = InMemoryActivationAuditSink()
ACTIVATION_RESOLVER = PueActivationResolver(
    repository=ACTIVATION_REPOSITORY,
    clock=_clock,
)
ACTIVATION_SERVICE = PueActivationService(
    repository=ACTIVATION_REPOSITORY,
    audit_sink=ACTIVATION_AUDIT,
    clock=_clock,
)
PILOT_SERVICE = PueStage12PilotService(
    activation_resolver=ACTIVATION_RESOLVER,
    shadow_orchestrator=ShadowOrchestrator(clock=_clock),
    audit_sink=ACTIVATION_AUDIT,
    clock=_clock,
)
CONFIRMATION_SERVICE = ConfirmationService(clock=_clock)
SEMANTIC_PILOT_SERVICE = PilotSemanticGovernanceService(
    activation_resolver=ACTIVATION_RESOLVER,
    confirmation_service=CONFIRMATION_SERVICE,
    telemetry=PILOT_SERVICE.telemetry,
    audit_sink=ACTIVATION_AUDIT,
    clock=_clock,
)
NORMALIZATION_PILOT_SERVICE = PilotGovernedNormalizationService(
    activation_resolver=ACTIVATION_RESOLVER,
    semantic_service=SEMANTIC_PILOT_SERVICE,
    confirmation_service=CONFIRMATION_SERVICE,
    telemetry=PILOT_SERVICE.telemetry,
)
MEASUREMENT_PILOT_SERVICE = PilotGovernedMeasurementService(
    activation_resolver=ACTIVATION_RESOLVER,
    normalization_service=NORMALIZATION_PILOT_SERVICE,
    telemetry=PILOT_SERVICE.telemetry,
    audit_sink=ACTIVATION_AUDIT,
    clock=_clock,
)


def get_pilot_service():
    configured = _configured_services()
    return configured.pilot if configured is not None else PILOT_SERVICE


def get_semantic_pilot_service():
    configured = _configured_services()
    return configured.semantic if configured is not None else SEMANTIC_PILOT_SERVICE


def get_normalization_pilot_service():
    configured = _configured_services()
    return configured.normalization if configured is not None else NORMALIZATION_PILOT_SERVICE


def get_measurement_pilot_service():
    configured = _configured_services()
    return configured.measurement if configured is not None else MEASUREMENT_PILOT_SERVICE


def get_activation_service():
    configured = _configured_services()
    return configured.activation if configured is not None else ACTIVATION_SERVICE


@dataclass(frozen=True)
class _ConfiguredPilotServices:
    pilot: object
    activation: object
    confirmation: object
    semantic: object
    normalization: object
    measurement: object


def _configured_services():
    database = str(os.getenv("NEXORA_UNIVERSAL_EVIDENCE_DB") or "").strip()
    return _build_configured_services(database) if database else None


@lru_cache(maxsize=8)
def _build_configured_services(database):
    from services.universal_evidence_runtime_service import (
        initialize_universal_evidence_runtime,
    )

    runtime = initialize_universal_evidence_runtime(database)
    audit = InMemoryActivationAuditSink()
    resolver, activation = runtime.build_activation_services(audit_sink=audit, clock=_clock)
    confirmation, semantic, normalization, measurement = runtime.build_pilot_services(
        activation_resolver=resolver,
        audit_sink=audit,
        clock=_clock,
    )
    pilot = PueStage12PilotService(
        activation_resolver=resolver,
        shadow_orchestrator=ShadowOrchestrator(clock=_clock),
        audit_sink=audit,
        clock=_clock,
    )
    return _ConfiguredPilotServices(
        pilot,
        activation,
        confirmation,
        semantic,
        normalization,
        measurement,
    )


def reset_configured_runtime_cache():
    """Dispose process composition pointers; durable authority remains untouched."""
    _build_configured_services.cache_clear()
