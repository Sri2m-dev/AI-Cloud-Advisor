"""Deterministic AWS and Microsoft 365 certification fixtures."""

from __future__ import annotations

from datetime import datetime, timezone

from connector_certification.evidence import CertificationPage, SourceObservation

FIXED_TIME = datetime(2026, 7, 20, 0, 0, tzinfo=timezone.utc)


def aws_pages() -> tuple[CertificationPage, ...]:
    return (
        CertificationPage(
            cursor="aws-native-page-1",
            next_cursor="aws-native-page-2",
            observations=(
                SourceObservation(
                    "ec2_instance",
                    "i-certification-001",
                    FIXED_TIME,
                    {"region": "us-east-1", "state": "running"},
                ),
            ),
            expected_source_count=1,
        ),
        CertificationPage(
            cursor="aws-native-page-2",
            next_cursor=None,
            observations=(
                SourceObservation(
                    "s3_bucket",
                    "wp004-certification-bucket",
                    FIXED_TIME,
                    {"region": "global", "state": "active"},
                ),
            ),
            expected_source_count=1,
        ),
    )


def microsoft365_pages() -> tuple[CertificationPage, ...]:
    return (
        CertificationPage(
            cursor="m365-native-page-1",
            next_cursor="m365-native-page-2",
            observations=(
                SourceObservation(
                    "user",
                    "wp004-user-001",
                    FIXED_TIME,
                    {"account_enabled": True, "license": "Microsoft 365 E5"},
                ),
            ),
            expected_source_count=1,
        ),
        CertificationPage(
            cursor="m365-native-page-2",
            next_cursor=None,
            observations=(
                SourceObservation(
                    "group",
                    "wp004-group-001",
                    FIXED_TIME,
                    {"display_name": "WP-004 Certification Group"},
                ),
            ),
            expected_source_count=1,
        ),
    )
