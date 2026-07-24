"""Persistence-neutral governed evidence registry reference implementation."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone

from data_fabric.foundation import DefaultDeterministicSerializer, TenantContext

from evidence_registry.models import (
    CaseEvidence,
    EvidenceItem,
    EvidencePackage,
    EvidencePackageStatus,
)

_SERIALIZER = DefaultDeterministicSerializer()


class EvidenceRegistryError(ValueError):
    """Raised when evidence governance invariants are violated."""


class InMemoryEvidenceRegistry:
    """Tenant-scoped registry; approved packages and evidence are immutable."""

    def __init__(self) -> None:
        self._items: dict[tuple[str, str, str], EvidenceItem] = {}
        self._source_index: dict[tuple[str, str, str, str], str] = {}
        self._packages: dict[tuple[str, str, str], EvidencePackage] = {}
        self._case_versions: dict[tuple[str, str, str], list[str]] = {}
        self._superseded_items: dict[tuple[str, str, str], str] = {}
        self._superseded_packages: dict[tuple[str, str, str], str] = {}

    def register_evidence(
        self, context: TenantContext, item: EvidenceItem
    ) -> EvidenceItem:
        context.assert_record_matches(item, "evidence item")
        key = self._item_key(context, item.evidence_id)
        if key in self._items:
            existing = self._items[key]
            if existing == item:
                return existing
            raise EvidenceRegistryError("evidence id is immutable")
        original = None
        if item.corrects_evidence_id:
            original = self.get_evidence(context, item.corrects_evidence_id)
            if self.is_evidence_superseded(context, original.evidence_id):
                raise EvidenceRegistryError("evidence is already superseded")
        source_key = (
            context.organization_id,
            context.tenant_id,
            item.source_system,
            item.source_identifier,
        )
        existing_id = self._source_index.get(source_key)
        if existing_id is not None:
            existing = self._items[self._item_key(context, existing_id)]
            if existing.evidence_hash == item.evidence_hash:
                return existing
            if item.corrects_evidence_id != existing.evidence_id:
                raise EvidenceRegistryError(
                    "conflicting source evidence requires an explicit correction"
                )
        if item.corrects_evidence_id:
            if original.source_system != item.source_system:
                raise EvidenceRegistryError("correction source must match original")
            self._superseded_items[
                self._item_key(context, original.evidence_id)
            ] = item.evidence_id
        self._items[key] = item
        self._source_index[source_key] = item.evidence_id
        return item

    def get_evidence(
        self, context: TenantContext, evidence_id: str
    ) -> EvidenceItem:
        try:
            return self._items[self._item_key(context, evidence_id)]
        except KeyError as exc:
            raise EvidenceRegistryError("evidence not found in tenant scope") from exc

    def is_evidence_superseded(
        self, context: TenantContext, evidence_id: str
    ) -> bool:
        return self._item_key(context, evidence_id) in self._superseded_items

    def evidence_successor(
        self, context: TenantContext, evidence_id: str
    ) -> str | None:
        return self._superseded_items.get(self._item_key(context, evidence_id))

    def create_package(
        self,
        context: TenantContext,
        *,
        package_id: str,
        case_id: str,
        evidence: tuple[CaseEvidence, ...],
        created_by: str,
        created_at: datetime | None = None,
        supersedes_package_id: str | None = None,
    ) -> EvidencePackage:
        key = self._package_key(context, package_id)
        if key in self._packages:
            raise EvidenceRegistryError("package id already exists")
        if not evidence:
            raise EvidenceRegistryError("evidence package cannot be empty")
        ids = [item.evidence_id for item in evidence]
        if len(ids) != len(set(ids)):
            raise EvidenceRegistryError("duplicate evidence reference in package")
        for evidence_id in ids:
            self.get_evidence(context, evidence_id)
            if self.is_evidence_superseded(context, evidence_id):
                raise EvidenceRegistryError("package cannot use superseded evidence")
        case_key = (context.organization_id, context.tenant_id, case_id)
        versions = self._case_versions.get(case_key, [])
        if supersedes_package_id:
            previous = self.get_package(context, supersedes_package_id)
            if previous.case_id != case_id:
                raise EvidenceRegistryError("superseded package must belong to same case")
            if previous.status is not EvidencePackageStatus.APPROVED:
                raise EvidenceRegistryError("only an approved package may be superseded")
            if self.is_package_superseded(context, previous.package_id):
                raise EvidenceRegistryError("package is already superseded")
        package = EvidencePackage(
            package_id=package_id,
            organization_id=context.organization_id,
            tenant_id=context.tenant_id,
            case_id=case_id,
            version=len(versions) + 1,
            status=EvidencePackageStatus.DRAFT,
            evidence=evidence,
            created_by=created_by,
            created_at=created_at or datetime.now(timezone.utc),
            supersedes_package_id=supersedes_package_id,
        )
        self._packages[key] = package
        self._case_versions.setdefault(case_key, []).append(package_id)
        return package

    def approve_package(
        self,
        context: TenantContext,
        package_id: str,
        *,
        approved_by: str,
        approved_at: datetime | None = None,
    ) -> EvidencePackage:
        package = self.get_package(context, package_id)
        if package.status is EvidencePackageStatus.APPROVED:
            raise EvidenceRegistryError("approved package is immutable")
        timestamp = approved_at or datetime.now(timezone.utc)
        content = {
            "package_id": package.package_id,
            "organization_id": package.organization_id,
            "tenant_id": package.tenant_id,
            "case_id": package.case_id,
            "version": package.version,
            "evidence": package.evidence,
            "supersedes_package_id": package.supersedes_package_id,
        }
        approved = replace(
            package,
            status=EvidencePackageStatus.APPROVED,
            approved_by=approved_by,
            approved_at=timestamp,
            package_hash=_SERIALIZER.content_hash(content),
        )
        self._packages[self._package_key(context, package_id)] = approved
        if approved.supersedes_package_id:
            self._superseded_packages[
                self._package_key(context, approved.supersedes_package_id)
            ] = approved.package_id
        return approved

    def get_package(
        self, context: TenantContext, package_id: str
    ) -> EvidencePackage:
        try:
            return self._packages[self._package_key(context, package_id)]
        except KeyError as exc:
            raise EvidenceRegistryError("package not found in tenant scope") from exc

    def case_history(
        self, context: TenantContext, case_id: str
    ) -> tuple[EvidencePackage, ...]:
        ids = self._case_versions.get(
            (context.organization_id, context.tenant_id, case_id), []
        )
        return tuple(self.get_package(context, package_id) for package_id in ids)

    def is_package_superseded(
        self, context: TenantContext, package_id: str
    ) -> bool:
        return self._package_key(context, package_id) in self._superseded_packages

    def package_successor(
        self, context: TenantContext, package_id: str
    ) -> str | None:
        return self._superseded_packages.get(self._package_key(context, package_id))

    @staticmethod
    def _item_key(context: TenantContext, evidence_id: str):
        return context.organization_id, context.tenant_id, evidence_id

    @staticmethod
    def _package_key(context: TenantContext, package_id: str):
        return context.organization_id, context.tenant_id, package_id
