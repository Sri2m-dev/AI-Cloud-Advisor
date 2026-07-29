"""Canonical enterprise financial data fabric service."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from threading import RLock
from time import monotonic
from typing import Any

from auth.authenticated_tenant import AuthenticatedTenantContext
from models.contracts.enterprise_financial_posture import EnterpriseFinancialPosture
from repositories.enterprise_spend_repository import EnterpriseSpendRepository


class EnterpriseSpendService:
    CONTRACT_VERSION = "pvt-003c1-v1"

    def __init__(
        self, repository: EnterpriseSpendRepository, *, cache_ttl_seconds: int = 60
    ) -> None:
        self._repository = repository
        self._cache_ttl = max(0, int(cache_ttl_seconds))
        self._cache: dict[tuple[Any, ...], tuple[float, EnterpriseFinancialPosture]] = {}
        self._lock = RLock()

    def _key(
        self,
        context: AuthenticatedTenantContext,
        period_start: date | None,
        period_end: date | None,
        currency: str,
    ) -> tuple[Any, ...]:
        return (
            context.organization_id,
            context.tenant_id,
            context.authorization_scope,
            period_start,
            period_end,
            currency,
            self.CONTRACT_VERSION,
        )

    def get_financial_posture(
        self,
        context: AuthenticatedTenantContext,
        period: tuple[date | None, date | None] | None = None,
        *,
        currency: str = "USD",
    ) -> EnterpriseFinancialPosture:
        start, end = period or (None, None)
        key = self._key(context, start, end, currency)
        now = monotonic()
        with self._lock:
            cached = self._cache.get(key)
            if cached and now - cached[0] <= self._cache_ttl:
                return cached[1]
        row = self._repository.get_posture(context, start, end)
        posture = (
            EnterpriseFinancialPosture.from_mapping(row)
            if row
            else EnterpriseFinancialPosture.empty(context.organization_id)
        )
        if posture.currency != currency and posture.has_data:
            raise ValueError("currency conversion is not available for canonical posture")
        with self._lock:
            self._cache[key] = (now, posture)
        return posture

    def get_spend_by_service(
        self,
        context: AuthenticatedTenantContext,
        period: tuple[date | None, date | None] | None = None,
    ):
        start, end = period or (None, None)
        return self._repository.get_spend_by_service(context, start, end)

    def get_unknown_account_posture(
        self,
        context: AuthenticatedTenantContext,
        period: tuple[date | None, date | None] | None = None,
        *,
        payer_id: str | None = None,
    ):
        start, end = period or (None, None)
        rows = self._repository.get_account_posture(context, start, end)
        return tuple(
            row
            for row in rows
            if row.get("mapping_status") != "resolved"
            and (payer_id is None or row.get("payer_account_id") == payer_id)
        )

    def get_import_history(self, context: AuthenticatedTenantContext):
        return self._repository.get_import_history(context)

    def get_reconciliation_status(
        self,
        context: AuthenticatedTenantContext,
        import_id: str | None = None,
    ) -> dict[str, Any]:
        posture = self.get_financial_posture(context)
        if import_id and posture.latest_import_id != import_id:
            for row in self.get_import_history(context):
                if str(row.get("import_id")) == import_id:
                    return {
                        "status": row.get("reconciliation_status"),
                        "variance": Decimal(str(row.get("reconciliation_variance") or 0)),
                    }
            return {"status": "not_found", "variance": Decimal("0")}
        return {
            "status": posture.reconciliation_status,
            "variance": posture.reconciliation_variance,
        }

    def invalidate(self, organization_id: str | None = None) -> None:
        with self._lock:
            if organization_id is None:
                self._cache.clear()
            else:
                self._cache = {
                    key: value for key, value in self._cache.items() if key[0] != organization_id
                }
