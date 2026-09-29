"""Governed multi-source evidence-package contract for zero-access onboarding.

This module validates package identity and source integrity only. It does not
infer semantics, publish SourceFacts, or treat expected findings as evidence.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping

SUPPORTED_PACKAGE_VERSION = "1.0"

SUPPORTED_SOURCE_TYPES = frozenset(
    {
        "org",
        "inventory",
        "cost",
        "application_mapping",
    }
)


class EvidencePackageError(ValueError):
    """Raised when an uploaded evidence package fails deterministic validation."""


@dataclass(frozen=True, slots=True)
class EvidencePackageSource:
    filename: str
    source_type: str
    sha256: str
    bytes: int

    def __post_init__(self) -> None:
        filename = str(self.filename or "").strip()
        source_type = str(self.source_type or "").strip()
        digest = str(self.sha256 or "").strip().lower()

        if not filename or Path(filename).name != filename:
            raise EvidencePackageError("package source filename must be a safe basename")

        if Path(filename).suffix.lower() not in {".csv", ".xlsx"}:
            raise EvidencePackageError("certified package sources must be CSV or XLSX evidence")

        if source_type not in SUPPORTED_SOURCE_TYPES:
            raise EvidencePackageError(
                f"unsupported package source type: {source_type or 'UNKNOWN'}"
            )

        if len(digest) != 64 or any(character not in "0123456789abcdef" for character in digest):
            raise EvidencePackageError(f"invalid sha256 for package source: {filename}")

        if isinstance(self.bytes, bool) or not isinstance(self.bytes, int) or self.bytes < 0:
            raise EvidencePackageError(f"invalid byte count for package source: {filename}")


@dataclass(frozen=True, slots=True)
class EvidencePackageManifest:
    package_version: str
    package_id: str
    customer: str
    engagement: str
    files: tuple[EvidencePackageSource, ...]
    raw: Mapping[str, Any]

    def source(self, source_type: str) -> EvidencePackageSource | None:
        matches = tuple(item for item in self.files if item.source_type == source_type)
        if len(matches) > 1:
            raise EvidencePackageError(f"duplicate package source type: {source_type}")
        return matches[0] if matches else None


@dataclass(frozen=True, slots=True)
class ValidatedEvidencePackage:
    manifest: EvidencePackageManifest
    files: tuple[tuple[str, bytes], ...]

    @property
    def package_id(self) -> str:
        return self.manifest.package_id

    def content(self, source_type: str) -> bytes | None:
        source = self.manifest.source(source_type)
        if source is None:
            return None
        lookup = dict(self.files)
        return lookup[source.filename]


def parse_package_manifest(content: bytes) -> EvidencePackageManifest:
    try:
        payload = json.loads(content.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise EvidencePackageError("manifest.json is not valid UTF-8 JSON") from exc

    if not isinstance(payload, dict):
        raise EvidencePackageError("manifest.json must contain a JSON object")

    package_version = str(payload.get("package_version") or "").strip()
    if package_version != SUPPORTED_PACKAGE_VERSION:
        raise EvidencePackageError(
            f"unsupported evidence package version: {package_version or 'UNKNOWN'}"
        )

    package_id = str(payload.get("package_id") or "").strip()
    if not package_id:
        raise EvidencePackageError("package_id is required")

    customer = str(payload.get("customer") or "").strip()
    engagement = str(payload.get("engagement") or "").strip()

    raw_files = payload.get("files")
    if not isinstance(raw_files, list) or not raw_files:
        raise EvidencePackageError("manifest files must be a non-empty list")

    sources = []
    seen_names: set[str] = set()
    seen_types: set[str] = set()

    for raw_source in raw_files:
        if not isinstance(raw_source, dict):
            raise EvidencePackageError("each manifest file entry must be an object")

        source = EvidencePackageSource(
            filename=str(raw_source.get("name") or raw_source.get("filename") or ""),
            source_type=str(raw_source.get("type") or ""),
            sha256=str(raw_source.get("sha256") or ""),
            bytes=raw_source.get("bytes"),
        )

        if source.filename in seen_names:
            raise EvidencePackageError(f"duplicate package filename: {source.filename}")

        if source.source_type in seen_types:
            raise EvidencePackageError(f"duplicate package source type: {source.source_type}")

        seen_names.add(source.filename)
        seen_types.add(source.source_type)
        sources.append(source)

    return EvidencePackageManifest(
        package_version=package_version,
        package_id=package_id,
        customer=customer,
        engagement=engagement,
        files=tuple(sources),
        raw=payload,
    )


def validate_evidence_package(
    files: Iterable[tuple[str, bytes]],
) -> ValidatedEvidencePackage:
    supplied: dict[str, bytes] = {}

    for filename, content in files:
        safe_name = str(filename or "").strip()
        if not safe_name or Path(safe_name).name != safe_name:
            raise EvidencePackageError("uploaded package filenames must be safe basenames")

        if safe_name in supplied:
            raise EvidencePackageError(f"duplicate uploaded filename: {safe_name}")

        supplied[safe_name] = bytes(content)

    manifest_content = supplied.get("manifest.json")
    if manifest_content is None:
        raise EvidencePackageError("manifest.json is required for an evidence package")

    manifest = parse_package_manifest(manifest_content)
    declared_names = {source.filename for source in manifest.files}

    missing = sorted(declared_names - supplied.keys())
    if missing:
        raise EvidencePackageError(
            "package is missing declared source files: " + ", ".join(missing)
        )

    unexpected = sorted(
        name for name in supplied if name != "manifest.json" and name not in declared_names
    )
    if unexpected:
        raise EvidencePackageError(
            "package contains undeclared source files: " + ", ".join(unexpected)
        )

    validated = []

    for source in manifest.files:
        content = supplied[source.filename]

        if len(content) != source.bytes:
            raise EvidencePackageError(f"byte count mismatch for package source: {source.filename}")

        digest = hashlib.sha256(content).hexdigest()
        if digest != source.sha256:
            raise EvidencePackageError(f"sha256 mismatch for package source: {source.filename}")

        validated.append((source.filename, content))

    return ValidatedEvidencePackage(
        manifest=manifest,
        files=tuple(validated),
    )
