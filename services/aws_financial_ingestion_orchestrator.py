"""Offline-only, dependency-injected AWS CUR integration boundary.

Production composition must provide independently verified identity, account
ownership, persistence, reconciliation, projection-refresh, and dashboard
dependencies. This module never creates infrastructure clients or AWS sessions.
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal
from enum import StrEnum
from typing import TYPE_CHECKING, BinaryIO, Iterable, Mapping, Protocol

from auth.authenticated_tenant import AuthenticatedTenantContext
from data_fabric.foundation import TenantContext
from models.contracts.enterprise_financial_posture import EnterpriseFinancialPosture
from services.aws_cur_ingestion_engine import (
    AccountMapping,
    AwsCurIngestionEngine,
    CurImportResult,
    CurIngestionError,
    CurState,
    file_sha256,
    iter_cur_chunks,
)

if TYPE_CHECKING:
    from services.aws_financial_import_contribution_verifier import (
        AwsFinancialImportContributionVerifier,
        CanonicalEvidence,
        DashboardQuery,
        ProjectionEvidence,
    )


class IngestionGate(StrEnum):
    SOURCE_VALIDATED = "SOURCE_VALIDATED"
    PERSISTENCE_COMPLETED = "PERSISTENCE_COMPLETED"
    RECONCILIATION_VERIFIED = "RECONCILIATION_VERIFIED"
    PROJECTION_REFRESHED = "PROJECTION_REFRESHED"
    CONTRIBUTIONS_VERIFIED = "CONTRIBUTIONS_VERIFIED"
    DASHBOARD_READY = "DASHBOARD_READY"
    PARTIAL = "PARTIAL"
    BLOCKED = "BLOCKED"
    FAILED = "FAILED"


@dataclass(frozen=True, slots=True)
class SourceEvidence:
    source_sha256: str
    payer_account_id: str
    source_rows: int
    source_total: Decimal
    currency_code: str
    billing_period_start: date
    billing_period_end: date


@dataclass(frozen=True, slots=True)
class ReconciliationEvidence:
    organization_id: str
    tenant_id: str
    import_id: str
    source_sha256: str
    source_rows: int
    persisted_rows: int
    source_total: Decimal
    persisted_total: Decimal
    currency_code: str


@dataclass(frozen=True, slots=True)
class ProjectionRefreshEvidence:
    organization_id: str
    tenant_id: str
    import_id: str
    refreshed_at: datetime


@dataclass(frozen=True, slots=True)
class AwsFinancialIngestionResult:
    gate: IngestionGate
    completed_gates: tuple[IngestionGate, ...]
    reason: str | None
    import_id: str | None = None
    source_sha256: str | None = None
    source_rows: int = 0
    persisted_rows: int = 0
    quarantined_rows: int = 0
    currency_code: str | None = None
    dashboard_generated_at: datetime | None = None
    verified_import_ids: tuple[str, ...] = ()
    verified_total: Decimal | None = None


class AuthenticatedTenantVerifier(Protocol):
    def verify(self, context: AuthenticatedTenantContext) -> bool: ...


class AwsAccountOwnershipAuthority(Protocol):
    def list_account_mappings(self, context: TenantContext) -> Iterable[AccountMapping]: ...


class CurPersistenceAdapter(Protocol):
    def find_import(
        self, context: TenantContext, payer: str, file_hash: str
    ) -> Mapping[str, object] | None: ...
    def create_import(self, context: TenantContext, payload: Mapping[str, object]) -> None: ...
    def update_import(
        self, context: TenantContext, import_id: str, payload: Mapping[str, object]
    ) -> None: ...
    def create_part(self, context: TenantContext, payload: Mapping[str, object]) -> None: ...
    def update_part(
        self, context: TenantContext, part_id: str, payload: Mapping[str, object]
    ) -> None: ...
    def write_facts(self, context: TenantContext, facts: list[Mapping[str, object]]) -> int: ...
    def upsert_reconciliation(
        self, context: TenantContext, payload: Mapping[str, object]
    ) -> None: ...


class IndependentReconciliationAuthority(Protocol):
    def verify(
        self,
        context: AuthenticatedTenantContext,
        import_id: str,
        source: BinaryIO,
        evidence: SourceEvidence,
    ) -> ReconciliationEvidence: ...


class TenantProjectionRefresher(Protocol):
    def refresh(
        self, context: AuthenticatedTenantContext, import_id: str
    ) -> ProjectionRefreshEvidence: ...


class CanonicalDashboardReader(Protocol):
    def invalidate(self, organization_id: str) -> None: ...
    def get_financial_posture(
        self, context: AuthenticatedTenantContext, *, currency: str
    ) -> EnterpriseFinancialPosture: ...


@dataclass(frozen=True, slots=True)
class ImportContributionEvidence:
    """Captured independent evidence, never synthesized from dashboard totals.

    The provider must use the NXR-DASH-06 complete, consistent read contracts.
    No production provider exists here. These bound readers let the unchanged
    verifier validate exactly the bundle tied to this orchestration attempt.
    """

    sources: Mapping[str, Mapping[str, object]]
    canonical: CanonicalEvidence | None
    projection: ProjectionEvidence | None

    def read_source(self, _context, import_id):
        return self.sources.get(import_id)

    def read_canonical(self, _context, _query):
        return self.canonical

    def read_projection(self, _context, _query):
        return self.projection


class ImportContributionEvidenceProvider(Protocol):
    def read(
        self,
        context: AuthenticatedTenantContext,
        import_ids: tuple[str, ...],
        query: DashboardQuery,
    ) -> ImportContributionEvidence | None: ...


class _ContributionReadinessError(ValueError):
    """Safe, boundary-generated reason suitable for the structured result."""


class _ScopedCurPersistence:
    """Bind engine mapping reads to the separately injected ownership authority."""

    def __init__(
        self,
        persistence: CurPersistenceAdapter,
        mappings: tuple[AccountMapping, ...],
    ) -> None:
        self._persistence = persistence
        self._mappings = mappings

    def find_import(self, context, payer, file_hash):
        return self._persistence.find_import(context, payer, file_hash)

    def list_account_mappings(self, _context):
        return self._mappings

    def create_import(self, context, payload):
        self._persistence.create_import(context, payload)

    def update_import(self, context, import_id, payload):
        self._persistence.update_import(context, import_id, payload)

    def create_part(self, context, payload):
        self._persistence.create_part(context, payload)

    def update_part(self, context, part_id, payload):
        self._persistence.update_part(context, part_id, payload)

    def write_facts(self, context, facts):
        return self._persistence.write_facts(context, facts)

    def upsert_reconciliation(self, context, payload):
        self._persistence.upsert_reconciliation(context, payload)


class AwsFinancialIngestionOrchestrator:
    def __init__(
        self,
        *,
        tenant_verifier: AuthenticatedTenantVerifier,
        account_ownership: AwsAccountOwnershipAuthority,
        persistence: CurPersistenceAdapter,
        reconciler: IndependentReconciliationAuthority,
        projection_refresher: TenantProjectionRefresher,
        dashboard: CanonicalDashboardReader,
        contribution_verifier: type[AwsFinancialImportContributionVerifier] | None = None,
        evidence_provider: ImportContributionEvidenceProvider | None = None,
    ) -> None:
        dependencies = {
            "tenant_verifier": tenant_verifier,
            "account_ownership": account_ownership,
            "persistence": persistence,
            "reconciler": reconciler,
            "projection_refresher": projection_refresher,
            "dashboard": dashboard,
        }
        missing = [name for name, dependency in dependencies.items() if dependency is None]
        if missing:
            raise ValueError(f"required offline integration dependency missing: {missing[0]}")
        self._tenant_verifier = tenant_verifier
        self._account_ownership = account_ownership
        self._persistence = persistence
        self._reconciler = reconciler
        self._projection_refresher = projection_refresher
        self._dashboard = dashboard
        self._contribution_verifier = contribution_verifier
        self._evidence_provider = evidence_provider

    def ingest(
        self,
        context: AuthenticatedTenantContext,
        source: BinaryIO,
        filename: str,
        *,
        organization_id_override: str | None = None,
        source_uri: str | None = None,
        supersedes_import_id: str | None = None,
        prior_import_ids: tuple[str, ...] | None = None,
        dashboard_query: DashboardQuery | None = None,
    ) -> AwsFinancialIngestionResult:
        if not isinstance(context, AuthenticatedTenantContext):
            return self._result(
                IngestionGate.BLOCKED,
                "verified authenticated tenant context is required",
            )
        if organization_id_override is not None:
            return self._result(
                IngestionGate.BLOCKED,
                "caller-provided organization overrides are not accepted",
            )
        try:
            if self._tenant_verifier.verify(context) is not True:
                return self._result(
                    IngestionGate.BLOCKED,
                    "authenticated tenant verification failed",
                )
        except Exception as exc:
            return self._result(
                IngestionGate.BLOCKED,
                f"authenticated tenant verification failed ({type(exc).__name__})",
            )

        try:
            source_evidence = self._validate_source(source, filename)
        except Exception as exc:
            return self._result(
                IngestionGate.FAILED,
                f"CUR source validation failed ({type(exc).__name__})",
            )

        completed = [IngestionGate.SOURCE_VALIDATED]
        if context.organization_id == _demo_organization_id():
            return self._result(
                IngestionGate.BLOCKED,
                "live CUR ingestion is disabled for the synthetic demo organization",
                completed=completed,
                source=source_evidence,
            )

        tenant_context = context.fabric_context
        try:
            mappings = tuple(self._account_ownership.list_account_mappings(tenant_context))
            self._validate_mapping_scope(tenant_context, mappings)
        except Exception as exc:
            return self._result(
                IngestionGate.BLOCKED,
                f"account ownership could not be verified ({type(exc).__name__})",
                completed=completed,
                source=source_evidence,
            )

        try:
            source.seek(0)
            imported = AwsCurIngestionEngine(
                _ScopedCurPersistence(self._persistence, mappings)
            ).ingest(
                tenant_context,
                source,
                filename,
                source_uri=source_uri,
                supersedes_import_id=supersedes_import_id,
            )
        except Exception as exc:
            return self._result(
                IngestionGate.PARTIAL,
                f"CUR persistence did not complete ({type(exc).__name__}); "
                "partial writes are possible",
                completed=completed,
                source=source_evidence,
            )

        if imported.source_rows <= 0 or imported.status not in {
            CurState.COMPLETED,
            CurState.AWAITING_ACCOUNT_RESOLUTION,
        }:
            return self._result(
                IngestionGate.PARTIAL,
                "CUR persistence did not reach a terminal persisted state",
                completed=completed,
                source=source_evidence,
                imported=imported,
            )

        completed.append(IngestionGate.PERSISTENCE_COMPLETED)
        if imported.quarantined_rows:
            return self._result(
                IngestionGate.PARTIAL,
                "account ownership is unresolved; quarantined costs are excluded "
                "from dashboard readiness",
                completed=completed,
                source=source_evidence,
                imported=imported,
            )

        try:
            independent = self._reconciler.verify(
                context, imported.import_id, source, source_evidence
            )
            self._validate_reconciliation(context, imported.import_id, source_evidence, independent)
        except Exception as exc:
            return self._result(
                IngestionGate.PARTIAL,
                f"independent source-to-persisted reconciliation failed ({type(exc).__name__})",
                completed=completed,
                source=source_evidence,
                imported=imported,
            )
        completed.append(IngestionGate.RECONCILIATION_VERIFIED)

        try:
            refreshed = self._projection_refresher.refresh(context, imported.import_id)
            self._validate_refresh(context, imported.import_id, refreshed)
        except Exception as exc:
            return self._result(
                IngestionGate.PARTIAL,
                f"tenant-scoped financial projection refresh failed ({type(exc).__name__})",
                completed=completed,
                source=source_evidence,
                imported=imported,
            )
        completed.append(IngestionGate.PROJECTION_REFRESHED)

        verified_ids, verified_total = (), None
        try:
            self._dashboard.invalidate(context.organization_id)
            posture = self._dashboard.get_financial_posture(
                context, currency=source_evidence.currency_code
            )
            if (
                prior_import_ids is not None
                or dashboard_query is not None
                or posture.import_count > 1
            ):
                verified_ids, verified_total = self._verify_contributions(
                    context,
                    imported.import_id,
                    source_evidence,
                    refreshed,
                    posture,
                    prior_import_ids,
                    dashboard_query,
                )
                completed.append(IngestionGate.CONTRIBUTIONS_VERIFIED)
            else:
                self._validate_dashboard(
                    context, imported.import_id, source_evidence, refreshed, posture
                )
        except Exception as exc:
            return self._result(
                IngestionGate.PARTIAL,
                "canonical dashboard posture is not fresh and ready: "
                + (
                    str(exc) if isinstance(exc, _ContributionReadinessError) else type(exc).__name__
                ),
                completed=completed,
                source=source_evidence,
                imported=imported,
            )
        completed.append(IngestionGate.DASHBOARD_READY)
        return self._result(
            IngestionGate.DASHBOARD_READY,
            None,
            completed=completed,
            source=source_evidence,
            imported=imported,
            dashboard_generated_at=posture.generated_at,
            verified_import_ids=verified_ids,
            verified_total=verified_total,
        )

    def _verify_contributions(
        self,
        context,
        import_id,
        source,
        refresh,
        posture,
        prior_import_ids,
        query,
    ) -> tuple[tuple[str, ...], Decimal]:
        # Local import avoids the verifier's existing AuthenticatedTenantVerifier
        # import cycle. The verifier implementation and its contracts stay intact.
        from services.aws_financial_import_contribution_verifier import (
            ContributionResult,
            DashboardQuery,
            ProjectionEvidence,
            ProofStatus,
        )

        if self._contribution_verifier is None or self._evidence_provider is None:
            raise _ContributionReadinessError(
                "import contribution verifier/evidence provider unavailable"
            )
        if (
            not isinstance(prior_import_ids, tuple)
            or any(not isinstance(iid, str) or not iid for iid in prior_import_ids)
            or not isinstance(query, DashboardQuery)
        ):
            raise _ContributionReadinessError(
                "explicit prior import IDs and dashboard query required"
            )
        # Current identity comes from persistence, prior identities from the caller;
        # no membership is inferred from totals or latest-import metadata.
        import_ids = (*prior_import_ids, import_id)
        if len(set(import_ids)) != len(import_ids):
            raise _ContributionReadinessError("duplicate import membership")
        evidence = self._evidence_provider.read(context, import_ids, query)
        if not isinstance(evidence, ImportContributionEvidence):
            raise _ContributionReadinessError("complete captured contribution evidence required")
        current = evidence.sources.get(import_id)
        if current is None or any(
            current.get(key) != value
            for key, value in {
                "organization_id": context.organization_id,
                "tenant_id": context.tenant_id,
                "import_id": import_id,
                "payer_account_id": source.payer_account_id,
                "source_file_sha256": source.source_sha256,
                "source_row_count": source.source_rows,
                "source_cost_total": source.source_total,
                "currency_code": source.currency_code,
                "billing_period_start": source.billing_period_start,
                "billing_period_end": source.billing_period_end,
            }.items()
        ):
            raise _ContributionReadinessError(
                "current import evidence does not match validated source"
            )
        projection = evidence.projection
        if (
            not isinstance(projection, ProjectionEvidence)
            or projection.refreshed_at != refresh.refreshed_at
            or projection.posture != posture
            or posture.latest_import_id != import_id
        ):
            raise _ContributionReadinessError(
                "contribution proof does not match refresh receipt/dashboard read"
            )
        verifier = self._contribution_verifier(
            tenant_verifier=self._tenant_verifier,
            source_reader=evidence,
            canonical_reader=evidence,
            projection_reader=evidence,
        )
        proof = verifier.verify(context, import_ids, query)
        if (
            not isinstance(proof, ContributionResult)
            or proof.status is not ProofStatus.PASS
            or proof.verified_import_ids != import_ids
            or proof.verified_total is None
        ):
            reasons = proof.reasons if isinstance(proof, ContributionResult) else ("invalid proof",)
            raise _ContributionReadinessError(f"import contribution proof failed: {reasons}")
        return proof.verified_import_ids, proof.verified_total

    @staticmethod
    def _result(
        gate: IngestionGate,
        reason: str | None,
        *,
        completed: Iterable[IngestionGate] = (),
        source: SourceEvidence | None = None,
        imported: CurImportResult | None = None,
        dashboard_generated_at: datetime | None = None,
        verified_import_ids: tuple[str, ...] = (),
        verified_total: Decimal | None = None,
    ) -> AwsFinancialIngestionResult:
        return AwsFinancialIngestionResult(
            gate=gate,
            completed_gates=tuple(completed),
            reason=reason,
            import_id=imported.import_id if imported else None,
            source_sha256=source.source_sha256 if source else None,
            source_rows=source.source_rows if source else 0,
            persisted_rows=imported.accepted_rows + imported.quarantined_rows if imported else 0,
            quarantined_rows=imported.quarantined_rows if imported else 0,
            currency_code=source.currency_code if source else None,
            dashboard_generated_at=dashboard_generated_at,
            verified_import_ids=verified_import_ids,
            verified_total=verified_total,
        )

    @staticmethod
    def _validate_source(source: BinaryIO, filename: str) -> SourceEvidence:
        source_hash = file_sha256(source)
        profile, chunks = iter_cur_chunks(source, filename)
        try:
            first = next(chunks, None)
            if not first:
                raise CurIngestionError("CUR has no data rows")
            payer = first[0][profile.payer].strip()
            if not payer:
                raise CurIngestionError("CUR payer account is empty")
            period = (
                _parse_cur_datetime(first[0][profile.billing_start]).date(),
                _parse_cur_datetime(first[0][profile.billing_end]).date(),
            )
            if period[1] < period[0]:
                raise CurIngestionError("CUR billing period end precedes start")
            currency = _validated_currency(first[0][profile.currency])
            total = Decimal("0")
            rows_seen = 0
            for chunk in itertools.chain((first,), chunks):
                for row in chunk:
                    if row[profile.payer].strip() != payer:
                        raise CurIngestionError("mixed-payer CUR is rejected")
                    row_period = (
                        _parse_cur_datetime(row[profile.billing_start]).date(),
                        _parse_cur_datetime(row[profile.billing_end]).date(),
                    )
                    if row_period != period:
                        raise CurIngestionError("mixed CUR billing periods are rejected")
                    if _validated_currency(row[profile.currency]) != currency:
                        raise CurIngestionError("mixed CUR currencies are rejected")
                    _parse_cur_datetime(row[profile.usage_start])
                    _parse_cur_datetime(row[profile.usage_end])
                    cost = Decimal(row[profile.unblended_cost] or "0")
                    if not cost.is_finite():
                        raise CurIngestionError("CUR cost must be finite")
                    total += cost
                    rows_seen += 1
        finally:
            chunks.close()
        source.seek(0)
        return SourceEvidence(
            source_sha256=source_hash,
            payer_account_id=payer,
            source_rows=rows_seen,
            source_total=total,
            currency_code=currency,
            billing_period_start=period[0],
            billing_period_end=period[1],
        )

    @staticmethod
    def _validate_mapping_scope(
        context: TenantContext, mappings: tuple[AccountMapping, ...]
    ) -> None:
        for mapping in mappings:
            if (
                mapping.organization_id != context.organization_id
                or mapping.tenant_id != context.tenant_id
            ):
                raise PermissionError("account ownership authority crossed tenant scope")

    @staticmethod
    def _validate_reconciliation(
        context: AuthenticatedTenantContext,
        import_id: str,
        source: SourceEvidence,
        evidence: ReconciliationEvidence,
    ) -> None:
        if (
            not isinstance(evidence, ReconciliationEvidence)
            or evidence.organization_id != context.organization_id
            or evidence.tenant_id != context.tenant_id
            or evidence.import_id != import_id
            or evidence.source_sha256 != source.source_sha256
            or evidence.source_rows != source.source_rows
            or evidence.persisted_rows != source.source_rows
            or evidence.source_total != source.source_total
            or evidence.persisted_total != source.source_total
            or evidence.currency_code != source.currency_code
        ):
            raise ValueError("independent reconciliation evidence does not match the import")

    @staticmethod
    def _validate_refresh(
        context: AuthenticatedTenantContext,
        import_id: str,
        evidence: ProjectionRefreshEvidence,
    ) -> None:
        if (
            not isinstance(evidence, ProjectionRefreshEvidence)
            or evidence.organization_id != context.organization_id
            or evidence.tenant_id != context.tenant_id
            or evidence.import_id != import_id
            or evidence.refreshed_at.tzinfo is None
        ):
            raise ValueError("projection refresh evidence is not tenant/import scoped")

    @staticmethod
    def _validate_dashboard(
        context: AuthenticatedTenantContext,
        import_id: str,
        source: SourceEvidence,
        refresh: ProjectionRefreshEvidence,
        posture: EnterpriseFinancialPosture,
    ) -> None:
        if (
            not isinstance(posture, EnterpriseFinancialPosture)
            or posture.organization_id != context.organization_id
            or posture.latest_import_id != import_id
            or posture.latest_import_status != CurState.COMPLETED.value
            # Aggregate postures cannot prove which import contributed each value.
            # Until an import-scoped canonical contract exists, fail closed.
            or posture.import_count != 1
            or posture.currency != source.currency_code
            or posture.period_start != source.billing_period_start
            or posture.period_end != source.billing_period_end
            or posture.source_rows != source.source_rows
            or posture.persisted_facts != source.source_rows
            or posture.total_ingested_spend != source.source_total
            or posture.cloud_spend != source.source_total
            or posture.resolved_spend != source.source_total
            or posture.reconciled_spend != source.source_total
            or not posture.has_data
            or posture.reconciliation_status != "reconciled"
            or posture.reconciliation_variance != 0
            or posture.unreconciled_spend != 0
            or posture.quarantined_spend != 0
            or posture.unknown_account_count
            or posture.foreign_account_count
            or posture.ambiguous_account_count
            or posture.generated_at.tzinfo is None
            or posture.generated_at < refresh.refreshed_at
        ):
            raise ValueError("canonical tenant posture is absent, unresolved, or stale")


def _demo_organization_id() -> str:
    from services.demo_tenant_service import DEMO_ORGANIZATION_ID

    return DEMO_ORGANIZATION_ID


def _validated_currency(value: str) -> str:
    currency = value.strip().upper()
    if len(currency) != 3 or not currency.isascii() or not currency.isalpha():
        raise CurIngestionError("invalid CUR currency code")
    return currency


def _parse_cur_datetime(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError as exc:
        raise CurIngestionError("invalid CUR timestamp") from exc
    return parsed.replace(tzinfo=parsed.tzinfo or timezone.utc).astimezone(timezone.utc)
