"""Canonical record validation."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Sequence

from connector_normalization.canonical_models import CanonicalEnterpriseRecord, CanonicalCostRecord


@dataclass(frozen=True)
class CanonicalValidationIssue:
    record_id: str
    field: str
    message: str
    severity: str = "error"


@dataclass(frozen=True)
class CanonicalValidationResult:
    valid: bool
    issues: tuple[CanonicalValidationIssue, ...] = field(default_factory=tuple)


class CanonicalValidator:
    """Validates canonical records before publishing."""

    def validate(self, records: Sequence[CanonicalEnterpriseRecord]) -> CanonicalValidationResult:
        issues: list[CanonicalValidationIssue] = []
        seen_ids: set[str] = set()

        for record in records:
            self._required(record, "record_id", record.record_id, issues)
            self._required(record, "source_system", record.source_system, issues)
            self._required(record, "source_id", record.source_id, issues)
            self._required(record, "name", record.name, issues)

            if record.record_id in seen_ids:
                issues.append(CanonicalValidationIssue(record.record_id, "record_id", "Duplicate canonical record ID."))
            seen_ids.add(record.record_id)

            if not isinstance(record.observed_at, datetime):
                issues.append(CanonicalValidationIssue(record.record_id, "observed_at", "Observed timestamp must be a datetime."))

            if isinstance(record, CanonicalCostRecord) and record.currency.upper() != record.currency:
                issues.append(CanonicalValidationIssue(record.record_id, "currency", "Currency must be normalized to uppercase ISO code."))

            for key, value in record.tags.items():
                if not isinstance(key, str) or not isinstance(value, str):
                    issues.append(CanonicalValidationIssue(record.record_id, "tags", "Tags must be normalized string key/value pairs."))

            if not record.provider_metadata:
                issues.append(CanonicalValidationIssue(record.record_id, "provider_metadata", "Provider metadata is recommended for lineage.", severity="warning"))

        return CanonicalValidationResult(
            valid=not any(issue.severity == "error" for issue in issues),
            issues=tuple(issues),
        )

    def _required(self, record: CanonicalEnterpriseRecord, field: str, value: object, issues: list[CanonicalValidationIssue]) -> None:
        if value is None or value == "":
            issues.append(CanonicalValidationIssue(record.record_id or "unknown", field, "Required field is missing."))
