from datetime import datetime, timezone

import pytest

from services.approval_service import calculate_sla_status

NOW = datetime(2026, 5, 20, 12, 0, tzinfo=timezone.utc)


@pytest.mark.parametrize(
    ("created_at", "expected"),
    [
        ("2026-05-19T12:00:00Z", "OK"),
        ("2026-05-19T11:59:59Z", "MANAGER_ESCALATION"),
        ("2026-05-18T12:00:00Z", "MANAGER_ESCALATION"),
        ("2026-05-18T11:59:59Z", "LEADERSHIP_ESCALATION"),
        ("2026-05-17T12:00:00Z", "LEADERSHIP_ESCALATION"),
        ("2026-05-17T11:59:59Z", "AUTO_CLOSE_OR_ESCALATE"),
    ],
)
def test_calculate_sla_status_threshold_boundaries(created_at, expected):
    result = calculate_sla_status(
        {"created_at": created_at, "status": "PENDING"},
        now=NOW,
    )

    assert result.success
    assert result.data == expected


def test_calculate_sla_status_preserves_historical_missing_status_behavior():
    result = calculate_sla_status({"created_at": "2026-05-19T00:00:00Z"}, now=NOW)

    assert result.success
    assert result.data == "OK"


def test_calculate_sla_status_normalizes_timezone_offsets():
    result = calculate_sla_status(
        {"created_at": "2026-05-19T13:00:00+01:00", "status": "PENDING"},
        now=NOW,
    )

    assert result.success
    assert result.data == "OK"


@pytest.mark.parametrize(
    ("approval", "error"),
    [
        (None, "invalid_approval"),
        ({}, "missing_created_at"),
        ({"created_at": "not-a-date"}, "invalid_created_at"),
    ],
)
def test_calculate_sla_status_rejects_invalid_or_missing_inputs(approval, error):
    result = calculate_sla_status(approval, now=NOW)

    assert not result.success
    assert result.data is None
    assert result.errors == (error,)

