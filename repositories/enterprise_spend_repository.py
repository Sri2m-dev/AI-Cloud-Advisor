"""Tenant-required repositories for canonical cloud financial projections."""

from __future__ import annotations

from datetime import date
from typing import Any, Mapping

from auth.authenticated_tenant import AuthenticatedTenantContext


class EnterpriseSpendRepository:
    """Call guarded database aggregations; intentionally has no unscoped API."""

    def __init__(self, client: Any) -> None:
        self._client = client

    @staticmethod
    def _params(
        context: AuthenticatedTenantContext,
        period_start: date | None = None,
        period_end: date | None = None,
    ) -> dict[str, Any]:
        if not isinstance(context, AuthenticatedTenantContext):
            raise TypeError("AuthenticatedTenantContext is required")
        return {
            "requested_organization_id": context.organization_id,
            "requested_period_start": period_start.isoformat() if period_start else None,
            "requested_period_end": period_end.isoformat() if period_end else None,
        }

    @staticmethod
    def _rows(response: Any) -> tuple[Mapping[str, Any], ...]:
        data = getattr(response, "data", None) or ()
        return (data,) if isinstance(data, Mapping) else tuple(data)

    def get_posture(
        self,
        context: AuthenticatedTenantContext,
        period_start: date | None = None,
        period_end: date | None = None,
    ) -> Mapping[str, Any] | None:
        rows = self._rows(
            self._client.rpc(
                "tenant_cloud_financial_posture",
                self._params(context, period_start, period_end),
            ).execute()
        )
        return rows[0] if rows else None

    def get_spend_by_service(
        self,
        context: AuthenticatedTenantContext,
        period_start: date | None = None,
        period_end: date | None = None,
    ) -> tuple[Mapping[str, Any], ...]:
        return self._rows(
            self._client.rpc(
                "tenant_cloud_service_spend",
                self._params(context, period_start, period_end),
            ).execute()
        )

    def get_account_posture(
        self,
        context: AuthenticatedTenantContext,
        period_start: date | None = None,
        period_end: date | None = None,
    ) -> tuple[Mapping[str, Any], ...]:
        return self._rows(
            self._client.rpc(
                "tenant_cloud_account_posture",
                self._params(context, period_start, period_end),
            ).execute()
        )

    def get_account_classification_evidence(
        self, context: AuthenticatedTenantContext, account_id: str
    ) -> tuple[Mapping[str, Any], ...]:
        if not isinstance(context, AuthenticatedTenantContext):
            raise TypeError("AuthenticatedTenantContext is required")
        return self._rows(
            self._client.rpc(
                "tenant_cloud_account_classification_evidence",
                {
                    "requested_organization_id": context.organization_id,
                    "requested_account_id": account_id,
                },
            ).execute()
        )

    def get_accounts_classification_evidence(
        self, context: AuthenticatedTenantContext, account_ids
    ) -> tuple[Mapping[str, Any], ...]:
        if not isinstance(context, AuthenticatedTenantContext):
            raise TypeError("AuthenticatedTenantContext is required")
        return self._rows(
            self._client.rpc(
                "tenant_cloud_accounts_classification_evidence",
                {
                    "requested_organization_id": context.organization_id,
                    "requested_account_ids": list(account_ids),
                },
            ).execute()
        )

    def get_import_history(
        self,
        context: AuthenticatedTenantContext,
    ) -> tuple[Mapping[str, Any], ...]:
        if not isinstance(context, AuthenticatedTenantContext):
            raise TypeError("AuthenticatedTenantContext is required")
        return self._rows(
            self._client.rpc(
                "tenant_cloud_import_history",
                {"requested_organization_id": context.organization_id},
            ).execute()
        )
