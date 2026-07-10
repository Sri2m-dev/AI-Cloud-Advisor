from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from enum import Enum
from uuid import UUID

import pytest

from data_fabric.foundation import (
    DataFabricError,
    DataFabricTenantBoundaryError,
    DataFabricValidationError,
    DefaultDeterministicSerializer,
    TenantContext,
    normalize_to_utc,
    require_timezone_aware,
    validate_created_updated_order,
    validate_effective_period,
)


class DemoEnum(str, Enum):
    VALUE = "value"


@dataclass(frozen=True)
class DemoRecord:
    id: str
    tags: set[str]
    values: tuple[int, ...]
    when: datetime


def test_shared_exceptions_are_catchable_through_data_fabric_error():
    with pytest.raises(DataFabricError):
        raise DataFabricValidationError("invalid")


def test_deterministic_serialization_supports_common_contract_values():
    serializer = DefaultDeterministicSerializer()
    when = datetime(2026, 7, 10, 12, 30, tzinfo=timezone.utc)
    value = {
        "enum": DemoEnum.VALUE,
        "uuid": UUID("12345678-1234-5678-1234-567812345678"),
        "tuple": (3, 2, 1),
        "set": {"b", "a"},
        "record": DemoRecord("demo", {"z", "a"}, (1, 2), when),
    }

    encoded = serializer.to_json_compatible(value)

    assert encoded["enum"] == "value"
    assert encoded["uuid"] == "12345678-1234-5678-1234-567812345678"
    assert encoded["set"] == ["a", "b"]
    assert encoded["record"]["tags"] == ["a", "z"]
    assert serializer.dumps(value) == serializer.dumps(value)


def test_dictionary_insertion_order_does_not_change_serialization_or_hash():
    serializer = DefaultDeterministicSerializer()
    left = {"b": 2, "a": {"y": 2, "x": 1}}
    right = {"a": {"x": 1, "y": 2}, "b": 2}

    assert serializer.dumps(left) == serializer.dumps(right)
    assert serializer.content_hash(left) == serializer.content_hash(right)


def test_naive_datetime_is_rejected():
    serializer = DefaultDeterministicSerializer()
    naive = datetime(2026, 7, 10, 12, 0)

    with pytest.raises(DataFabricValidationError):
        require_timezone_aware(naive)
    with pytest.raises(DataFabricValidationError):
        serializer.dumps({"when": naive})


def test_utc_normalization_is_deterministic():
    value = datetime(2026, 7, 10, 18, 0, tzinfo=timezone(timedelta(hours=5, minutes=30)))

    assert normalize_to_utc(value).isoformat() == "2026-07-10T12:30:00+00:00"


def test_time_order_helpers_validate_boundaries():
    created = datetime(2026, 7, 10, 12, 0, tzinfo=timezone.utc)
    updated = datetime(2026, 7, 10, 12, 5, tzinfo=timezone.utc)

    validate_created_updated_order(created, updated)
    validate_effective_period(created, updated)
    with pytest.raises(DataFabricValidationError):
        validate_created_updated_order(updated, created)
    with pytest.raises(DataFabricValidationError):
        validate_effective_period(updated, created)


def test_tenant_boundary_mismatch_raises_explicit_error():
    left = TenantContext("org-1", "tenant-a")
    right = TenantContext("org-1", "tenant-b")

    with pytest.raises(DataFabricTenantBoundaryError):
        left.assert_matches(right)


def test_tenant_context_serializes_deterministically():
    serializer = DefaultDeterministicSerializer()
    context = TenantContext("org-1", "tenant-a")

    assert context.to_serializable() == {"organization_id": "org-1", "tenant_id": "tenant-a"}
    assert serializer.dumps(context) == '{"organization_id":"org-1","tenant_id":"tenant-a"}'
