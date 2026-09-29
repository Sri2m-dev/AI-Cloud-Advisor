import hashlib
import json

import pytest
from cryptography.fernet import Fernet

from services.prospect_data_intake_service import (
    ProspectIntakeError,
    create_prospect_tenant,
    load_governed_bundle,
)
from universal_evidence.pilot.evidence_package import EvidencePackageError
from universal_evidence.pilot.evidence_package_persistence import (
    load_validated_evidence_package,
    persist_validated_evidence_package,
)


def _source(filename, source_type, content):
    return {
        "filename": filename,
        "type": source_type,
        "sha256": hashlib.sha256(content).hexdigest(),
        "bytes": len(content),
    }


def _package():
    org = b"AccountId,AccountName\n111111111111,Production\n"
    inventory = b"ResourceId,AccountId\ni-001,111111111111\n"
    cost = b"UsageAccountId,ResourceId,UnblendedCost\n" b"111111111111,i-001,10.00\n"
    mapping = b"Application,BusinessService\nPortal,Digital Checkout\n"

    manifest = {
        "package_version": "1.0",
        "package_id": "EVD-PERSIST-1",
        "customer": "Test Customer",
        "engagement": "Pilot-001",
        "files": [
            _source("org_accounts.csv", "org", org),
            _source("inventory.csv", "inventory", inventory),
            _source("cost_export.csv", "cost", cost),
            _source("app_mapping.csv", "application_mapping", mapping),
        ],
    }

    manifest_content = json.dumps(manifest).encode()

    files = (
        ("manifest.json", manifest_content),
        ("org_accounts.csv", org),
        ("inventory.csv", inventory),
        ("cost_export.csv", cost),
        ("app_mapping.csv", mapping),
    )

    return manifest_content, files


def _test_key():
    return Fernet.generate_key()


def _tenant(tmp_path, key):
    return create_prospect_tenant(
        "Package Test",
        consent=True,
        actor="tester@example.com",
        role="sales_engineer",
        retention_days=90,
        root=tmp_path,
        key=key,
    )


def test_valid_package_persists_declared_sources_only(tmp_path):
    _, files = _package()
    key = _test_key()
    tenant = _tenant(tmp_path, key)

    persisted = persist_validated_evidence_package(
        tenant,
        files=files,
        input_profile="aws",
        actor="tester@example.com",
        root=tmp_path,
        key=key,
    )

    assert persisted.package_id == "EVD-PERSIST-1"
    assert len(persisted.evidence_files) == 4

    stored = load_governed_bundle(
        tenant.tenant_id,
        root=tmp_path,
        key=key,
    )

    assert tuple(name for name, _ in stored) == (
        "org_accounts.csv",
        "inventory.csv",
        "cost_export.csv",
        "app_mapping.csv",
    )
    assert "manifest.json" not in {name for name, _ in stored}


def test_persisted_package_reloads_and_revalidates_customer_manifest(tmp_path):
    manifest_content, files = _package()
    key = _test_key()
    tenant = _tenant(tmp_path, key)

    persist_validated_evidence_package(
        tenant,
        files=files,
        input_profile="aws",
        actor="tester@example.com",
        root=tmp_path,
        key=key,
    )

    reloaded = load_validated_evidence_package(
        tenant.tenant_id,
        manifest_content=manifest_content,
        root=tmp_path,
        key=key,
    )

    assert reloaded.package_id == "EVD-PERSIST-1"
    assert reloaded.content("cost").startswith(b"UsageAccountId")


def test_invalid_manifest_fails_before_bundle_is_written(tmp_path):
    _, files = _package()
    key = _test_key()
    tenant = _tenant(tmp_path, key)

    bad_manifest = json.loads(files[0][1].decode())
    bad_manifest["files"][0]["sha256"] = "0" * 64

    bad_files = (("manifest.json", json.dumps(bad_manifest).encode()),) + files[1:]

    with pytest.raises(EvidencePackageError, match="sha256 mismatch"):
        persist_validated_evidence_package(
            tenant,
            files=bad_files,
            input_profile="aws",
            actor="tester@example.com",
            root=tmp_path,
            key=key,
        )

    assert not (tmp_path / tenant.tenant_id / "governed_bundle.enc").exists()


def test_expected_findings_are_not_persisted_as_evidence(tmp_path):
    _, files = _package()
    key = _test_key()
    tenant = _tenant(tmp_path, key)

    files = files + (("expected_findings.json", b'{"expected": "certification only"}'),)

    with pytest.raises(EvidencePackageError, match="undeclared source files"):
        persist_validated_evidence_package(
            tenant,
            files=files,
            input_profile="aws",
            actor="tester@example.com",
            root=tmp_path,
            key=key,
        )


def test_tampered_encrypted_source_fails_existing_bundle_identity_check(tmp_path):
    manifest_content, files = _package()
    key = _test_key()
    tenant = _tenant(tmp_path, key)

    persist_validated_evidence_package(
        tenant,
        files=files,
        input_profile="aws",
        actor="tester@example.com",
        root=tmp_path,
        key=key,
    )

    source_path = tmp_path / tenant.tenant_id / "governed_source_000.enc"
    source_path.write_bytes(b"tampered-encrypted-payload")

    with pytest.raises(ProspectIntakeError):
        load_validated_evidence_package(
            tenant.tenant_id,
            manifest_content=manifest_content,
            root=tmp_path,
            key=key,
        )
