"""Bounded, tenant-safe AWS CUR ingestion on the PVT-003A persistence model.

This module deliberately contains no browser-facing write path and does not
propagate data into financial marts (PVT-003C).
"""

from __future__ import annotations

import csv
import gzip
import hashlib
import io
import itertools
import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from pathlib import Path
from typing import Any, BinaryIO, Iterable, Iterator, Mapping, Protocol

from data_fabric.foundation import TenantContext
from data_fabric.foundation.exceptions import (
    DataFabricTenantBoundaryError,
    DataFabricValidationError,
)

DEFAULT_CHUNK_SIZE = 10_000
MAX_CHUNK_SIZE = 25_000


class CurIngestionError(DataFabricValidationError):
    """A malformed or unsafe CUR cannot be ingested."""


class CurState(StrEnum):
    RECEIVED = "received"
    VALIDATING = "validating"
    AWAITING_ACCOUNT_RESOLUTION = "quarantined"
    PROCESSING = "processing"
    PARTIAL = "failed"
    RECONCILING = "reconciling"
    COMPLETED = "completed"
    FAILED = "failed"
    SUPERSEDED = "superseded"


@dataclass(frozen=True, slots=True)
class CurProfile:
    payer: str
    member: str
    billing_start: str
    billing_end: str
    usage_start: str
    usage_end: str
    service: str
    product: str
    line_item_type: str
    unblended_cost: str
    currency: str


@dataclass(frozen=True, slots=True)
class AccountMapping:
    organization_id: str
    tenant_id: str
    payer_account_id: str
    account_id: str
    status: str


@dataclass(frozen=True, slots=True)
class CurImportResult:
    import_id: str
    status: CurState
    source_rows: int
    accepted_rows: int
    quarantined_rows: int
    duplicate_rows: int
    normalized_total: Decimal
    replayed: bool = False


class CurPersistence(Protocol):
    """Service-role persistence boundary; implementations must enforce scope."""

    def find_import(
        self, context: TenantContext, payer: str, file_hash: str
    ) -> Mapping[str, Any] | None: ...
    def list_account_mappings(self, context: TenantContext) -> Iterable[AccountMapping]: ...
    def create_import(self, context: TenantContext, payload: Mapping[str, Any]) -> None: ...
    def update_import(
        self, context: TenantContext, import_id: str, payload: Mapping[str, Any]
    ) -> None: ...
    def create_part(self, context: TenantContext, payload: Mapping[str, Any]) -> None: ...
    def update_part(
        self, context: TenantContext, part_id: str, payload: Mapping[str, Any]
    ) -> None: ...
    def write_facts(self, context: TenantContext, facts: list[Mapping[str, Any]]) -> int: ...
    def upsert_reconciliation(self, context: TenantContext, payload: Mapping[str, Any]) -> None: ...


def _column(headers: Iterable[str], *names: str) -> str:
    available = {header.strip(): header for header in headers}
    for name in names:
        if name in available:
            return available[name]
    raise CurIngestionError(f"CUR is missing required field: {names[0]}")


def detect_profile(headers: Iterable[str]) -> CurProfile:
    """Validate AWS CUR headers before financial facts are committed."""
    headers = tuple(headers)
    return CurProfile(
        payer=_column(headers, "bill/PayerAccountId"),
        member=_column(headers, "lineItem/UsageAccountId"),
        billing_start=_column(headers, "bill/BillingPeriodStartDate"),
        billing_end=_column(headers, "bill/BillingPeriodEndDate"),
        usage_start=_column(headers, "lineItem/UsageStartDate"),
        usage_end=_column(headers, "lineItem/UsageEndDate"),
        service=_column(headers, "product/ProductName", "lineItem/ProductCode"),
        product=_column(headers, "lineItem/ProductCode", "product/productName"),
        line_item_type=_column(headers, "lineItem/LineItemType"),
        unblended_cost=_column(headers, "lineItem/UnblendedCost"),
        currency=_column(headers, "lineItem/CurrencyCode"),
    )


def _parse_timestamp(value: str) -> datetime:
    value = value.strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise CurIngestionError(f"invalid CUR timestamp: {value!r}") from exc
    return parsed.replace(tzinfo=parsed.tzinfo or timezone.utc).astimezone(timezone.utc)


def _decimal(value: str, field: str) -> Decimal:
    try:
        return Decimal(value or "0")
    except InvalidOperation as exc:
        raise CurIngestionError(f"invalid decimal in {field}: {value!r}") from exc


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def file_sha256(source: BinaryIO) -> str:
    """Hash a seekable upload in fixed-size blocks without retaining its data."""
    if not source.seekable():
        raise CurIngestionError("CUR upload must be seekable for deterministic hashing")
    digest = hashlib.sha256()
    while block := source.read(1024 * 1024):
        digest.update(block)
    source.seek(0)
    return digest.hexdigest()


def _open_csv(source: BinaryIO, filename: str) -> io.TextIOBase:
    lower = filename.lower()
    if lower.endswith(".csv.gz") or lower.endswith(".gz"):
        return io.TextIOWrapper(gzip.GzipFile(fileobj=source), encoding="utf-8-sig", newline="")
    if lower.endswith(".csv"):
        return io.TextIOWrapper(source, encoding="utf-8-sig", newline="")
    raise CurIngestionError("unsupported CUR format; only .csv and .csv.gz are accepted")


def iter_cur_chunks(
    source: BinaryIO, filename: str, chunk_size: int = DEFAULT_CHUNK_SIZE
) -> tuple[CurProfile, Iterator[list[dict[str, str]]]]:
    if not DEFAULT_CHUNK_SIZE <= chunk_size <= MAX_CHUNK_SIZE:
        raise CurIngestionError(
            f"chunk_size must be between {DEFAULT_CHUNK_SIZE} and {MAX_CHUNK_SIZE}"
        )
    reader = csv.DictReader(_open_csv(source, filename))
    if not reader.fieldnames:
        raise CurIngestionError("CUR has no header row")
    profile = detect_profile(reader.fieldnames)

    def chunks() -> Iterator[list[dict[str, str]]]:
        chunk: list[dict[str, str]] = []
        for row in reader:
            chunk.append({key: value or "" for key, value in row.items()})
            if len(chunk) == chunk_size:
                yield chunk
                chunk = []
        if chunk:
            yield chunk

    return profile, chunks()


class AwsCurIngestionEngine:
    def __init__(
        self, persistence: CurPersistence, *, chunk_size: int = DEFAULT_CHUNK_SIZE
    ) -> None:
        self._persistence = persistence
        self._chunk_size = chunk_size

    def ingest(
        self,
        context: TenantContext,
        source: BinaryIO,
        filename: str,
        *,
        source_uri: str | None = None,
        supersedes_import_id: str | None = None,
    ) -> CurImportResult:
        if not isinstance(context, TenantContext):
            raise CurIngestionError("TenantContext is required")
        file_hash = file_sha256(source)
        profile, chunks = iter_cur_chunks(source, filename, self._chunk_size)
        # Profile detection occurs before an import row/fact is created.
        first_chunk = next(chunks, None)
        if not first_chunk:
            raise CurIngestionError("CUR has no data rows")
        payer = first_chunk[0].get(profile.payer, "").strip()
        if not payer:
            raise CurIngestionError("CUR payer account is empty")
        period_start = _parse_timestamp(first_chunk[0][profile.billing_start]).date()
        period_end = _parse_timestamp(first_chunk[0][profile.billing_end]).date()
        if period_end < period_start:
            raise CurIngestionError("CUR billing period end precedes start")
        existing = self._persistence.find_import(context, payer, file_hash)
        if existing and existing["status"] in {
            CurState.COMPLETED.value,
            CurState.AWAITING_ACCOUNT_RESOLUTION.value,
        }:
            return CurImportResult(
                str(existing["import_id"]),
                CurState(existing["status"]),
                0,
                0,
                0,
                0,
                Decimal("0"),
                replayed=True,
            )

        import_id = str(existing["import_id"]) if existing else str(uuid.uuid4())
        import_key = _sha256(
            f"{context.organization_id}:{context.tenant_id}:{payer}:{file_hash}".encode()
        )
        import_payload = {
                "import_id": import_id,
                "organization_id": context.organization_id,
                "tenant_id": context.tenant_id,
                "import_key": import_key,
                "payer_account_id": payer,
                "billing_period_start": str(period_start),
                "billing_period_end": str(period_end),
                "source_file_name": filename,
                "source_file_sha256": file_hash,
                "source_uri": source_uri,
                "compression": "gzip" if filename.lower().endswith(".gz") else "csv",
                "parser_profile": "aws-cur-v1",
                "status": CurState.VALIDATING.value,
                "supersedes_import_id": supersedes_import_id,
                "source_evidence": {"file_sha256": file_hash},
        }
        if existing:
            self._persistence.update_import(
                context,
                import_id,
                {"status": CurState.VALIDATING.value, "failure_code": None, "failure_detail": None},
            )
        else:
            self._persistence.create_import(context, import_payload)
        try:
            mappings = tuple(self._persistence.list_account_mappings(context))
            self._validate_mapping_scope(context, mappings)
            accepted = quarantined = duplicates = source_rows = 0
            normalized_total = Decimal("0")
            all_chunks = itertools.chain((first_chunk,), chunks)
            for number, chunk in enumerate(all_chunks, start=1):
                part_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"{import_id}:part:{number}"))
                part_hash = _sha256(
                    "\n".join(json.dumps(row, sort_keys=True) for row in chunk).encode()
                )
                self._persistence.create_part(
                    context,
                    {
                        "import_part_id": part_id,
                        "organization_id": context.organization_id,
                        "tenant_id": context.tenant_id,
                        "import_id": import_id,
                        "part_key": f"{import_key}:{number}",
                        "part_name": f"{Path(filename).name}.part-{number}",
                        "part_sha256": part_hash,
                        "row_start": source_rows + 1,
                        "row_end": source_rows + len(chunk),
                        "checkpoint_row": source_rows,
                        "status": "processing",
                    },
                )
                facts, part_accepted, part_quarantined = self._normalise_chunk(
                    context, import_id, part_id, chunk, profile, payer, mappings
                )
                written = self._persistence.write_facts(context, facts)
                duplicates += len(facts) - written
                accepted += part_accepted
                quarantined += part_quarantined
                source_rows += len(chunk)
                normalized_total += sum(
                    (Decimal(str(f["unblended_cost"] or 0)) for f in facts), Decimal("0")
                )
                self._persistence.update_part(
                    context,
                    part_id,
                    {
                        "checkpoint_row": source_rows,
                        "accepted_row_count": part_accepted,
                        "rejected_row_count": part_quarantined,
                        "duplicate_row_count": len(facts) - written,
                        "status": "completed",
                    },
                )
            status = CurState.AWAITING_ACCOUNT_RESOLUTION if quarantined else CurState.RECONCILING
            self._persistence.update_import(
                context,
                import_id,
                {
                    "status": status.value,
                    "source_row_count": source_rows,
                    "accepted_row_count": accepted,
                    "rejected_row_count": quarantined,
                    "duplicate_row_count": duplicates,
                    "source_cost_total": str(normalized_total),
                    "normalized_cost_total": str(normalized_total),
                },
            )
            self._persistence.upsert_reconciliation(
                context,
                {
                    "cloud_cost_reconciliation_id": str(uuid.uuid4()),
                    "organization_id": context.organization_id,
                    "tenant_id": context.tenant_id,
                    "import_id": import_id,
                    "billing_period_start": str(period_start),
                    "billing_period_end": str(period_end),
                    "payer_account_id": payer,
                    "source_row_count": source_rows,
                    "normalized_row_count": accepted + quarantined,
                    "rejected_row_count": quarantined,
                    "duplicate_row_count": duplicates,
                    "source_cost_total": str(normalized_total),
                    "normalized_cost_total": str(normalized_total),
                    "currency_code": first_chunk[0][profile.currency],
                    "status": "quarantined" if quarantined else "reconciled",
                    "evidence": {"parser_profile": "aws-cur-v1"},
                },
            )
            final = CurState.AWAITING_ACCOUNT_RESOLUTION if quarantined else CurState.COMPLETED
            self._persistence.update_import(
                context,
                import_id,
                {"status": final.value, "completed_at": datetime.now(timezone.utc).isoformat()},
            )
            return CurImportResult(
                import_id, final, source_rows, accepted, quarantined, duplicates, normalized_total
            )
        except Exception as exc:
            self._persistence.update_import(
                context,
                import_id,
                {
                    "status": CurState.FAILED.value,
                    "failure_code": type(exc).__name__,
                    "failure_detail": str(exc),
                },
            )
            raise

    @staticmethod
    def _validate_mapping_scope(context: TenantContext, mappings: Iterable[AccountMapping]) -> None:
        for mapping in mappings:
            if (
                mapping.organization_id != context.organization_id
                or mapping.tenant_id != context.tenant_id
            ):
                raise DataFabricTenantBoundaryError("account mapping crosses tenant boundary")

    def _normalise_chunk(
        self,
        context: TenantContext,
        import_id: str,
        part_id: str,
        rows: list[dict[str, str]],
        profile: CurProfile,
        payer: str,
        mappings: tuple[AccountMapping, ...],
    ) -> tuple[list[dict[str, Any]], int, int]:
        owned = {mapping.account_id: mapping for mapping in mappings if mapping.status == "active"}
        facts: list[dict[str, Any]] = []
        accepted = quarantined = 0
        for offset, row in enumerate(rows):
            if row[profile.payer].strip() != payer:
                raise CurIngestionError("mixed-payer CUR is rejected")
            member = row[profile.member].strip()
            account_known = payer in owned and member in owned
            fact_status = "active" if account_known else "quarantined"
            accepted += int(account_known)
            quarantined += int(not account_known)
            usage_start, usage_end = (
                _parse_timestamp(row[profile.usage_start]),
                _parse_timestamp(row[profile.usage_end]),
            )
            billing_start, billing_end = (
                _parse_timestamp(row[profile.billing_start]).date(),
                _parse_timestamp(row[profile.billing_end]).date(),
            )
            source_key = _sha256(
                f"{import_id}:{part_id}:{offset}:{json.dumps(row, sort_keys=True)}".encode()
            )
            source_hash = _sha256(json.dumps(row, sort_keys=True, separators=(",", ":")).encode())
            facts.append(
                {
                    "cloud_cost_fact_id": str(
                        uuid.uuid5(uuid.NAMESPACE_URL, f"{import_id}:{part_id}:{source_hash}")
                    ),
                    "organization_id": context.organization_id,
                    "tenant_id": context.tenant_id,
                    "import_id": import_id,
                    "import_part_id": part_id,
                    "source_row_key": source_key,
                    "source_row_hash": source_hash,
                    "fact_status": fact_status,
                    "payer_account_id": payer,
                    "member_account_id": member,
                    "billing_period_start": str(billing_start),
                    "billing_period_end": str(billing_end),
                    "usage_start_at": usage_start.isoformat(),
                    "usage_end_at": usage_end.isoformat(),
                    "service_name": row[profile.service],
                    "product_code": row[profile.product],
                    "line_item_type": row[profile.line_item_type],
                    "currency_code": row[profile.currency],
                    "unblended_cost": str(
                        _decimal(row[profile.unblended_cost], profile.unblended_cost)
                    ),
                    "blended_cost": row.get("lineItem/BlendedCost") or None,
                    "reservation_arn": row.get("reservation/ReservationARN") or None,
                    "reservation_effective_cost": row.get("reservation/EffectiveCost") or None,
                    "savings_plan_arn": row.get("savingsPlan/SavingsPlanARN") or None,
                    "savings_plan_effective_cost": row.get("savingsPlan/SavingsPlanEffectiveCost")
                    or None,
                    "discount_amount": row.get("lineItem/DiscountedUsageAmount") or None,
                    "credit_amount": row.get("lineItem/CreditAmount") or None,
                    "refund_amount": row.get("lineItem/RefundAmount") or None,
                    "tax_amount": row.get("lineItem/TaxAmount") or None,
                    "raw_fields": row,
                    "source_evidence": {
                        "source_row_hash": source_hash,
                        "source_row_offset": offset,
                    },
                }
            )
        return facts, accepted, quarantined
