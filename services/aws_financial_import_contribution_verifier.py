"""Offline proof boundary; evidence adapters, deployment and readiness are external.

Readers must independently observe source bytes, canonical rows, and projection
membership. Canonical reads must include ALL imports/facts for the query (including
inactive and supersession rows), without pagination omissions. Projection reads
must expose actual membership, not infer it from totals. Complete snapshots share
a consistent revision and identify the last successful tenant-scoped refresh.
These are new adapter requirements, not claims about deployed RPC capabilities.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, localcontext
from enum import StrEnum
from typing import Mapping, Protocol

from auth.authenticated_tenant import AuthenticatedTenantContext
from models.contracts.enterprise_financial_posture import EnterpriseFinancialPosture
from services.aws_financial_ingestion_orchestrator import AuthenticatedTenantVerifier
from services.demo_tenant_service import DEMO_ORGANIZATION_ID

Row = Mapping[str, object]
PRECISION = Decimal("0.0000000001")  # Canonical numeric(24, 10); no rounding allowed.
LIMIT = Decimal("100000000000000")


class ProofStatus(StrEnum):
    PASS = "PASS"
    PARTIAL = "PARTIAL"
    BLOCKED = "BLOCKED"
    FAILED = "FAILED"


@dataclass(frozen=True)
class ContributionResult:
    status: ProofStatus
    reasons: tuple[str, ...]
    verified_import_ids: tuple[str, ...] = ()
    verified_total: Decimal | None = None


@dataclass(frozen=True)
class DashboardQuery:
    currency: str
    period_start: date
    period_end: date
    spans_multiple_periods: bool = False


@dataclass(frozen=True)
class CanonicalEvidence:
    organization_id: str
    tenant_id: str
    query: DashboardQuery
    revision: str
    observed_at: datetime
    complete: bool
    imports: tuple[Row, ...]
    facts: tuple[Row, ...] | None
    reconciliations: tuple[Row, ...]


@dataclass(frozen=True)
class ProjectionEvidence:
    organization_id: str
    tenant_id: str
    query: DashboardQuery
    revision: str
    observed_at: datetime
    refreshed_at: datetime | None
    complete: bool
    contributions: tuple[Row, ...] | None
    included_fact_ids: tuple[str, ...] | None
    total: Decimal
    posture: EnterpriseFinancialPosture | None


class SourceReader(Protocol):
    def read_source(self, context: AuthenticatedTenantContext, import_id: str) -> Row | None:
        """Observe source identity, rows and cost independently of canonical totals."""
        ...


class CanonicalReader(Protocol):
    def read_canonical(
        self, context: AuthenticatedTenantContext, query: DashboardQuery
    ) -> CanonicalEvidence | None: ...


class ProjectionReader(Protocol):
    def read_projection(
        self, context: AuthenticatedTenantContext, query: DashboardQuery
    ) -> ProjectionEvidence | None: ...


class _ProofError(Exception):
    def __init__(self, status: ProofStatus, reason: str):
        self.status = status
        super().__init__(reason)


def _require(condition: bool, reason: str, status=ProofStatus.FAILED) -> None:
    if not condition:
        raise _ProofError(status, reason)


def _field(row: Row, name: str):
    value = row.get(name)
    _require(value is not None, f"missing evidence: {name}", ProofStatus.BLOCKED)
    return value


def _nullable(row: Row, name: str):
    _require(name in row, f"missing evidence: {name}", ProofStatus.BLOCKED)
    return row[name]


def _amount(value: object) -> Decimal:
    _require(isinstance(value, Decimal), "financial evidence must use Decimal")
    _require(value.is_finite(), "non-finite financial amount")
    with localcontext() as ctx:
        ctx.prec = 50
        _require(
            abs(value) < LIMIT and value == value.quantize(PRECISION),
            "amount exceeds numeric(24,10) precision",
        )
    return value


def _time(value: object) -> datetime:
    _require(
        isinstance(value, datetime) and value.utcoffset() is not None,
        "missing timezone-aware evidence timestamp",
        ProofStatus.BLOCKED,
    )
    return value


def _scope(context: AuthenticatedTenantContext, organization_id, tenant_id) -> None:
    _require(
        organization_id == context.organization_id and tenant_id == context.tenant_id,
        "cross-tenant evidence",
        ProofStatus.BLOCKED,
    )


def _row_scope(context: AuthenticatedTenantContext, row: Row) -> None:
    _scope(context, _field(row, "organization_id"), _field(row, "tenant_id"))


def _identity(row: Row) -> tuple:
    return tuple(
        _field(row, key)
        for key in (
            "import_id",
            "payer_account_id",
            "currency_code",
            "billing_period_start",
            "billing_period_end",
        )
    )


def _count(row: Row, key: str) -> int:
    value = _field(row, key)
    _require(type(value) is int and value >= 0, f"invalid count: {key}")
    return value


class AwsFinancialImportContributionVerifier:
    def __init__(
        self,
        *,
        tenant_verifier: AuthenticatedTenantVerifier,
        source_reader: SourceReader,
        canonical_reader: CanonicalReader,
        projection_reader: ProjectionReader,
    ):
        self._tenant_verifier = tenant_verifier
        self._source_reader = source_reader
        self._canonical_reader = canonical_reader
        self._projection_reader = projection_reader

    def verify(
        self,
        context: AuthenticatedTenantContext,
        import_ids: tuple[str, ...],
        query: DashboardQuery,
    ) -> ContributionResult:
        verified = []
        try:
            _require(
                isinstance(context, AuthenticatedTenantContext),
                "verified authenticated tenant context required",
                ProofStatus.BLOCKED,
            )
            _require(
                all(
                    x is not None
                    for x in (
                        self._tenant_verifier,
                        self._source_reader,
                        self._canonical_reader,
                        self._projection_reader,
                    )
                ),
                "missing injected evidence dependency",
                ProofStatus.BLOCKED,
            )
            try:
                authorized = self._tenant_verifier.verify(context)
            except Exception:
                authorized = False
            _require(
                authorized is True and context.organization_id != DEMO_ORGANIZATION_ID,
                "tenant verification failed or demo tenant",
                ProofStatus.BLOCKED,
            )
            _require(
                bool(import_ids) and all(isinstance(x, str) and x for x in import_ids),
                "explicit import IDs required",
                ProofStatus.BLOCKED,
            )
            _require(len(set(import_ids)) == len(import_ids), "duplicate requested import")
            _require(
                isinstance(query, DashboardQuery)
                and re.fullmatch(r"[A-Z]{3}", query.currency) is not None
                and type(query.period_start) is date
                and type(query.period_end) is date
                and query.period_start <= query.period_end
                and type(query.spans_multiple_periods) is bool,
                "invalid dashboard query",
            )
            try:
                sources = tuple(self._source_reader.read_source(context, x) for x in import_ids)
                canonical = self._canonical_reader.read_canonical(context, query)
                projection = self._projection_reader.read_projection(context, query)
            except Exception as exc:
                raise _ProofError(
                    ProofStatus.BLOCKED, f"evidence reader unavailable ({type(exc).__name__})"
                ) from exc
            _require(
                all(x is not None for x in sources)
                and isinstance(canonical, CanonicalEvidence)
                and isinstance(projection, ProjectionEvidence),
                "missing source/canonical/projection evidence",
                ProofStatus.BLOCKED,
            )
            for snapshot in (canonical, projection):
                _scope(context, snapshot.organization_id, snapshot.tenant_id)
                _require(
                    snapshot.complete is True and bool(snapshot.revision),
                    "incomplete evidence snapshot",
                    ProofStatus.BLOCKED,
                )
                _require(snapshot.query == query, "dashboard query evidence mismatch")
                _time(snapshot.observed_at)
            _require(
                canonical.revision == projection.revision,
                "inconsistent snapshot revisions",
                ProofStatus.BLOCKED,
            )
            _require(
                canonical.facts is not None
                and projection.contributions is not None
                and projection.included_fact_ids is not None,
                "missing independent fact or projection membership evidence",
                ProofStatus.BLOCKED,
            )
            refreshed = _time(projection.refreshed_at)
            _require(
                refreshed <= canonical.observed_at <= projection.observed_at,
                "inconsistent snapshot/refresh chronology",
                ProofStatus.PARTIAL,
            )
            imports = self._index(context, canonical.imports)
            recons = self._index(context, canonical.reconciliations)
            projected = self._index(context, projection.contributions)
            expected_ids = set(import_ids)
            _require(
                set(imports) == expected_ids
                and set(recons) == expected_ids
                and set(projected) == expected_ids,
                "missing or unexpected import membership",
                ProofStatus.BLOCKED,
            )
            facts_by_import = {x: [] for x in import_ids}
            fact_ids, row_keys = set(), set()
            for fact in canonical.facts:
                _row_scope(context, fact)
                iid = _field(fact, "import_id")
                _require(iid in expected_ids, "unexpected fact import", ProofStatus.BLOCKED)
                fid = _field(fact, "cloud_cost_fact_id")
                row_key = _field(fact, "source_row_key")
                _require(
                    isinstance(fid, str)
                    and bool(fid)
                    and isinstance(row_key, str)
                    and bool(row_key),
                    "missing fact provenance",
                    ProofStatus.BLOCKED,
                )
                _require(
                    fid not in fact_ids and row_key not in row_keys,
                    "duplicate persisted fact identity",
                )
                fact_ids.add(fid)
                row_keys.add(row_key)
                _require(
                    _field(fact, "fact_status") == "active"
                    and _nullable(fact, "supersedes_fact_id") is None,
                    "quarantined/rejected/superseded fact",
                    ProofStatus.PARTIAL,
                )
                facts_by_import[iid].append(fact)
            source_keys = set()
            total = Decimal(0)
            with localcontext() as ctx:
                ctx.prec = 50
                for iid, source in zip(import_ids, sources, strict=True):
                    _row_scope(context, source)
                    imported, recon, contribution = imports[iid], recons[iid], projected[iid]
                    identity = _identity(source)
                    _require(
                        identity[0] == iid
                        and all(
                            _identity(x) == identity
                            for x in (imported, recon, contribution, *facts_by_import[iid])
                        ),
                        "import/currency/period/payer identity mismatch",
                    )
                    start, end = identity[3:]
                    _require(
                        type(start) is date and type(end) is date and start <= end,
                        "invalid source billing period",
                    )
                    _require(
                        identity[2] == query.currency
                        and (
                            (query.period_start <= start <= end <= query.period_end)
                            if query.spans_multiple_periods
                            else (start == query.period_start and end == query.period_end)
                        ),
                        "currency or billing period incompatible with dashboard query",
                    )
                    sha = _field(source, "source_file_sha256")
                    _require(
                        isinstance(sha, str) and re.fullmatch(r"[0-9a-f]{64}", sha) is not None,
                        "invalid source hash",
                    )
                    _require(_field(imported, "source_file_sha256") == sha, "source hash mismatch")
                    key = (identity[1], sha)
                    _require(key not in source_keys, "duplicate source contribution")
                    source_keys.add(key)
                    _require(
                        _field(imported, "status") == "completed"
                        and _nullable(imported, "supersedes_import_id") is None,
                        "nonterminal or superseded import",
                        ProofStatus.PARTIAL,
                    )
                    for row in (imported, recon):
                        _require(
                            _count(row, "duplicate_row_count") == 0
                            and _count(row, "rejected_row_count") == 0,
                            "duplicate or rejected contribution",
                            ProofStatus.PARTIAL,
                        )
                    _require(
                        _field(recon, "status") == "reconciled"
                        and _amount(_field(recon, "variance_amount")) == 0,
                        "reconciliation failed or nonzero variance",
                        ProofStatus.PARTIAL,
                    )
                    _require(
                        max(
                            _time(_field(imported, "completed_at")),
                            _time(_field(recon, "reconciled_at")),
                            *(_time(_field(f, "ingested_at")) for f in facts_by_import[iid]),
                        )
                        <= refreshed,
                        "stale projection",
                        ProofStatus.PARTIAL,
                    )
                    count = _count(source, "source_row_count")
                    _require(
                        count > 0
                        and len(facts_by_import[iid]) == count
                        and _count(imported, "source_row_count") == count
                        and _count(imported, "accepted_row_count") == count
                        and _count(recon, "source_row_count") == count
                        and _count(recon, "normalized_row_count") == count
                        and _count(contribution, "persisted_facts") == count,
                        "persisted/source/projected row count mismatch",
                    )
                    for fact in facts_by_import[iid]:
                        _require(
                            re.fullmatch(r"[0-9a-f]{64}", _field(fact, "source_row_hash"))
                            is not None,
                            "missing fact hash provenance",
                            ProofStatus.BLOCKED,
                        )
                    _require(
                        len({_field(f, "source_row_hash") for f in facts_by_import[iid]}) == count,
                        "duplicate source-row hash",
                    )
                    amount = _amount(_field(source, "source_cost_total"))
                    persisted = sum(
                        (_amount(_field(f, "unblended_cost")) for f in facts_by_import[iid]),
                        Decimal(0),
                    )
                    _require(
                        persisted == amount
                        and all(
                            _amount(_field(row, field)) == amount
                            for row, field in (
                                (imported, "source_cost_total"),
                                (imported, "normalized_cost_total"),
                                (recon, "source_cost_total"),
                                (recon, "normalized_cost_total"),
                                (contribution, "total_unblended_spend"),
                            )
                        ),
                        "independent contribution amounts mismatch",
                    )
                    verified.append(iid)
                    total += amount
                _require(
                    len(projection.included_fact_ids) == len(fact_ids)
                    and set(projection.included_fact_ids) == fact_ids,
                    "projection fact membership mismatch",
                )
                _require(_amount(projection.total) == total, "incorrect aggregate total")
                posture = projection.posture
                _require(
                    isinstance(posture, EnterpriseFinancialPosture),
                    "missing canonical dashboard posture",
                    ProofStatus.BLOCKED,
                )
                _require(
                    posture.organization_id == context.organization_id,
                    "cross-tenant dashboard posture",
                    ProofStatus.BLOCKED,
                )
                _require(
                    posture.currency == query.currency
                    and posture.period_start == min(_identity(x)[3] for x in sources)
                    and posture.period_end == max(_identity(x)[4] for x in sources)
                    and posture.import_count == len(import_ids)
                    and posture.latest_import_id in expected_ids
                    and posture.latest_import_status == "completed"
                    and posture.source_rows == len(fact_ids)
                    and posture.persisted_facts == len(fact_ids),
                    "dashboard identity/period/count mismatch",
                )
                _require(
                    refreshed <= _time(posture.generated_at) <= projection.observed_at,
                    "stale dashboard posture",
                    ProofStatus.PARTIAL,
                )
                _require(
                    posture.reconciliation_status == "reconciled"
                    and all(
                        _amount(x) == 0
                        for x in (
                            posture.reconciliation_variance,
                            posture.unreconciled_spend,
                            posture.quarantined_spend,
                        )
                    )
                    and not (
                        posture.unknown_account_count
                        or posture.foreign_account_count
                        or posture.ambiguous_account_count
                    ),
                    "unresolved dashboard posture",
                    ProofStatus.PARTIAL,
                )
                _require(
                    all(
                        _amount(x) == total
                        for x in (
                            posture.total_ingested_spend,
                            posture.cloud_spend,
                            posture.resolved_spend,
                            posture.reconciled_spend,
                        )
                    ),
                    "canonical dashboard amount mismatch",
                )
            return ContributionResult(
                ProofStatus.PASS, ("offline contribution proof verified",), tuple(verified), total
            )
        except _ProofError as exc:
            return ContributionResult(exc.status, (str(exc),), tuple(verified))
        except Exception as exc:
            return ContributionResult(
                ProofStatus.FAILED, (f"malformed evidence ({type(exc).__name__})",), tuple(verified)
            )

    @staticmethod
    def _index(context, rows):
        indexed = {}
        for row in rows:
            _row_scope(context, row)
            iid = _field(row, "import_id")
            _require(
                isinstance(iid, str) and bool(iid), "missing import identity", ProofStatus.BLOCKED
            )
            _require(iid not in indexed, "duplicate import evidence")
            indexed[iid] = row
        return indexed
