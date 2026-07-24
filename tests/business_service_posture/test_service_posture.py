from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from business_service_posture import (
    BusinessServicePostureService,
    InMemoryBusinessServicePostureRepository,
    PostureAvailability,
    PostureDimension,
    PostureSignal,
)
from data_fabric.foundation import DataFabricTenantBoundaryError, TenantContext
from enterprise_registry import (
    BusinessServiceRegistry,
    InMemoryBusinessServiceRepository,
    create_business_service,
)


@pytest.fixture
def context() -> TenantContext:
    return TenantContext("org-1", "tenant-a")


@pytest.fixture
def service_id(context: TenantContext) -> str:
    registry = BusinessServiceRegistry(
        context,
        InMemoryBusinessServiceRepository(),
    )
    registered = registry.register(
        create_business_service(
            context=context,
            business_service_id="payments",
            name="Payments",
            description="Processes payments",
            business_domain="payments",
            service_type="customer_facing",
            criticality="critical",
            owner_id="owner-1",
            source_system="service-catalog",
            source_id="svc-100",
        )
    )
    return registered.canonical_id


@pytest.fixture
def posture_service(
    context: TenantContext,
) -> tuple[BusinessServicePostureService, str]:
    registry = BusinessServiceRegistry(
        context,
        InMemoryBusinessServiceRepository(),
    )
    registered = registry.register(
        create_business_service(
            context=context,
            business_service_id="payments",
            name="Payments",
            description="Processes payments",
            business_domain="payments",
            service_type="customer_facing",
            criticality="critical",
            owner_id="owner-1",
            source_system="service-catalog",
            source_id="svc-100",
        )
    )
    return (
        BusinessServicePostureService(
            context,
            services=registry,
            repository=InMemoryBusinessServicePostureRepository(),
        ),
        registered.canonical_id,
    )


def signal(
    context: TenantContext,
    dimension: PostureDimension,
    *,
    now: datetime,
    age: timedelta = timedelta(),
    score: float = 90.0,
) -> PostureSignal:
    return PostureSignal(
        dimension=dimension,
        organization_id=context.organization_id,
        tenant_id=context.tenant_id,
        source_system=f"{dimension.value}-domain",
        observed_at=now - age,
        score=score,
        value={"measurement": score},
        evidence_ids=(f"{dimension.value}-evidence",),
        confidence=0.95,
    )


def test_posture_exposes_dimensional_evidence_without_composite(
    context: TenantContext,
    posture_service: tuple[BusinessServicePostureService, str],
) -> None:
    service, canonical_id = posture_service
    now = datetime(2026, 7, 24, 2, 0, tzinfo=timezone.utc)

    posture = service.publish(
        canonical_id,
        {
            dimension: signal(context, dimension, now=now)
            for dimension in PostureDimension
        },
        generated_at=now,
    )

    assert posture.posture_version == 1
    assert posture.completeness == 1.0
    assert posture.missing_dimensions == ()
    assert posture.has_stale_data is False
    assert set(posture.dimensions) == set(PostureDimension)
    assert posture.dimensions[PostureDimension.COST].evidence_ids == (
        "cost-evidence",
    )
    assert not hasattr(posture, "overall_score")


def test_missing_domain_inputs_are_visible_and_never_scored(
    context: TenantContext,
    posture_service: tuple[BusinessServicePostureService, str],
) -> None:
    service, canonical_id = posture_service
    now = datetime(2026, 7, 24, 2, 0, tzinfo=timezone.utc)

    posture = service.publish(
        canonical_id,
        {
            PostureDimension.HEALTH: signal(
                context,
                PostureDimension.HEALTH,
                now=now,
            )
        },
        generated_at=now,
    )

    assert posture.completeness == pytest.approx(1 / 3, rel=1e-4)
    assert posture.missing_dimensions == (
        PostureDimension.COST,
        PostureDimension.RISK,
    )
    for dimension in posture.missing_dimensions:
        result = posture.dimensions[dimension]
        assert result.availability is PostureAvailability.MISSING
        assert result.score is None
        assert result.reason == "domain_input_missing"


def test_freshness_is_dimension_specific_and_explicit(
    context: TenantContext,
    posture_service: tuple[BusinessServicePostureService, str],
) -> None:
    service, canonical_id = posture_service
    now = datetime(2026, 7, 24, 2, 0, tzinfo=timezone.utc)

    posture = service.publish(
        canonical_id,
        {
            PostureDimension.COST: signal(
                context,
                PostureDimension.COST,
                now=now,
                age=timedelta(hours=25),
            ),
            PostureDimension.RISK: signal(
                context,
                PostureDimension.RISK,
                now=now,
                age=timedelta(hours=25),
            ),
            PostureDimension.HEALTH: signal(
                context,
                PostureDimension.HEALTH,
                now=now,
                age=timedelta(minutes=16),
            ),
        },
        generated_at=now,
    )

    assert (
        posture.dimensions[PostureDimension.COST].availability
        is PostureAvailability.AVAILABLE
    )
    assert (
        posture.dimensions[PostureDimension.RISK].availability
        is PostureAvailability.STALE
    )
    assert (
        posture.dimensions[PostureDimension.HEALTH].availability
        is PostureAvailability.STALE
    )
    assert posture.has_stale_data is True


def test_posture_versions_and_history_are_deterministic(
    context: TenantContext,
    posture_service: tuple[BusinessServicePostureService, str],
) -> None:
    service, canonical_id = posture_service
    now = datetime(2026, 7, 24, 2, 0, tzinfo=timezone.utc)
    inputs = {
        dimension: signal(context, dimension, now=now)
        for dimension in PostureDimension
    }

    first = service.publish(canonical_id, inputs, generated_at=now)
    second = service.publish(
        canonical_id,
        inputs,
        generated_at=now + timedelta(minutes=1),
    )

    assert first.posture_version == 1
    assert second.posture_version == 2
    assert [item.posture_version for item in service.history(canonical_id)] == [
        1,
        2,
    ]
    assert service.latest(canonical_id) == second


def test_cross_tenant_domain_signal_is_rejected(
    posture_service: tuple[BusinessServicePostureService, str],
) -> None:
    service, canonical_id = posture_service
    other_context = TenantContext("org-1", "tenant-b")
    now = datetime(2026, 7, 24, 2, 0, tzinfo=timezone.utc)

    with pytest.raises(DataFabricTenantBoundaryError):
        service.publish(
            canonical_id,
            {
                PostureDimension.COST: signal(
                    other_context,
                    PostureDimension.COST,
                    now=now,
                )
            },
            generated_at=now,
        )


def test_future_or_naive_observation_times_are_rejected(
    context: TenantContext,
    posture_service: tuple[BusinessServicePostureService, str],
) -> None:
    service, canonical_id = posture_service
    now = datetime(2026, 7, 24, 2, 0, tzinfo=timezone.utc)
    with pytest.raises(ValueError, match="timezone-aware"):
        signal(
            context,
            PostureDimension.COST,
            now=now.replace(tzinfo=None),
        )
    with pytest.raises(ValueError, match="future"):
        service.publish(
            canonical_id,
            {
                PostureDimension.COST: signal(
                    context,
                    PostureDimension.COST,
                    now=now + timedelta(minutes=1),
                )
            },
            generated_at=now,
        )
