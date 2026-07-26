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

CUR_FIELD_ALIASES: dict[str, tuple[str, ...]] = {
    "payer_account_id": ("bill/PayerAccountId", "bill_payer_account_id"),
    "member_account_id": ("lineItem/UsageAccountId", "line_item_usage_account_id"),
    "billing_period_start": (
        "bill/BillingPeriodStartDate",
        "bill_billing_period_start_date",
    ),
    "billing_period_end": (
        "bill/BillingPeriodEndDate",
        "bill_billing_period_end_date",
    ),
    "usage_start": ("lineItem/UsageStartDate", "line_item_usage_start_date"),
    "usage_end": ("lineItem/UsageEndDate", "line_item_usage_end_date"),
    "service_name": (
        "product/ProductName",
        "product_servicecode",
    ),
    "product_code": ("lineItem/ProductCode", "line_item_product_code"),
    "region": ("product/regionCode", "product_region_code"),
    "availability_zone": (
        "lineItem/AvailabilityZone",
        "line_item_availability_zone",
    ),
    "resource_id": ("lineItem/ResourceId", "line_item_resource_id"),
    "usage_type": ("lineItem/UsageType", "line_item_usage_type"),
    "operation": ("lineItem/Operation", "line_item_operation"),
    "usage_quantity": ("lineItem/UsageAmount", "line_item_usage_amount"),
    "usage_unit": ("pricing/unit", "pricing_unit"),
    "line_item_type": ("lineItem/LineItemType", "line_item_line_item_type"),
    "unblended_cost": ("lineItem/UnblendedCost", "line_item_unblended_cost"),
    "blended_cost": ("lineItem/BlendedCost", "line_item_blended_cost"),
    "currency_code": ("lineItem/CurrencyCode", "line_item_currency_code"),
    "reservation_arn": (
        "reservation/ReservationARN",
        "reservation_reservation_a_r_n",
    ),
    "reservation_effective_cost": (
        "reservation/EffectiveCost",
        "reservation_effective_cost",
    ),
    "savings_plan_arn": (
        "savingsPlan/SavingsPlanARN",
        "savings_plan_savings_plan_a_r_n",
    ),
    "savings_plan_effective_cost": (
        "savingsPlan/SavingsPlanEffectiveCost",
        "savings_plan_savings_plan_effective_cost",
    ),
    "discount_amount": (
        "lineItem/DiscountedUsageAmount",
        "discount_total_discount",
    ),
    "credit_amount": ("lineItem/CreditAmount", "line_item_credit_amount"),
    "refund_amount": ("lineItem/RefundAmount", "line_item_refund_amount"),
    "tax_amount": ("lineItem/TaxAmount", "line_item_tax_amount"),
    "resource_tags": ("resourceTags/user", "resource_tags"),
}

REQUIRED_CUR_FIELDS = (
    "payer_account_id",
    "member_account_id",
    "billing_period_start",
    "billing_period_end",
    "usage_start",
    "usage_end",
    "service_name",
    "product_code",
    "line_item_type",
    "unblended_cost",
    "currency_code",
)


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


def canonical_header_map(headers: Iterable[str]) -> dict[str, str]:
    """Map explicit source aliases to internal fields and reject ambiguity."""
    alias_to_canonical = {
        alias: canonical
        for canonical, aliases in CUR_FIELD_ALIASES.items()
        for alias in aliases
    }
    resolved: dict[str, str] = {}
    for raw_header in headers:
        source_header = raw_header.lstrip("\ufeff").strip()
        canonical = alias_to_canonical.get(source_header)
        if canonical is None:
            continue
        if canonical in resolved:
            raise CurIngestionError(
                f"ambiguous CUR aliases for {canonical}: "
                f"{resolved[canonical]!r} and {source_header!r}"
            )
        resolved[canonical] = source_header
    return resolved


def detect_profile(headers: Iterable[str]) -> CurProfile:
    """Validate AWS CUR headers before financial facts are committed."""
    available = set(headers)
    missing = [field for field in REQUIRED_CUR_FIELDS if field not in available]
    if missing:
        raise CurIngestionError(f"CUR is missing required field: {missing[0]}")
    return CurProfile(
        payer="payer_account_id",
        member="member_account_id",
        billing_start="billing_period_start",
        billing_end="billing_period_end",
        usage_start="usage_start",
        usage_end="usage_end",
        service="service_name",
        product="product_code",
        line_item_type="line_item_type",
        unblended_cost="unblended_cost",
        currency="currency_code",
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


def _canonical_identity(row: Mapping[str, Any]) -> dict[str, str]:
    identity = {
        key: str(value)
        for key, value in row.items()
        if not key.startswith("__")
    }
    raw_fields = row.get("__raw_fields__", {})
    mapped_headers = set(row.get("__mapped_source_headers__", ()))
    identity.update(
        {
            f"raw:{header}": str(value)
            for header, value in raw_fields.items()
            if header not in mapped_headers
        }
    )
    return identity


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
) -> tuple[CurProfile, Iterator[list[dict[str, Any]]]]:
    if not DEFAULT_CHUNK_SIZE <= chunk_size <= MAX_CHUNK_SIZE:
        raise CurIngestionError(
            f"chunk_size must be between {DEFAULT_CHUNK_SIZE} and {MAX_CHUNK_SIZE}"
        )
    reader = csv.DictReader(_open_csv(source, filename))
    if not reader.fieldnames:
        raise CurIngestionError("CUR has no header row")
    header_map = canonical_header_map(reader.fieldnames)
    profile = detect_profile(header_map)

    def chunks() -> Iterator[list[dict[str, Any]]]:
        chunk: list[dict[str, Any]] = []
        for source_row in reader:
            raw_row = {
                (key or "").lstrip("\ufeff"): value or ""
                for key, value in source_row.items()
            }
            canonical_row = {
                canonical: raw_row.get(source_header, "")
                for canonical, source_header in header_map.items()
            }
            canonical_row["__raw_fields__"] = raw_row
            canonical_row["__mapped_source_headers__"] = tuple(header_map.values())
            chunk.append(canonical_row)
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
                    "\n".join(
                        json.dumps(_canonical_identity(row), sort_keys=True)
                        for row in chunk
                    ).encode()
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
        rows: list[dict[str, Any]],
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
            identity_row = _canonical_identity(row)
            source_key = _sha256(
                f"{import_id}:{part_id}:{offset}:"
                f"{json.dumps(identity_row, sort_keys=True)}".encode()
            )
            source_hash = _sha256(
                json.dumps(
                    identity_row,
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode()
            )
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
                    "region": row.get("region") or None,
                    "availability_zone": row.get("availability_zone") or None,
                    "resource_id": row.get("resource_id") or None,
                    "usage_type": row.get("usage_type") or None,
                    "operation": row.get("operation") or None,
                    "usage_quantity": row.get("usage_quantity") or None,
                    "usage_unit": row.get("usage_unit") or None,
                    "line_item_type": row[profile.line_item_type],
                    "currency_code": row[profile.currency],
                    "unblended_cost": str(
                        _decimal(row[profile.unblended_cost], profile.unblended_cost)
                    ),
                    "blended_cost": row.get("blended_cost") or None,
                    "reservation_arn": row.get("reservation_arn") or None,
                    "reservation_effective_cost": row.get("reservation_effective_cost") or None,
                    "savings_plan_arn": row.get("savings_plan_arn") or None,
                    "savings_plan_effective_cost": row.get("savings_plan_effective_cost")
                    or None,
                    "discount_amount": row.get("discount_amount") or None,
                    "credit_amount": row.get("credit_amount") or None,
                    "refund_amount": row.get("refund_amount") or None,
                    "tax_amount": row.get("tax_amount") or None,
                    "raw_fields": row["__raw_fields__"],
                    "source_evidence": {
                        "source_row_hash": source_hash,
                        "source_row_offset": offset,
                    },
                }
            )
        return facts, accepted, quarantined
