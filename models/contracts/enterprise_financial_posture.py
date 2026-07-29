"""Provider-neutral, Decimal-preserving enterprise financial posture."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any, Mapping

ZERO = Decimal("0")


def money(value: Any) -> Decimal:
    if value is None or value == "":
        return ZERO
    return value if isinstance(value, Decimal) else Decimal(str(value))


@dataclass(frozen=True, slots=True)
class EnterpriseFinancialPosture:
    organization_id: str
    currency: str
    period_start: date | None
    period_end: date | None
    generated_at: datetime
    import_count: int = 0
    latest_import_id: str | None = None
    latest_import_status: str | None = None
    source_rows: int = 0
    persisted_facts: int = 0
    total_ingested_spend: Decimal = ZERO
    cloud_spend: Decimal = ZERO
    resolved_spend: Decimal = ZERO
    quarantined_spend: Decimal = ZERO
    allocated_spend: Decimal = ZERO
    unallocated_resolved_spend: Decimal = ZERO
    reconciled_spend: Decimal = ZERO
    unreconciled_spend: Decimal = ZERO
    resolved_account_count: int = 0
    unknown_account_count: int = 0
    foreign_account_count: int = 0
    ambiguous_account_count: int = 0
    allocation_coverage_percentage: Decimal = ZERO
    reconciliation_status: str = "no_data"
    reconciliation_variance: Decimal = ZERO
    warnings: tuple[str, ...] = field(default_factory=tuple)
    contract_version: str = "pvt-003c1-v1"

    def __post_init__(self) -> None:
        for name in (
            "total_ingested_spend",
            "cloud_spend",
            "resolved_spend",
            "quarantined_spend",
            "allocated_spend",
            "unallocated_resolved_spend",
            "reconciled_spend",
            "unreconciled_spend",
            "allocation_coverage_percentage",
            "reconciliation_variance",
        ):
            object.__setattr__(self, name, money(getattr(self, name)))
        self.validate()

    def validate(self) -> None:
        if self.total_ingested_spend != self.resolved_spend + self.quarantined_spend:
            raise ValueError(
                "total_ingested_spend must equal resolved_spend plus quarantined_spend"
            )
        if self.resolved_spend != self.allocated_spend + self.unallocated_resolved_spend:
            raise ValueError(
                "resolved_spend must equal allocated_spend plus unallocated_resolved_spend"
            )
        if self.total_ingested_spend != self.reconciled_spend + self.unreconciled_spend:
            raise ValueError(
                "reconciled_spend plus unreconciled_spend must equal total_ingested_spend"
            )

    @property
    def has_data(self) -> bool:
        return self.persisted_facts > 0 or self.import_count > 0

    @classmethod
    def empty(
        cls, organization_id: str, *, warning: str | None = None
    ) -> "EnterpriseFinancialPosture":
        return cls(
            organization_id=organization_id,
            currency="USD",
            period_start=None,
            period_end=None,
            generated_at=datetime.now(timezone.utc),
            warnings=(warning,) if warning else (),
        )

    @classmethod
    def from_mapping(cls, row: Mapping[str, Any]) -> "EnterpriseFinancialPosture":
        generated = row.get("generated_at")
        if isinstance(generated, str):
            generated = datetime.fromisoformat(generated.replace("Z", "+00:00"))
        period_start = row.get("period_start")
        period_end = row.get("period_end")
        return cls(
            organization_id=str(row["organization_id"]),
            currency=str(row.get("currency") or "USD"),
            period_start=date.fromisoformat(period_start)
            if isinstance(period_start, str)
            else period_start,
            period_end=date.fromisoformat(period_end)
            if isinstance(period_end, str)
            else period_end,
            generated_at=generated or datetime.now(timezone.utc),
            import_count=int(row.get("import_count") or 0),
            latest_import_id=str(row["latest_import_id"]) if row.get("latest_import_id") else None,
            latest_import_status=row.get("latest_import_status"),
            source_rows=int(row.get("source_rows") or 0),
            persisted_facts=int(row.get("persisted_facts") or 0),
            total_ingested_spend=money(row.get("total_ingested_spend")),
            cloud_spend=money(row.get("cloud_spend")),
            resolved_spend=money(row.get("resolved_spend")),
            quarantined_spend=money(row.get("quarantined_spend")),
            allocated_spend=money(row.get("allocated_spend")),
            unallocated_resolved_spend=money(row.get("unallocated_resolved_spend")),
            reconciled_spend=money(row.get("reconciled_spend")),
            unreconciled_spend=money(row.get("unreconciled_spend")),
            resolved_account_count=int(row.get("resolved_account_count") or 0),
            unknown_account_count=int(row.get("unknown_account_count") or 0),
            foreign_account_count=int(row.get("foreign_account_count") or 0),
            ambiguous_account_count=int(row.get("ambiguous_account_count") or 0),
            allocation_coverage_percentage=money(row.get("allocation_coverage_percentage")),
            reconciliation_status=str(row.get("reconciliation_status") or "no_data"),
            reconciliation_variance=money(row.get("reconciliation_variance")),
            warnings=tuple(row.get("warnings") or ()),
        )
