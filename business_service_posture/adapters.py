"""Thin adapters over existing cost, risk, and health signal contracts."""

from __future__ import annotations

from datetime import datetime
from typing import Iterable

from business_service_posture.attribution import BusinessServiceAttributionResolver
from business_service_posture.models import (
    PostureDimension,
    PostureEvidenceReference,
    PostureSignal,
)
from core.digital_twin.technology.cost_signal import CostSignal
from core.digital_twin.technology.health_signal import HealthSignal
from core.digital_twin.technology.risk_signal import RiskSignal
from data_fabric.foundation import TenantContext


class DomainPostureAdapters:
    """Adapt owned domain signals without replacing their scoring engines."""

    def __init__(
        self,
        context: TenantContext,
        *,
        attribution: BusinessServiceAttributionResolver,
    ) -> None:
        context.assert_matches(attribution.context, "attribution resolver")
        self.context = context
        self.attribution = attribution

    def cost(
        self,
        signal: CostSignal,
        *,
        evidence: Iterable[PostureEvidenceReference] | None = None,
    ) -> PostureSignal:
        service = self.attribution.resolve_technology(str(signal.technology_id))
        source = signal.provider.strip() or "cost-domain"
        return self._signal(
            dimension=PostureDimension.COST,
            service_id=service.canonical_id,
            source_system=source,
            source_identifier=str(signal.id),
            observed_at=_parse_timestamp(signal.observed_at),
            score=None,
            value={
                "amount": signal.amount,
                "effective_amount": signal.effective_amount(),
                "provider": signal.provider,
                "service": signal.service,
                "signal_type": signal.signal_type,
            },
            confidence=signal.confidence_score,
            evidence=evidence,
        )

    def risk(
        self,
        signal: RiskSignal,
        *,
        evidence: Iterable[PostureEvidenceReference] | None = None,
    ) -> PostureSignal:
        service = self.attribution.resolve_technology(str(signal.technology_id))
        return self._signal(
            dimension=PostureDimension.RISK,
            service_id=service.canonical_id,
            source_system=signal.source_system,
            source_identifier=str(signal.id),
            observed_at=_parse_timestamp(signal.last_observed),
            score=signal.score,
            value={
                "risk_type": signal.risk_type,
                "severity": signal.severity,
                "probability": signal.probability,
                "impact": signal.impact,
                "status": signal.status,
            },
            confidence=signal.confidence_score,
            evidence=evidence,
        )

    def health(
        self,
        signal: HealthSignal,
        *,
        evidence: Iterable[PostureEvidenceReference] | None = None,
    ) -> PostureSignal:
        service = self.attribution.resolve_technology(str(signal.technology_id))
        return self._signal(
            dimension=PostureDimension.HEALTH,
            service_id=service.canonical_id,
            source_system=signal.source_system,
            source_identifier=str(signal.id),
            observed_at=_parse_timestamp(signal.last_observed),
            score=signal.value,
            value={
                "signal_type": signal.signal_type,
                "status": signal.status,
                "value": signal.value,
            },
            confidence=signal.confidence_score,
            evidence=evidence,
        )

    def _signal(
        self,
        *,
        dimension: PostureDimension,
        service_id: str,
        source_system: str,
        source_identifier: str,
        observed_at: datetime,
        score: float | None,
        value: dict[str, object],
        confidence: float,
        evidence: Iterable[PostureEvidenceReference] | None,
    ) -> PostureSignal:
        references = tuple(evidence or ())
        if not references:
            references = (
                PostureEvidenceReference(
                    evidence_id=source_identifier,
                    organization_id=self.context.organization_id,
                    tenant_id=self.context.tenant_id,
                    source_system=source_system,
                    source_identifier=source_identifier,
                ),
            )
        for reference in references:
            self.context.assert_record_matches(reference, "domain evidence")
        return PostureSignal(
            dimension=dimension,
            organization_id=self.context.organization_id,
            tenant_id=self.context.tenant_id,
            business_service_id=service_id,
            source_system=source_system,
            observed_at=observed_at,
            score=score,
            value=value,
            evidence=references,
            confidence=confidence,
        )


def _parse_timestamp(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("domain signal timestamp must be timezone-aware")
    return parsed
