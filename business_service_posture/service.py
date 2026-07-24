"""Tenant-bound Business Service posture query/data product."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Mapping

from business_service_posture.models import (
    REQUIRED_POSTURE_DIMENSIONS,
    BusinessServicePosture,
    PostureAvailability,
    PostureDimension,
    PostureDimensionResult,
    PostureSignal,
    utc_now,
)
from business_service_posture.repository import BusinessServicePostureRepository
from data_fabric.foundation import TenantContext
from enterprise_registry import BusinessServiceRegistry

DEFAULT_FRESHNESS_LIMITS: Mapping[PostureDimension, timedelta] = {
    PostureDimension.COST: timedelta(hours=26),
    PostureDimension.RISK: timedelta(hours=24),
    PostureDimension.HEALTH: timedelta(minutes=15),
}


class BusinessServicePostureService:
    """Compose owned domain evidence without hiding missing dimensions."""

    def __init__(
        self,
        context: TenantContext,
        *,
        services: BusinessServiceRegistry,
        repository: BusinessServicePostureRepository,
        freshness_limits: Mapping[PostureDimension, timedelta] | None = None,
    ) -> None:
        context.assert_matches(services.context, "business service registry")
        self.context = context
        self.services = services
        self.repository = repository
        self.freshness_limits = dict(
            freshness_limits or DEFAULT_FRESHNESS_LIMITS
        )

    def publish(
        self,
        business_service_id: str,
        signals: Mapping[PostureDimension, PostureSignal],
        *,
        generated_at: datetime | None = None,
    ) -> BusinessServicePosture:
        now = generated_at or utc_now()
        if now.tzinfo is None:
            raise ValueError("generated_at must be timezone-aware")
        service = self.services.get_by_canonical_id(
            business_service_id,
            include_inactive=True,
        )
        normalized = {
            PostureDimension(key): value for key, value in signals.items()
        }
        for signal in normalized.values():
            self.context.assert_record_matches(signal, "posture signal")
            if signal.dimension not in REQUIRED_POSTURE_DIMENSIONS:
                raise ValueError("unsupported posture dimension")
        previous = self.repository.latest(self.context, service.canonical_id)
        posture = BusinessServicePosture(
            organization_id=self.context.organization_id,
            tenant_id=self.context.tenant_id,
            business_service_id=service.canonical_id,
            business_service_version=service.version,
            posture_version=1 if previous is None else previous.posture_version + 1,
            generated_at=now,
            dimensions={
                dimension: self._dimension_result(
                    dimension,
                    normalized.get(dimension),
                    now=now,
                )
                for dimension in REQUIRED_POSTURE_DIMENSIONS
            },
        )
        return self.repository.publish(self.context, posture)

    def latest(self, business_service_id: str) -> BusinessServicePosture | None:
        service = self.services.get_by_canonical_id(
            business_service_id,
            include_inactive=True,
        )
        return self.repository.latest(self.context, service.canonical_id)

    def history(self, business_service_id: str) -> list[BusinessServicePosture]:
        service = self.services.get_by_canonical_id(
            business_service_id,
            include_inactive=True,
        )
        return self.repository.history(self.context, service.canonical_id)

    def _dimension_result(
        self,
        dimension: PostureDimension,
        signal: PostureSignal | None,
        *,
        now: datetime,
    ) -> PostureDimensionResult:
        if signal is None:
            return PostureDimensionResult(
                dimension=dimension,
                availability=PostureAvailability.MISSING,
                score=None,
                source_system=None,
                observed_at=None,
                age_seconds=None,
                evidence_ids=(),
                value={},
                confidence=None,
                reason="domain_input_missing",
            )
        if signal.dimension is not dimension:
            raise ValueError("posture signal is keyed under the wrong dimension")
        age = now - signal.observed_at
        if age.total_seconds() < 0:
            raise ValueError("posture signal cannot be observed in the future")
        stale = age > self.freshness_limits[dimension]
        return PostureDimensionResult(
            dimension=dimension,
            availability=(
                PostureAvailability.STALE
                if stale
                else PostureAvailability.AVAILABLE
            ),
            score=signal.score,
            source_system=signal.source_system,
            observed_at=signal.observed_at,
            age_seconds=int(age.total_seconds()),
            evidence_ids=signal.evidence_ids,
            value=signal.value,
            confidence=signal.confidence,
            reason="freshness_limit_exceeded" if stale else "domain_input_available",
        )
