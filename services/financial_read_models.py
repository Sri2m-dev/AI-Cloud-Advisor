"""Typed financial read models backed by governed P1 authority."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from auth.authenticated_tenant import AuthenticatedTenantContext
from services.enterprise_spend_service import EnterpriseSpendService


@dataclass(frozen=True, slots=True)
class FinancialReadValue:
    value: Decimal | None
    currency: str | None
    availability: str
    authority: str
    provenance: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class EnterpriseSpendReadModel:
    total: FinancialReadValue
    cloud: FinancialReadValue
    saas: FinancialReadValue
    msp: FinancialReadValue
    license: FinancialReadValue


def enterprise_spend_read_model(
    context: AuthenticatedTenantContext,
    spend_service: EnterpriseSpendService,
) -> EnterpriseSpendReadModel:
    posture = spend_service.get_financial_posture(context)
    provenance = tuple(str(value) for value in getattr(posture, "evidence_references", ()) if value)
    if not provenance and hasattr(spend_service, "get_financial_evidence"):
        provenance = tuple(
            dict.fromkeys(
                str(row["evidence_reference"])
                for row in spend_service.get_financial_evidence(context)
                if row.get("evidence_reference")
            )
        )
    availability = "AVAILABLE" if posture.has_data else "UNKNOWN"
    currency = posture.currency if posture.has_data else None
    contract_version = getattr(spend_service, "CONTRACT_VERSION", "pvt-003c1-v1")

    def known(value: Any) -> FinancialReadValue:
        return FinancialReadValue(
            value=Decimal(str(value)) if value is not None else None,
            currency=currency,
            availability=availability,
            authority=f"P1:{contract_version}",
            provenance=provenance,
        )

    def unknown() -> FinancialReadValue:
        return FinancialReadValue(
            value=None,
            currency=currency,
            availability="UNKNOWN",
            authority="P1",
            provenance=provenance,
        )

    return EnterpriseSpendReadModel(
        total=known(posture.total_ingested_spend) if posture.has_data else unknown(),
        cloud=known(posture.cloud_spend) if posture.has_data else unknown(),
        saas=unknown(),
        msp=unknown(),
        license=unknown(),
    )
