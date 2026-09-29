import hashlib
import json

import pytest

from universal_evidence.pilot.evidence_package import (
    EvidencePackageError,
    parse_package_manifest,
    validate_evidence_package,
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
    cost = b"UsageAccountId,ResourceId,UnblendedCost\n111111111111,i-001,10.00\n"
    mapping = b"Application,BusinessService\nPortal,Digital Checkout\n"

    manifest = {
        "package_version": "1.0",
        "package_id": "EVD-TEST-1",
        "customer": "Test Customer",
        "engagement": "Pilot-001",
        "files": [
            _source("org_accounts.csv", "org", org),
            _source("inventory.csv", "inventory", inventory),
            _source("cost_export.csv", "cost", cost),
            _source("app_mapping.csv", "application_mapping", mapping),
        ],
    }

    files = (
        ("manifest.json", json.dumps(manifest).encode()),
        ("org_accounts.csv", org),
        ("inventory.csv", inventory),
        ("cost_export.csv", cost),
        ("app_mapping.csv", mapping),
    )
    return manifest, files


def test_valid_multi_source_package_is_verified():
    _, files = _package()

    package = validate_evidence_package(files)

    assert package.package_id == "EVD-TEST-1"
    assert len(package.files) == 4
    assert package.manifest.source("cost").filename == "cost_export.csv"
    assert package.content("inventory").startswith(b"ResourceId")


def test_manifest_parser_rejects_unsupported_source_type():
    manifest, _ = _package()
    manifest["files"][0]["type"] = "expected_findings"

    with pytest.raises(EvidencePackageError, match="unsupported package source type"):
        parse_package_manifest(json.dumps(manifest).encode())


def test_expected_findings_cannot_be_ingested_as_evidence():
    _, files = _package()
    files = files + (("expected_findings.json", b'{"answer": "do not ingest"}'),)

    with pytest.raises(EvidencePackageError, match="undeclared source files"):
        validate_evidence_package(files)


def test_missing_declared_source_fails_closed():
    _, files = _package()
    files = tuple(item for item in files if item[0] != "inventory.csv")

    with pytest.raises(EvidencePackageError, match="missing declared source files"):
        validate_evidence_package(files)


def test_modified_source_fails_sha256_validation():
    _, files = _package()
    files = tuple(
        (name, b"tampered") if name == "cost_export.csv" else (name, content)
        for name, content in files
    )

    with pytest.raises(EvidencePackageError, match="byte count mismatch|sha256 mismatch"):
        validate_evidence_package(files)


def test_duplicate_source_type_fails_closed():
    manifest, _ = _package()
    duplicate = dict(manifest["files"][0])
    duplicate["filename"] = "another_org.csv"
    duplicate["sha256"] = "0" * 64
    duplicate["bytes"] = 0
    manifest["files"].append(duplicate)

    with pytest.raises(EvidencePackageError, match="duplicate package source type"):
        parse_package_manifest(json.dumps(manifest).encode())


def test_path_traversal_filename_is_rejected():
    manifest, _ = _package()
    manifest["files"][0]["filename"] = "../org_accounts.csv"

    with pytest.raises(EvidencePackageError, match="safe basename"):
        parse_package_manifest(json.dumps(manifest).encode())


def test_manifest_v1_accepts_canonical_name_field():
    import hashlib
    import json

    from universal_evidence.pilot.evidence_package import (
        parse_package_manifest,
    )

    content = b"AccountId,AccountName\n111,Production\n"

    payload = {
        "package_version": "1.0",
        "package_id": "EVD-CONTRACT-NAME",
        "customer": "Contract Test",
        "engagement": "Pilot",
        "files": [
            {
                "name": "org_accounts.csv",
                "type": "org",
                "sha256": hashlib.sha256(content).hexdigest(),
                "bytes": len(content),
            }
        ],
    }

    manifest = parse_package_manifest(json.dumps(payload).encode("utf-8"))

    assert len(manifest.files) == 1
    assert manifest.files[0].filename == "org_accounts.csv"
    assert manifest.files[0].source_type == "org"


def test_manifest_v1_filename_alias_remains_compatible():
    import hashlib
    import json

    from universal_evidence.pilot.evidence_package import (
        parse_package_manifest,
    )

    content = b"AccountId,AccountName\n111,Production\n"

    payload = {
        "package_version": "1.0",
        "package_id": "EVD-CONTRACT-FILENAME",
        "customer": "Contract Test",
        "engagement": "Pilot",
        "files": [
            {
                "filename": "org_accounts.csv",
                "type": "org",
                "sha256": hashlib.sha256(content).hexdigest(),
                "bytes": len(content),
            }
        ],
    }

    manifest = parse_package_manifest(json.dumps(payload).encode("utf-8"))

    assert len(manifest.files) == 1
    assert manifest.files[0].filename == "org_accounts.csv"
    assert manifest.files[0].source_type == "org"


def test_manifest_cannot_disguise_json_oracle_as_a_supported_source():
    manifest, _ = _package()
    manifest["files"][0]["filename"] = "expected_findings.json"
    with pytest.raises(EvidencePackageError, match="CSV or XLSX"):
        parse_package_manifest(json.dumps(manifest).encode())
