"""Canonical RPC boundary; capabilities come only from an external approved issuer.

No client creation, credential lookup, grant issuance or source attestation occurs here.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, Mapping
from uuid import UUID

from auth.authenticated_tenant import AuthenticatedTenantContext
from services.aws_financial_import_contribution_verifier import DashboardQuery
from services.demo_tenant_service import DEMO_ORGANIZATION_ID


class FinancialEvidenceUnavailable(ValueError):
    """Evidence cannot be certified; callers must show NOT_READY."""


@dataclass(frozen=True)
class FinancialOperation:
    context: AuthenticatedTenantContext
    import_ids: tuple[str, ...]
    query: DashboardQuery
    permission: str
    trigger_import_id: str | None = None
    request_id: str | None = None
    expected_previous_generation_id: str | None = None


class AwsFinancialEvidenceRepository:
    def __init__(self, client: Any, *, grant_provider: Callable | None = None):
        self._client = client
        self._grant_provider = grant_provider

    def _params(self, operation: FinancialOperation):
        context, ids, query = operation.context, operation.import_ids, operation.query
        if not isinstance(context, AuthenticatedTenantContext):
            raise TypeError("authenticated tenant required")
        if context.organization_id == DEMO_ORGANIZATION_ID:
            raise FinancialEvidenceUnavailable("demo evidence cannot certify AWS spend")
        UUID(context.user_id)
        if not ids or len(set(ids)) != len(ids):
            raise FinancialEvidenceUnavailable("explicit unique import coverage required")
        for iid in ids:
            UUID(iid)
        if self._grant_provider is None:
            raise PermissionError("D1/D7 approved grant issuer is unavailable")
        grant_id = str(UUID(str(self._grant_provider(operation))))
        return {
            "organization_id": context.organization_id,
            "tenant_id": context.tenant_id,
            "import_ids": list(ids),
            "currency": query.currency,
            "period_start": query.period_start.isoformat(),
            "period_end": query.period_end.isoformat(),
            "spanning_periods": query.spans_multiple_periods,
            "authorization_grant_id": grant_id,
        }

    @staticmethod
    def _object(response):
        data = response.data
        if isinstance(data, list) and len(data) == 1:
            data = data[0]
        if not isinstance(data, Mapping):
            raise FinancialEvidenceUnavailable("RPC object missing")
        return dict(data)

    def read(self, context, import_ids, query):
        op = FinancialOperation(context, import_ids, query, "read")
        value = self._object(
            self._client.rpc(
                "read_aws_financial_contribution_evidence_v1", self._params(op)
            ).execute()
        )
        if (value.get("organization_id"), value.get("tenant_id")) != (
            context.organization_id,
            context.tenant_id,
        ):
            raise FinancialEvidenceUnavailable("cross-tenant evidence response")
        if value.get("completeness") != "COMPLETE":
            raise FinancialEvidenceUnavailable("canonical evidence incomplete or stale")
        return value

    def refresh(
        self,
        context,
        import_ids,
        query,
        *,
        trigger_import_id,
        request_id,
        expected_previous_generation_id=None,
    ):
        op = FinancialOperation(
            context,
            import_ids,
            query,
            "refresh",
            trigger_import_id,
            request_id,
            expected_previous_generation_id,
        )
        params = self._params(op)
        params.update(
            trigger_import_id=trigger_import_id,
            request_id=request_id,
            expected_previous_generation_id=expected_previous_generation_id,
        )
        receipt = self._object(
            self._client.rpc("refresh_tenant_cloud_financial_projections_v2", params).execute()
        )
        for key, expected in {
            "organization_id": context.organization_id,
            "tenant_id": context.tenant_id,
            "request_id": request_id,
            "trigger_import_id": trigger_import_id,
            "currency": query.currency,
            "period_start": query.period_start.isoformat(),
            "period_end": query.period_end.isoformat(),
            "spanning_periods": query.spans_multiple_periods,
        }.items():
            if receipt.get(key) != expected:
                raise FinancialEvidenceUnavailable("refresh receipt identity mismatch")
        if receipt.get("is_current") is not True or set(receipt.get("import_ids", ())) != set(
            import_ids
        ):
            raise FinancialEvidenceUnavailable("receipt is superseded or coverage mismatches")
        UUID(receipt["generation_id"])
        stamp = datetime.fromisoformat(receipt["published_at"].replace("Z", "+00:00"))
        if stamp.tzinfo is None:
            raise FinancialEvidenceUnavailable("receipt lacks publication timezone")
        return receipt


class PostgresFinancialRpcClient:
    """DB-API transport with enforced transaction isolation and confirmed commit.

    The backend supplies an already approved connection factory. No environment URLs,
    passwords or implicit Supabase connections are discovered. This transport does
    not provision roles, bypass RLS or replace the database's authority denial.
    """

    def __init__(self, connection_factory, *, max_attempts=3):
        self._factory = connection_factory
        self._attempts = max(1, min(3, int(max_attempts)))

    def rpc(self, name, params):
        from types import SimpleNamespace

        signatures = {
            "read_aws_financial_contribution_evidence_v1": {
                "organization_id",
                "tenant_id",
                "import_ids",
                "currency",
                "period_start",
                "period_end",
                "spanning_periods",
                "authorization_grant_id",
            },
            "refresh_tenant_cloud_financial_projections_v2": {
                "organization_id",
                "tenant_id",
                "import_ids",
                "currency",
                "period_start",
                "period_end",
                "spanning_periods",
                "authorization_grant_id",
                "trigger_import_id",
                "request_id",
                "expected_previous_generation_id",
            },
        }
        if name not in signatures or set(params) != signatures[name]:
            raise ValueError("unsupported financial RPC signature")
        bound = dict(params)

        def execute():
            import psycopg2
            from psycopg2 import sql

            refresh = name == "refresh_tenant_cloud_financial_projections_v2"
            for attempt in range(self._attempts):
                connection = self._factory()
                try:
                    connection.set_session(
                        isolation_level="SERIALIZABLE" if refresh else "REPEATABLE READ",
                        readonly=not refresh,
                    )
                    with connection:
                        with connection.cursor() as cursor:
                            statement = sql.SQL("select public.{}({})").format(
                                sql.Identifier(name),
                                sql.SQL(",").join(
                                    sql.SQL(
                                        "{} => %s" + ("::uuid[]" if k == "import_ids" else "")
                                    ).format(sql.Identifier(k))
                                    for k in bound
                                ),
                            )
                            cursor.execute(statement, list(bound.values()))
                            result = cursor.fetchone()[0]
                    # Context manager committed successfully before result escapes.
                    return SimpleNamespace(data=result)
                except (psycopg2.errors.SerializationFailure, psycopg2.errors.DeadlockDetected):
                    if attempt + 1 == self._attempts:
                        raise
                finally:
                    connection.close()
            raise RuntimeError("financial RPC retry exhausted")

        return SimpleNamespace(execute=execute)
