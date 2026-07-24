from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from business_service_posture import (
    BusinessServicePostureService,
    InMemoryBusinessServicePostureRepository,
    PostureAvailability,
    PostureDimension,
    PostureEvidenceReference,
    PostureSignal,
)
from data_fabric.foundation import DataFabricTenantBoundaryError, TenantContext
from enterprise_registry import (
    BusinessServiceNotFoundError,
    BusinessServiceRegistry,
    InMemoryBusinessServiceRepository,
    canonical_business_service_id,
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
        business_service_id=canonical_business_service_id(context, "payments"),
        source_system=f"{dimension.value}-domain",
        observed_at=now - age,
        score=score,
        value={"measurement": score},
        evidence=(
            PostureEvidenceReference(
                evidence_id=f"{dimension.value}-evidence",
                organization_id=context.organization_id,
                tenant_id=context.tenant_id,
                source_system=f"{dimension.value}-domain",
                source_identifier=f"{dimension.value}-source",
            ),
        ),
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
    assert second == first
    assert [item.posture_version for item in service.history(canonical_id)] == [1]
    assert service.get_version(canonical_id, 1) == first
    assert service.latest(canonical_id) == first


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


def test_completely_missing_posture_is_explicit(
    posture_service: tuple[BusinessServicePostureService, str],
) -> None:
    service, canonical_id = posture_service
    now = datetime(2026, 7, 24, 2, 0, tzinfo=timezone.utc)

    posture = service.publish(canonical_id, {}, generated_at=now)

    assert posture.completeness == 0.0
    assert posture.missing_dimensions == tuple(PostureDimension)
    assert all(result.score is None for result in posture.dimensions.values())


@pytest.mark.parametrize(
    ("dimension", "threshold"),
    [
        (PostureDimension.COST, timedelta(hours=26)),
        (PostureDimension.RISK, timedelta(hours=24)),
        (PostureDimension.HEALTH, timedelta(minutes=15)),
    ],
)
def test_freshness_boundary_and_stale_transition_are_versioned(
    context: TenantContext,
    posture_service: tuple[BusinessServicePostureService, str],
    dimension: PostureDimension,
    threshold: timedelta,
) -> None:
    service, canonical_id = posture_service
    observed = datetime(2026, 7, 24, 2, 0, tzinfo=timezone.utc)
    domain_signal = signal(context, dimension, now=observed)

    boundary = service.publish(
        canonical_id,
        {dimension: domain_signal},
        generated_at=observed + threshold,
    )
    stale = service.publish(
        canonical_id,
        {dimension: domain_signal},
        generated_at=observed + threshold + timedelta(seconds=1),
    )

    assert (
        boundary.dimensions[dimension].availability
        is PostureAvailability.AVAILABLE
    )
    assert stale.dimensions[dimension].availability is PostureAvailability.STALE
    assert boundary.posture_version == 1
    assert stale.posture_version == 2


@pytest.mark.parametrize("changed_dimension", list(PostureDimension))
def test_dimension_changes_create_one_deterministic_new_version(
    context: TenantContext,
    posture_service: tuple[BusinessServicePostureService, str],
    changed_dimension: PostureDimension,
) -> None:
    service, canonical_id = posture_service
    now = datetime(2026, 7, 24, 2, 0, tzinfo=timezone.utc)
    original = {
        dimension: signal(context, dimension, now=now, score=90)
        for dimension in PostureDimension
    }
    changed = dict(original)
    changed[changed_dimension] = signal(
        context,
        changed_dimension,
        now=now,
        score=75,
    )

    first = service.publish(canonical_id, original, generated_at=now)
    second = service.publish(canonical_id, changed, generated_at=now)

    assert second.posture_version == first.posture_version + 1
    assert second.dimensions[changed_dimension].score == 75
    for dimension in set(PostureDimension) - {changed_dimension}:
        assert second.dimensions[dimension] == first.dimensions[dimension]


def test_cross_tenant_business_service_is_not_visible(
    context: TenantContext,
) -> None:
    repository = InMemoryBusinessServiceRepository()
    other_context = TenantContext("org-1", "tenant-b")
    other_registry = BusinessServiceRegistry(other_context, repository)
    foreign = other_registry.register(
        create_business_service(
            context=other_context,
            business_service_id="foreign",
            name="Foreign",
            description="Other tenant",
            business_domain="other",
            service_type="shared",
            criticality="medium",
            owner_id="owner-2",
            source_system="catalog",
            source_id="foreign",
        )
    )
    service = BusinessServicePostureService(
        context,
        services=BusinessServiceRegistry(context, repository),
        repository=InMemoryBusinessServicePostureRepository(),
    )

    with pytest.raises(BusinessServiceNotFoundError):
        service.publish(
            foreign.canonical_id,
            {},
            generated_at=datetime(2026, 7, 24, 2, 0, tzinfo=timezone.utc),
        )
