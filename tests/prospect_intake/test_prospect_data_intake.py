from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from cryptography.fernet import Fernet

from services.prospect_data_intake_service import (
    PROSPECT_CLASSIFICATION,
    SUPPORTED_PROFILES,
    ProspectIntakeError,
    create_prospect_tenant,
    ingest_upload,
    load_analysis,
    purge_tenant,
    scan_upload,
)


@pytest.fixture
def key() -> bytes:
    return Fernet.generate_key()


def _tenant(tmp_path: Path, key: bytes):
    return create_prospect_tenant(
        "ABC Corporation",
        consent=True,
        actor="sales@example.com",
        role="sales_engineer",
        root=tmp_path,
        key=key,
    )


def test_tenant_requires_consent_and_authorized_role(tmp_path: Path, key: bytes) -> None:
    with pytest.raises(ProspectIntakeError, match="consent"):
        create_prospect_tenant(
            "ABC", consent=False, actor="x", role="sales_engineer", root=tmp_path, key=key
        )
    with pytest.raises(ProspectIntakeError, match="Sales Engineer"):
        create_prospect_tenant(
            "ABC", consent=True, actor="x", role="executive", root=tmp_path, key=key
        )


def test_tenant_has_unique_ids_and_30_day_expiration(tmp_path: Path, key: bytes) -> None:
    tenant = _tenant(tmp_path, key)
    assert tenant.tenant_id.startswith("prospect-")
    assert tenant.audit_id.startswith("audit-")
    assert tenant.classification == PROSPECT_CLASSIFICATION
    lifetime = datetime.fromisoformat(tenant.expires_at) - datetime.fromisoformat(
        tenant.created_at
    )
    assert lifetime == timedelta(days=30)


def test_malware_and_executable_content_are_rejected() -> None:
    with pytest.raises(ProspectIntakeError, match="malware"):
        scan_upload("bill.csv", b"EICAR-STANDARD-ANTIVIRUS-TEST-FILE")
    with pytest.raises(ProspectIntakeError, match="executable"):
        scan_upload("bill.csv", b"MZ" + b"0" * 20)


@pytest.mark.parametrize("profile", SUPPORTED_PROFILES)
def test_all_six_authorized_profiles_normalize(
    profile: str, tmp_path: Path, key: bytes
) -> None:
    tenant = _tenant(tmp_path, key)
    analysis = ingest_upload(
        tenant,
        profile=profile,
        filename="input.csv",
        content=b"provider,service,cost,currency\nAWS,Compute,100,USD\n",
        actor="sales@example.com",
        role="sales_engineer",
        root=tmp_path,
        key=key,
    )
    assert analysis.total_spend == 100


def test_ingestion_encrypts_source_and_derivatives(tmp_path: Path, key: bytes) -> None:
    tenant = _tenant(tmp_path, key)
    content = (
        b"provider,service,cost,currency,potential_savings\n"
        b"AWS,EC2,1000,USD,200\nAzure,Storage,500,USD,50\n"
    )
    analysis = ingest_upload(
        tenant,
        profile="Generic technology-cost Excel/CSV",
        filename="costs.csv",
        content=content,
        actor="sales@example.com",
        role="sales_engineer",
        root=tmp_path,
        key=key,
    )
    assert analysis.total_spend == 1500
    assert analysis.cloud_spend == 1500
    assert analysis.opportunity_identified == 250
    assert analysis.opportunity_evidence_qualified == 250
    assert analysis.opportunity_recommended == 0
    tenant_path = tmp_path / tenant.tenant_id
    assert b"AWS" not in (tenant_path / "source.enc").read_bytes()
    assert b"1500" not in (tenant_path / "analysis.enc").read_bytes()
    assert load_analysis(tenant.tenant_id, root=tmp_path, key=key) == analysis


def test_unsupported_attribution_remains_unknown(tmp_path: Path, key: bytes) -> None:
    tenant = _tenant(tmp_path, key)
    analysis = ingest_upload(
        tenant,
        profile="Manual invoice/bill spreadsheet",
        filename="invoice.csv",
        content=b"amount,currency\n1000,USD\n",
        actor="finance@example.com",
        role="finance",
        root=tmp_path,
        key=key,
    )
    assert analysis.unclassified_spend == 1000
    assert analysis.evidence_coverage == 0
    assert analysis.opportunity_evidence_qualified == 0


def test_saas_unused_license_opportunity_is_evidence_qualified(
    tmp_path: Path, key: bytes
) -> None:
    tenant = _tenant(tmp_path, key)
    analysis = ingest_upload(
        tenant,
        profile="SaaS/license CSV or Excel",
        filename="licenses.csv",
        content=(
            b"vendor,product,cost,currency,licenses,used_licenses\n"
            b"Vendor A,Collaboration,12000,USD,100,75\n"
        ),
        actor="finance@example.com",
        role="finance",
        root=tmp_path,
        key=key,
    )
    assert analysis.saas_spend == 12000
    assert analysis.opportunity_identified == 3000
    assert analysis.opportunity_evidence_qualified == 3000


def test_purge_removes_all_tenant_artifacts_and_leaves_minimal_tombstone(
    tmp_path: Path, key: bytes
) -> None:
    tenant = _tenant(tmp_path, key)
    ingest_upload(
        tenant,
        profile="AWS billing/CUR-derived CSV",
        filename="aws.csv",
        content=b"provider,service,cost\nAWS,EC2,100\n",
        actor="sales@example.com",
        role="sales_engineer",
        root=tmp_path,
        key=key,
    )
    expired = replace(
        tenant, expires_at=(datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()
    )
    purge_tenant(
        expired,
        actor="sales@example.com",
        role="sales_engineer",
        root=tmp_path,
        key=key,
    )
    assert not (tmp_path / tenant.tenant_id).exists()
    tombstone = (tmp_path / "purge_tombstones.jsonl").read_text(encoding="utf-8")
    assert tenant.tenant_id in tombstone
    assert "ABC Corporation" not in tombstone


def test_invalid_encryption_key_cannot_read_analysis(tmp_path: Path, key: bytes) -> None:
    tenant = _tenant(tmp_path, key)
    ingest_upload(
        tenant,
        profile="GCP billing export",
        filename="gcp.csv",
        content=b"provider,service,cost\nGCP,Compute,100\n",
        actor="sales@example.com",
        role="sales_engineer",
        root=tmp_path,
        key=key,
    )
    with pytest.raises(ProspectIntakeError, match="cannot be read"):
        load_analysis(tenant.tenant_id, root=tmp_path, key=Fernet.generate_key())
