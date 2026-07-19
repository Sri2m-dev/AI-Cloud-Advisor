from __future__ import annotations

import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import pytest

from governance.contract_event_governance import (
    ChangeLevel,
    ConsumerRequirement,
    ContractManifest,
    DeprecationNotice,
    FieldSchema,
    GovernanceValidationError,
    SemanticVersion,
    assess_compatibility,
)


def _manifest(version="1.0.0", fields=None, kind="event"):
    return ContractManifest(
        contract_id="enterprise.correlation-event",
        kind=kind,
        version=SemanticVersion.parse(version),
        provider="Enterprise Correlation",
        fields=tuple(
            fields
            or (
                FieldSchema("event_type", "string"),
                FieldSchema("organization_id", "string"),
                FieldSchema("payload", "object", required=False),
            )
        ),
    )


@pytest.mark.parametrize("value", ["1", "1.0", "v1.0.0", "1.-1.0", "1.0.x"])
def test_semantic_version_rejects_malformed_values(value):
    with pytest.raises(GovernanceValidationError):
        SemanticVersion.parse(value)


def test_optional_field_requires_minor_version_and_passes_when_declared():
    previous = _manifest()
    current = _manifest(
        "1.1.0",
        fields=previous.fields + (FieldSchema("correlation_id", "string", required=False),),
    )

    result = assess_compatibility(previous, current)

    assert result.required_change is ChangeLevel.MINOR
    assert result.declared_change is ChangeLevel.MINOR
    assert result.compatible is True


def test_required_field_addition_is_breaking_and_requires_major_version():
    previous = _manifest()
    insufficient = _manifest(
        "1.1.0", fields=previous.fields + (FieldSchema("subject_id", "string"),)
    )
    sufficient = replace(insufficient, version=SemanticVersion.parse("2.0.0"))

    assert assess_compatibility(previous, insufficient).compatible is False
    assert assess_compatibility(previous, sufficient).compatible is True


def test_field_removal_type_change_and_enum_removal_are_breaking():
    previous = _manifest(
        fields=(
            FieldSchema("event_type", "string", enum_values=("Created", "Deleted")),
            FieldSchema("organization_id", "string"),
        )
    )
    removed = _manifest(
        "1.1.0",
        fields=(FieldSchema("event_type", "string", enum_values=("Created",)),),
    )

    result = assess_compatibility(previous, removed)

    assert result.required_change is ChangeLevel.MAJOR
    assert result.compatible is False
    assert len(result.reasons) == 2


def test_manifest_change_without_version_increment_fails():
    previous = _manifest()
    current = replace(previous, fields=previous.fields[:-1])

    result = assess_compatibility(previous, current)

    assert result.compatible is False
    assert "manifest changed without a version increment" in result.reasons


def test_deprecation_requires_replacement_and_major_removal_window():
    with pytest.raises(GovernanceValidationError, match="major-version removal window"):
        DeprecationNotice(
            "legacy_id",
            SemanticVersion.parse("1.2.0"),
            SemanticVersion.parse("1.9.0"),
            "canonical_id",
        )


def test_deprecation_must_reference_present_field():
    notice = DeprecationNotice(
        "legacy_id",
        SemanticVersion.parse("1.2.0"),
        SemanticVersion.parse("2.0.0"),
        "canonical_id",
    )
    with pytest.raises(GovernanceValidationError, match="not present"):
        replace(_manifest(), deprecations=(notice,))


def test_consumer_provider_gate_checks_identity_version_fields_and_types():
    requirement = ConsumerRequirement(
        consumer="Impact Analysis",
        contract_id="enterprise.correlation-event",
        minimum_version=SemanticVersion.parse("1.0.0"),
        required_fields={"event_type": "string", "organization_id": "string"},
    )
    requirement.verify(_manifest())

    with pytest.raises(GovernanceValidationError, match="consumer field missing"):
        requirement.verify(_manifest(fields=(FieldSchema("event_type", "string"),)))


def test_payload_validation_fails_closed_for_required_type_and_enum():
    manifest = _manifest(
        fields=(
            FieldSchema("event_type", "string", enum_values=("Created", "Deleted")),
            FieldSchema("organization_id", "string"),
        )
    )
    manifest.validate_payload({"event_type": "Created", "organization_id": "org-a"})

    with pytest.raises(GovernanceValidationError, match="required field missing"):
        manifest.validate_payload({"event_type": "Created"})
    with pytest.raises(GovernanceValidationError, match="unsupported event_type"):
        manifest.validate_payload({"event_type": "Changed", "organization_id": "org-a"})
    with pytest.raises(GovernanceValidationError, match="must be string"):
        manifest.validate_payload({"event_type": "Created", "organization_id": 1})


def test_committed_provider_consumer_registry_passes_cli_gate():
    root = Path(__file__).resolve().parents[2]
    result = subprocess.run(
        [sys.executable, str(root / "scripts" / "check_contract_event_governance.py")],
        cwd=root,
        capture_output=True,
        check=False,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert "2 providers, 2 consumers" in result.stdout
