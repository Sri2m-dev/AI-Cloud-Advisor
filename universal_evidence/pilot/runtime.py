"""Process-local, default-deny ACT-002 pilot runtime wiring."""

from datetime import datetime, timezone

from universal_evidence.activation import (
    InMemoryActivationAuditSink,
    InMemoryPueActivationRepository,
    PueActivationResolver,
    PueActivationService,
)
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


def get_pilot_service():
    return PILOT_SERVICE
