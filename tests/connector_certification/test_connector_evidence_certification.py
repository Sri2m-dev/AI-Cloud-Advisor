from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import FrozenInstanceError
from datetime import timedelta
from pathlib import Path

import pytest

from auth.tenant_authorization import TenantAuthorizationContext, TenantAuthorizationError
from connector_certification.evidence import (
    CertificationCheckpoint,
    CertificationError,
    CertificationPage,
    ConnectorEvidenceCertifier,
    LogicalTombstone,
    SourceObservation,
)
from connector_certification.fixtures import FIXED_TIME, aws_pages, microsoft365_pages


def _context(organization="org-a", tenant="tenant-a", permissions=("connector:run",)):
    return TenantAuthorizationContext(
        organization_id=organization,
        tenant_id=tenant,
        subject_id="wp004-runner",
        subject_type="service",
        permissions=frozenset(permissions),
        source_boundary="connector",
    )


def _checkpoint(cursor="native-page-1", organization="org-a", tenant="tenant-a"):
    return CertificationCheckpoint(organization, tenant, "connector.test", "inventory", cursor)


def _observation(source_id="record-1", payload=None):
    return SourceObservation(
        "asset",
        source_id,
        FIXED_TIME,
        payload or {"name": "Certification Asset"},
    )


def _certify(page, **kwargs):
    return ConnectorEvidenceCertifier(**kwargs).certify_page(
        connector_id="connector.test",
        source_system="Test Source",
        stream_id="inventory",
        context=_context(),
        checkpoint=_checkpoint(page.cursor),
        page=page,
    )


@pytest.mark.parametrize(
    "connector_id,source_system,stream_id,pages",
    [
        ("aws.reference", "AWS", "inventory", aws_pages()),
        ("microsoft365.certification", "Microsoft 365", "directory", microsoft365_pages()),
    ],
)
def test_lighthouse_fixtures_certify_with_opaque_checkpoint_progression(
    connector_id, source_system, stream_id, pages
):
    context = _context()
    certifier = ConnectorEvidenceCertifier()
    checkpoint = CertificationCheckpoint(
        "org-a", "tenant-a", connector_id, stream_id, pages[0].cursor
    )
    seen = frozenset()
    accepted = 0
    for page in pages:
        result = certifier.certify_page(
            connector_id=connector_id,
            source_system=source_system,
            stream_id=stream_id,
            context=context,
            checkpoint=checkpoint,
            page=page,
            seen_identities=seen,
        )
        assert result.reconciled
        assert result.previous_checkpoint.cursor == page.cursor
        assert result.resulting_checkpoint.cursor == (page.next_cursor or page.cursor)
        accepted += result.accepted
        checkpoint, seen = result.resulting_checkpoint, result.seen_identities
    assert accepted == 2


def test_replay_is_idempotent_and_evidence_hash_is_deterministic():
    page = CertificationPage("native-page-1", None, (_observation(),), expected_source_count=1)
    first = _certify(page)
    replay = ConnectorEvidenceCertifier().certify_page(
        connector_id="connector.test",
        source_system="Test Source",
        stream_id="inventory",
        context=_context(),
        checkpoint=first.resulting_checkpoint,
        page=page,
        seen_identities=first.seen_identities,
    )
    assert first.accepted == 1
    assert replay.accepted == 0
    assert replay.duplicates == 1
    assert replay.observations == ()


def test_duplicate_records_in_one_page_are_classified_not_republished():
    observation = _observation()
    result = _certify(
        CertificationPage(
            "native-page-1", None, (observation, observation), expected_source_count=2
        )
    )
    assert (result.extracted, result.accepted, result.duplicates) == (2, 1, 1)
    assert result.reconciled


@pytest.mark.parametrize("valid,expected", [(False, "page validation"), (True, "count mismatch")])
def test_partial_or_unreconciled_page_does_not_advance_checkpoint(valid, expected):
    checkpoint = _checkpoint()
    page = CertificationPage(
        checkpoint.cursor,
        "native-page-2",
        (_observation(),),
        expected_source_count=2 if valid else 1,
        valid=valid,
    )
    with pytest.raises(CertificationError, match=expected):
        ConnectorEvidenceCertifier().certify_page(
            connector_id="connector.test",
            source_system="Test Source",
            stream_id="inventory",
            context=_context(),
            checkpoint=checkpoint,
            page=page,
        )
    assert checkpoint.cursor == "native-page-1"


def test_invalid_or_expired_cursor_fails_without_checkpoint_advance():
    checkpoint = _checkpoint("native-page-1")
    page = CertificationPage("expired-native-cursor", "native-page-2")
    with pytest.raises(CertificationError, match="invalid or expired"):
        ConnectorEvidenceCertifier().certify_page(
            connector_id="connector.test",
            source_system="Test Source",
            stream_id="inventory",
            context=_context(),
            checkpoint=checkpoint,
            page=page,
        )
    assert checkpoint.cursor == "native-page-1"


def test_tombstone_is_immutable_complete_and_idempotent():
    tombstone = LogicalTombstone(
        source_system="AWS",
        source_entity_type="ec2_instance",
        source_entity_id="i-deleted-001",
        tenant_id="tenant-a",
        organization_id="org-a",
        observed_at=FIXED_TIME,
        deleted_at=FIXED_TIME + timedelta(minutes=1),
        checkpoint_reference="native-page-1",
        deletion_reason="source_record_removed",
    )
    with pytest.raises(FrozenInstanceError):
        tombstone.deletion_reason = "changed"
    page = CertificationPage(
        "native-page-1", None, tombstones=(tombstone,), expected_source_count=1
    )
    first = _certify(page)
    replay = ConnectorEvidenceCertifier().certify_page(
        connector_id="connector.test",
        source_system="Test Source",
        stream_id="inventory",
        context=_context(),
        checkpoint=first.resulting_checkpoint,
        page=page,
        seen_identities=first.seen_identities,
    )
    assert first.deleted == 1
    assert first.observations[0].operation.value == "delete"
    assert replay.duplicates == 1 and replay.deleted == 0


@pytest.mark.parametrize(
    "checkpoint,match",
    [
        (_checkpoint(organization="org-b"), "organization boundary"),
        (_checkpoint(tenant="tenant-b"), "tenant boundary"),
        (
            CertificationCheckpoint("org-a", "tenant-a", "other", "inventory", "native-page-1"),
            "connector or stream",
        ),
    ],
)
def test_checkpoint_scope_cannot_cross_tenant_connector_or_stream(checkpoint, match):
    with pytest.raises(CertificationError, match=match):
        ConnectorEvidenceCertifier().certify_page(
            connector_id="connector.test",
            source_system="Test Source",
            stream_id="inventory",
            context=_context(),
            checkpoint=checkpoint,
            page=CertificationPage("native-page-1", None),
        )


def test_missing_connector_permission_is_denied_before_processing():
    with pytest.raises(TenantAuthorizationError, match="permission denied"):
        ConnectorEvidenceCertifier().certify_page(
            connector_id="connector.test",
            source_system="Test Source",
            stream_id="inventory",
            context=_context(permissions=()),
            checkpoint=_checkpoint(),
            page=CertificationPage("native-page-1", None),
        )


def test_secret_sentinel_is_rejected_and_not_reflected_in_error():
    secret = "wp004-synthetic-secret-value"
    page = CertificationPage(
        "native-page-1",
        None,
        (_observation(payload={"credential": secret}),),
        expected_source_count=1,
    )
    with pytest.raises(CertificationError) as exc_info:
        _certify(page, secret_sentinels=(secret,))
    assert secret not in str(exc_info.value)
    assert "secret material detected" in str(exc_info.value)


def test_tombstone_rejects_incorrect_hash_and_time_order():
    values = dict(
        source_system="AWS",
        source_entity_type="asset",
        source_entity_id="asset-1",
        tenant_id="tenant-a",
        organization_id="org-a",
        observed_at=FIXED_TIME,
        deleted_at=FIXED_TIME + timedelta(minutes=1),
        checkpoint_reference="native-page-1",
        deletion_reason="removed",
    )
    with pytest.raises(CertificationError, match="hash mismatch"):
        LogicalTombstone(**values, evidence_hash="incorrect")
    with pytest.raises(CertificationError, match="cannot precede"):
        LogicalTombstone(**{**values, "deleted_at": FIXED_TIME - timedelta(minutes=1)})


def test_manifest_payload_contains_only_governed_fields():
    result = _certify(
        CertificationPage("native-page-1", None, (_observation(),), expected_source_count=1)
    )
    payload = result.observations[0].as_manifest_payload()
    assert set(payload) == {
        "profile_version",
        "connector_id",
        "source_system",
        "source_entity_type",
        "source_entity_id",
        "tenant_id",
        "organization_id",
        "observed_at",
        "checkpoint_reference",
        "operation",
        "evidence_hash",
    }


def test_cli_gate_is_deterministic_and_secret_free():
    root = Path(__file__).resolve().parents[2]
    command = [
        sys.executable,
        str(root / "scripts" / "check_connector_evidence_certification.py"),
        "--json",
    ]
    first = subprocess.run(command, cwd=root, capture_output=True, text=True, check=False)
    second = subprocess.run(command, cwd=root, capture_output=True, text=True, check=False)
    assert first.returncode == second.returncode == 0
    assert json.loads(first.stdout) == json.loads(second.stdout)
    assert "secret" not in first.stdout.lower()
    assert [item["profile"] for item in json.loads(first.stdout)["profiles"]] == [
        "aws",
        "microsoft365",
    ]
