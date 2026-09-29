"""Governed persistence bridge for validated zero-access evidence packages.

The package manifest is validated before persistence. Only declared evidence
sources enter the existing encrypted governed bundle. The customer manifest
remains package control metadata and is not admitted as analytical evidence.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from services.prospect_data_intake_service import (
    STORE_ROOT,
    ProspectTenant,
    load_governed_bundle,
    store_governed_bundle,
)

from .evidence_package import (
    EvidencePackageManifest,
    ValidatedEvidencePackage,
    validate_evidence_package,
)


@dataclass(frozen=True, slots=True)
class PersistedEvidencePackage:
    package_id: str
    manifest: EvidencePackageManifest
    evidence_files: tuple[tuple[str, bytes], ...]


def persist_validated_evidence_package(
    tenant: ProspectTenant,
    *,
    files: Iterable[tuple[str, bytes]],
    input_profile: str,
    actor: str,
    root: Path = STORE_ROOT,
    key: str | bytes | None = None,
) -> PersistedEvidencePackage:
    """Validate a customer package and retain only its declared evidence sources."""

    package = validate_evidence_package(tuple(files))

    store_governed_bundle(
        tenant,
        files=package.files,
        input_profile=input_profile,
        actor=actor,
        root=root,
        key=key,
    )

    return PersistedEvidencePackage(
        package_id=package.package_id,
        manifest=package.manifest,
        evidence_files=package.files,
    )


def load_validated_evidence_package(
    tenant_id: str,
    *,
    manifest_content: bytes,
    root: Path = STORE_ROOT,
    key: str | bytes | None = None,
) -> ValidatedEvidencePackage:
    """Reload encrypted evidence and revalidate it against customer manifest."""

    evidence_files = load_governed_bundle(
        tenant_id,
        root=root,
        key=key,
    )

    return validate_evidence_package((("manifest.json", manifest_content),) + tuple(evidence_files))
