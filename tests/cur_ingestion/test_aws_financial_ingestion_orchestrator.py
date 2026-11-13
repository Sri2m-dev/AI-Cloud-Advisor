import csv
import io
from dataclasses import replace
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

import pytest

from auth.authenticated_tenant import AuthenticatedTenantContext
from data_fabric.foundation import TenantContext
from models.contracts.enterprise_financial_posture import EnterpriseFinancialPosture
from services.aws_cur_ingestion_engine import AccountMapping
from services.aws_financial_import_contribution_verifier import (
    AwsFinancialImportContributionVerifier,
    CanonicalEvidence,
    DashboardQuery,
    ProjectionEvidence,
)
from services.aws_financial_ingestion_orchestrator import (
    AwsFinancialIngestionOrchestrator,
    ImportContributionEvidence,
    IngestionGate,
    ProjectionRefreshEvidence,
    ReconciliationEvidence,
)
from services.demo_tenant_service import DEMO_ORGANIZATION_ID

ORG_A = str(uuid4())
ORG_B = str(uuid4())
HEADERS = (
    "bill/PayerAccountId",
    "lineItem/UsageAccountId",
    "bill/BillingPeriodStartDate",
    "bill/BillingPeriodEndDate",
    "lineItem/UsageStartDate",
    "lineItem/UsageEndDate",
    "product/ProductName",
    "lineItem/ProductCode",
    "lineItem/LineItemType",
    "lineItem/UnblendedCost",
    "lineItem/CurrencyCode",
)


def context(organization_id=ORG_A):
    return AuthenticatedTenantContext(
        organization_id=organization_id,
        organization_name="Synthetic tenant",
        user_id=str(uuid4()),
        user_email="analyst@example.test",
        role="cio",
        authorization_claims=frozenset({"financial:read"}),
        tenant_id=organization_id,
    )


def cur_bytes(*, member="MEMBER-A", cost="12.50"):
    return (
        ",".join(HEADERS)
        + "\n"
        + ",".join(
            (
                "PAYER-A",
                member,
                "2026-07-01T00:00:00Z",
                "2026-07-31T23:59:59Z",
                "2026-07-02T00:00:00Z",
                "2026-07-02T01:00:00Z",
                "Amazon Elastic Compute Cloud",
                "AmazonEC2",
                "Usage",
                cost,
                "USD",
            )
        )
        + "\n"
    ).encode()


def mappings(organization_id=ORG_A, *, member_status="active", effective_to=None):
    return (
        AccountMapping(
            organization_id,
            organization_id,
            "PAYER-A",
            "PAYER-A",
            "active",
            effective_from="2026-01-01",
            account_kind="payer",
        ),
        AccountMapping(
            organization_id,
            organization_id,
            "PAYER-A",
            "MEMBER-A",
            member_status,
            effective_from="2026-01-01",
            effective_to=effective_to,
            account_kind="member",
        ),
    )


class FakeTenantVerifier:
    def __init__(self, verified=True):
        self.verified = verified
        self.calls = []

    def verify(self, tenant_context):
        self.calls.append(tenant_context)
        return self.verified


class FakePersistence:
    def __init__(self, *, fail_after_write=False):
        self.imports = {}
        self.facts = {}
        self.parts = {}
        self.reconciliations = {}
        self.fail_after_write = fail_after_write
        self.calls = []

    def find_import(self, context, payer, file_hash):
        self.calls.append("find_import")
        return next(
            (
                item
                for item in self.imports.values()
                if item["payer_account_id"] == payer and item["source_file_sha256"] == file_hash
            ),
            None,
        )

    def create_import(self, context, payload):
        self.calls.append("create_import")
        self.imports[payload["import_id"]] = dict(payload)

    def update_import(self, context, import_id, payload):
        self.imports[import_id].update(payload)

    def create_part(self, context, payload):
        self.parts[payload["import_part_id"]] = dict(payload)

    def update_part(self, context, part_id, payload):
        self.parts[part_id].update(payload)

    def write_facts(self, context, facts):
        for fact in facts:
            self.facts[fact["source_row_hash"]] = dict(fact)
            if self.fail_after_write:
                raise RuntimeError("synthetic partial persistence failure")
        return len(facts)

    def upsert_reconciliation(self, context, payload):
        self.reconciliations[payload["import_id"]] = dict(payload)


class FakeAccountAuthority:
    def __init__(self, records=None, *, error=None):
        self.records = tuple(records or mappings())
        self.error = error
        self.calls = []

    def list_account_mappings(self, context):
        self.calls.append(context)
        if self.error:
            raise self.error
        return self.records


class FakeReconciler:
    def __init__(self, persistence, *, fail=False, corrupt=False):
        self.persistence = persistence
        self.fail = fail
        self.corrupt = corrupt
        self.calls = []

    def verify(self, tenant, import_id, source, evidence):
        self.calls.append((tenant.organization_id, import_id))
        if self.fail:
            raise RuntimeError("synthetic reconciliation failure")
        source.seek(0)
        reader = csv.DictReader(io.StringIO(source.read().decode("utf-8")))
        source_rows = list(reader)
        source_total = sum(
            (Decimal(row["lineItem/UnblendedCost"]) for row in source_rows),
            Decimal("0"),
        )
        persisted = [
            fact for fact in self.persistence.facts.values() if fact["import_id"] == import_id
        ]
        persisted_total = sum((Decimal(fact["unblended_cost"]) for fact in persisted), Decimal("0"))
        if self.corrupt:
            persisted_total += Decimal("1")
        source.seek(0)
        return ReconciliationEvidence(
            organization_id=tenant.organization_id,
            tenant_id=tenant.tenant_id,
            import_id=import_id,
            source_sha256=evidence.source_sha256,
            source_rows=len(source_rows),
            persisted_rows=len(persisted),
            source_total=source_total,
            persisted_total=persisted_total,
            currency_code=source_rows[0]["lineItem/CurrencyCode"],
        )


class FakeDashboard:
    def __init__(self, *, posture_enabled=True):
        self.posture_enabled = posture_enabled
        self.import_id = None
        self.generated_at = None
        self.invalidations = []
        self.cache = {ORG_A: "tenant-a-cache", ORG_B: "tenant-b-cache"}

    def invalidate(self, organization_id):
        self.invalidations.append(organization_id)
        self.cache.pop(organization_id, None)

    def get_financial_posture(self, tenant, *, currency):
        if not self.posture_enabled or self.import_id is None:
            return EnterpriseFinancialPosture.empty(tenant.organization_id)
        return EnterpriseFinancialPosture(
            organization_id=tenant.organization_id,
            currency=currency,
            period_start=date(2026, 7, 1),
            period_end=date(2026, 7, 31),
            generated_at=self.generated_at or datetime.now(timezone.utc),
            import_count=1,
            latest_import_id=self.import_id,
            latest_import_status="completed",
            source_rows=1,
            persisted_facts=1,
            total_ingested_spend=Decimal("12.50"),
            cloud_spend=Decimal("12.50"),
            resolved_spend=Decimal("12.50"),
            unallocated_resolved_spend=Decimal("12.50"),
            reconciled_spend=Decimal("12.50"),
            reconciliation_status="reconciled",
        )


class FakeProjectionRefresher:
    def __init__(self, dashboard, *, fail=False, wrong_tenant=False):
        self.dashboard = dashboard
        self.fail = fail
        self.wrong_tenant = wrong_tenant
        self.calls = []

    def refresh(self, tenant, import_id):
        self.calls.append((tenant.organization_id, import_id))
        if self.fail:
            raise RuntimeError("synthetic projection failure")
        refreshed_at = datetime.now(timezone.utc)
        self.dashboard.import_id = import_id
        self.dashboard.generated_at = refreshed_at
        return ProjectionRefreshEvidence(
            organization_id=ORG_B if self.wrong_tenant else tenant.organization_id,
            tenant_id=tenant.tenant_id,
            import_id=import_id,
            refreshed_at=refreshed_at,
        )


def make_orchestrator(
    *,
    tenant_verifier=None,
    account_authority=None,
    persistence=None,
    reconciler=None,
    refresher=None,
    dashboard=None,
):
    persistence = persistence or FakePersistence()
    dashboard = dashboard or FakeDashboard()
    account_authority = account_authority or FakeAccountAuthority()
    return AwsFinancialIngestionOrchestrator(
        tenant_verifier=tenant_verifier or FakeTenantVerifier(),
        account_ownership=account_authority,
        persistence=persistence,
        reconciler=reconciler or FakeReconciler(persistence),
        projection_refresher=refresher or FakeProjectionRefresher(dashboard),
        dashboard=dashboard,
    )


def test_verified_tenant_progresses_through_all_independent_gates():
    dashboard = FakeDashboard()
    persistence = FakePersistence()
    orchestrator = make_orchestrator(
        persistence=persistence,
        dashboard=dashboard,
        reconciler=FakeReconciler(persistence),
        refresher=FakeProjectionRefresher(dashboard),
    )

    result = orchestrator.ingest(context(), io.BytesIO(cur_bytes()), "cost.csv")

    assert result.gate is IngestionGate.DASHBOARD_READY, (
        result.reason,
        result.completed_gates,
    )
    assert result.completed_gates == (
        IngestionGate.SOURCE_VALIDATED,
        IngestionGate.PERSISTENCE_COMPLETED,
        IngestionGate.RECONCILIATION_VERIFIED,
        IngestionGate.PROJECTION_REFRESHED,
        IngestionGate.DASHBOARD_READY,
    )
    assert result.import_id
    assert result.source_sha256
    assert result.currency_code == "USD"
    assert result.dashboard_generated_at is not None


def test_unverified_context_is_rejected_before_persistence():
    persistence = FakePersistence()
    result = make_orchestrator(
        tenant_verifier=FakeTenantVerifier(verified=False),
        persistence=persistence,
    ).ingest(context(), io.BytesIO(cur_bytes()), "cost.csv")

    assert result.gate is IngestionGate.BLOCKED
    assert persistence.calls == []


def test_plain_fabric_context_and_caller_organization_override_are_rejected():
    orchestrator = make_orchestrator()

    plain_context_result = orchestrator.ingest(
        TenantContext(ORG_A, ORG_A), io.BytesIO(cur_bytes()), "cost.csv"
    )
    override_result = orchestrator.ingest(
        context(),
        io.BytesIO(cur_bytes()),
        "cost.csv",
        organization_id_override=ORG_A,
    )

    assert plain_context_result.gate is IngestionGate.BLOCKED
    assert override_result.gate is IngestionGate.BLOCKED


def test_demo_tenant_is_rejected_before_ownership_or_persistence_calls():
    authority = FakeAccountAuthority()
    persistence = FakePersistence()
    result = make_orchestrator(account_authority=authority, persistence=persistence).ingest(
        context(DEMO_ORGANIZATION_ID), io.BytesIO(cur_bytes()), "cost.csv"
    )

    assert result.gate is IngestionGate.BLOCKED
    assert authority.calls == []
    assert persistence.calls == []


def test_foreign_tenant_mapping_is_blocked_before_import_persistence():
    persistence = FakePersistence()
    result = make_orchestrator(
        account_authority=FakeAccountAuthority(mappings(ORG_B)),
        persistence=persistence,
    ).ingest(context(), io.BytesIO(cur_bytes()), "cost.csv")

    assert result.gate is IngestionGate.BLOCKED
    assert persistence.calls == []


def test_unknown_account_is_persisted_only_as_quarantine_and_not_dashboard_ready():
    persistence = FakePersistence()
    authority = FakeAccountAuthority((mappings()[0],))
    dashboard = FakeDashboard()
    reconciler = FakeReconciler(persistence)
    refresher = FakeProjectionRefresher(dashboard)

    result = make_orchestrator(
        account_authority=authority,
        persistence=persistence,
        reconciler=reconciler,
        dashboard=dashboard,
        refresher=refresher,
    ).ingest(context(), io.BytesIO(cur_bytes(member="UNKNOWN")), "unknown.csv")

    assert result.gate is IngestionGate.PARTIAL
    assert result.quarantined_rows == 1
    assert {fact["fact_status"] for fact in persistence.facts.values()} == {"quarantined"}
    assert reconciler.calls == []
    assert refresher.calls == []


@pytest.mark.parametrize(
    "authority_mappings",
    [
        mappings(member_status="inactive"),
        mappings(effective_to="2026-07-01"),
    ],
)
def test_inactive_or_expired_mapping_quarantines_costs(authority_mappings):
    persistence = FakePersistence()
    result = make_orchestrator(
        account_authority=FakeAccountAuthority(authority_mappings),
        persistence=persistence,
    ).ingest(context(), io.BytesIO(cur_bytes()), "cost.csv")

    assert result.gate is IngestionGate.PARTIAL
    assert result.quarantined_rows == 1
    assert next(iter(persistence.facts.values()))["fact_status"] == "quarantined"


@pytest.mark.parametrize(
    "missing",
    [
        "tenant_verifier",
        "account_ownership",
        "persistence",
        "reconciler",
        "projection_refresher",
        "dashboard",
    ],
)
def test_missing_integration_dependency_fails_closed(missing):
    dependencies = dict(
        tenant_verifier=FakeTenantVerifier(),
        account_ownership=FakeAccountAuthority(),
        persistence=FakePersistence(),
        reconciler=object(),
        projection_refresher=object(),
        dashboard=object(),
    )
    dependencies[missing] = None
    with pytest.raises(ValueError, match=missing):
        AwsFinancialIngestionOrchestrator(**dependencies)


def test_engine_failure_after_partial_write_never_reports_success():
    persistence = FakePersistence(fail_after_write=True)
    result = make_orchestrator(persistence=persistence).ingest(
        context(), io.BytesIO(cur_bytes()), "cost.csv"
    )

    assert result.gate is IngestionGate.PARTIAL
    assert IngestionGate.PERSISTENCE_COMPLETED not in result.completed_gates
    assert persistence.facts


def test_independent_reconciliation_mismatch_blocks_projection_refresh():
    dashboard = FakeDashboard()
    persistence = FakePersistence()
    refresher = FakeProjectionRefresher(dashboard)
    result = make_orchestrator(
        persistence=persistence,
        reconciler=FakeReconciler(persistence, corrupt=True),
        dashboard=dashboard,
        refresher=refresher,
    ).ingest(context(), io.BytesIO(cur_bytes()), "cost.csv")

    assert result.gate is IngestionGate.PARTIAL
    assert IngestionGate.RECONCILIATION_VERIFIED not in result.completed_gates
    assert refresher.calls == []


def test_projection_refresh_failure_blocks_dashboard_readiness():
    dashboard = FakeDashboard()
    persistence = FakePersistence()
    refresher = FakeProjectionRefresher(dashboard, fail=True)
    result = make_orchestrator(
        persistence=persistence,
        reconciler=FakeReconciler(persistence),
        dashboard=dashboard,
        refresher=refresher,
    ).ingest(context(), io.BytesIO(cur_bytes()), "cost.csv")

    assert result.gate is IngestionGate.PARTIAL
    assert IngestionGate.RECONCILIATION_VERIFIED in result.completed_gates
    assert IngestionGate.PROJECTION_REFRESHED not in result.completed_gates
    assert dashboard.invalidations == []


def test_cross_tenant_projection_receipt_is_rejected():
    dashboard = FakeDashboard()
    persistence = FakePersistence()
    result = make_orchestrator(
        persistence=persistence,
        reconciler=FakeReconciler(persistence),
        dashboard=dashboard,
        refresher=FakeProjectionRefresher(dashboard, wrong_tenant=True),
    ).ingest(context(), io.BytesIO(cur_bytes()), "cost.csv")

    assert result.gate is IngestionGate.PARTIAL
    assert IngestionGate.PROJECTION_REFRESHED not in result.completed_gates


def test_tenant_a_cache_invalidation_preserves_tenant_b_cache():
    dashboard = FakeDashboard()
    persistence = FakePersistence()
    result = make_orchestrator(
        persistence=persistence,
        reconciler=FakeReconciler(persistence),
        dashboard=dashboard,
        refresher=FakeProjectionRefresher(dashboard),
    ).ingest(context(ORG_A), io.BytesIO(cur_bytes()), "cost.csv")

    assert result.gate is IngestionGate.DASHBOARD_READY, result
    assert dashboard.invalidations == [ORG_A]
    assert dashboard.cache[ORG_B] == "tenant-b-cache"


def test_absent_canonical_posture_never_reports_dashboard_ready():
    dashboard = FakeDashboard(posture_enabled=False)
    persistence = FakePersistence()
    result = make_orchestrator(
        persistence=persistence,
        reconciler=FakeReconciler(persistence),
        dashboard=dashboard,
        refresher=FakeProjectionRefresher(dashboard),
    ).ingest(context(), io.BytesIO(cur_bytes()), "cost.csv")

    assert result.gate is IngestionGate.PARTIAL
    assert IngestionGate.PROJECTION_REFRESHED in result.completed_gates
    assert IngestionGate.DASHBOARD_READY not in result.completed_gates


def test_posture_older_than_projection_refresh_is_not_fresh():
    dashboard = FakeDashboard()
    persistence = FakePersistence()

    class StaleRefresher(FakeProjectionRefresher):
        def refresh(self, tenant, import_id):
            evidence = super().refresh(tenant, import_id)
            self.dashboard.generated_at = evidence.refreshed_at.replace(year=2025)
            return evidence

    result = make_orchestrator(
        persistence=persistence,
        reconciler=FakeReconciler(persistence),
        dashboard=dashboard,
        refresher=StaleRefresher(dashboard),
    ).ingest(context(), io.BytesIO(cur_bytes()), "cost.csv")

    assert result.gate is IngestionGate.PARTIAL
    assert IngestionGate.DASHBOARD_READY not in result.completed_gates


def test_reconciliation_exception_blocks_refresh_and_readiness():
    dashboard = FakeDashboard()
    persistence = FakePersistence()
    refresher = FakeProjectionRefresher(dashboard)
    result = make_orchestrator(
        persistence=persistence,
        reconciler=FakeReconciler(persistence, fail=True),
        dashboard=dashboard,
        refresher=refresher,
    ).ingest(context(), io.BytesIO(cur_bytes()), "cost.csv")

    assert result.gate is IngestionGate.PARTIAL
    assert IngestionGate.RECONCILIATION_VERIFIED not in result.completed_gates
    assert refresher.calls == []
    assert dashboard.invalidations == []


@pytest.mark.parametrize(
    "changes",
    [
        {"organization_id": ORG_B},
        {"latest_import_id": "foreign-import"},
        {"latest_import_status": "failed"},
        {"import_count": 2},
        {"currency": "EUR"},
        {"period_start": None},
        {"period_end": date(2026, 8, 31)},
        {"source_rows": 0},
        {"persisted_facts": 0},
        {"cloud_spend": Decimal("999")},
        {
            "total_ingested_spend": Decimal("99"),
            "resolved_spend": Decimal("99"),
            "unallocated_resolved_spend": Decimal("99"),
            "reconciled_spend": Decimal("99"),
        },
    ],
)
def test_canonical_values_and_provenance_must_match_verified_source(changes):
    class CorruptDashboard(FakeDashboard):
        def get_financial_posture(self, tenant, *, currency):
            return replace(super().get_financial_posture(tenant, currency=currency), **changes)

    dashboard = CorruptDashboard()
    result = make_orchestrator(dashboard=dashboard).ingest(
        context(), io.BytesIO(cur_bytes()), "cost.csv"
    )

    assert result.gate is IngestionGate.PARTIAL
    assert IngestionGate.PROJECTION_REFRESHED in result.completed_gates
    assert IngestionGate.DASHBOARD_READY not in result.completed_gates


class IntegrationPersistence(FakePersistence):
    def write_facts(self, tenant, facts):
        for fact in facts:
            fact.setdefault("ingested_at", datetime.now(timezone.utc))
            fact.setdefault("supersedes_fact_id", None)
        return super().write_facts(tenant, facts)

    def upsert_reconciliation(self, tenant, payload):
        super().upsert_reconciliation(tenant, payload)
        self.reconciliations[payload["import_id"]].update(
            variance_amount=Decimal(0),
            reconciled_at=datetime.now(timezone.utc),
        )


def canonical_row(row):
    row = dict(row)
    for name in ("billing_period_start", "billing_period_end"):
        row[name] = date.fromisoformat(row[name])
    for name in ("unblended_cost", "source_cost_total", "normalized_cost_total"):
        if name in row:
            row[name] = Decimal(row[name])
    if isinstance(row.get("completed_at"), str):
        row["completed_at"] = datetime.fromisoformat(row["completed_at"])
    return row


class IntegrationDashboard(FakeDashboard):
    def __init__(self):
        super().__init__()
        self.posture = None

    def get_financial_posture(self, tenant, *, currency):
        if not self.posture_enabled or self.posture is None:
            return EnterpriseFinancialPosture.empty(tenant.organization_id)
        return self.posture


class IntegrationRefresher(FakeProjectionRefresher):
    """Synthetic materialization and receipt; never a production adapter."""

    def __init__(self, dashboard, persistence):
        super().__init__(dashboard)
        self.persistence = persistence
        self.projection = None

    def refresh(self, tenant, import_id):
        receipt = super().refresh(tenant, import_id)
        imports = [canonical_row(row) for row in self.persistence.imports.values()]
        facts = [canonical_row(row) for row in self.persistence.facts.values()]
        contributions = []
        for imported in imports:
            included = [f for f in facts if f["import_id"] == imported["import_id"]]
            contributions.append(
                {
                    **imported,
                    "persisted_facts": len(included),
                    "total_unblended_spend": sum(
                        (f["unblended_cost"] for f in included), Decimal(0)
                    ),
                }
            )
        total = sum((x["total_unblended_spend"] for x in contributions), Decimal(0))
        query = DashboardQuery("USD", date(2026, 7, 1), date(2026, 7, 31))
        observed = datetime.now(timezone.utc)
        self.dashboard.posture = EnterpriseFinancialPosture(
            organization_id=tenant.organization_id,
            currency="USD",
            period_start=query.period_start,
            period_end=query.period_end,
            generated_at=observed,
            import_count=len(imports),
            latest_import_id=import_id,
            latest_import_status="completed",
            source_rows=len(facts),
            persisted_facts=len(facts),
            total_ingested_spend=total,
            cloud_spend=total,
            resolved_spend=total,
            unallocated_resolved_spend=total,
            reconciled_spend=total,
            reconciliation_status="reconciled",
        )
        self.projection = ProjectionEvidence(
            tenant.organization_id,
            tenant.tenant_id,
            query,
            "synthetic-shared-revision",
            observed,
            receipt.refreshed_at,
            True,
            tuple(contributions),
            tuple(f["cloud_cost_fact_id"] for f in facts),
            total,
            self.dashboard.posture,
        )
        return receipt


class IntegrationEvidenceProvider:
    def __init__(self, persistence, refresher):
        self.persistence, self.refresher = persistence, refresher
        self.blobs = {}
        self.calls = []
        self.mutate = lambda evidence: evidence

    def read(self, tenant, import_ids, query):
        self.calls.append((tenant, import_ids, query))
        imports = tuple(canonical_row(x) for x in self.persistence.imports.values())
        facts = tuple(canonical_row(x) for x in self.persistence.facts.values())
        recons = tuple(canonical_row(x) for x in self.persistence.reconciliations.values())
        sources = {}
        for imported in imports:
            blob = self.blobs[imported["source_file_sha256"]]
            rows = list(csv.DictReader(io.StringIO(blob.decode())))
            # Source amount/count/hash are read from separately retained bytes.
            import hashlib

            sources[imported["import_id"]] = {
                "organization_id": tenant.organization_id,
                "tenant_id": tenant.tenant_id,
                "import_id": imported["import_id"],
                "payer_account_id": rows[0]["bill/PayerAccountId"],
                "billing_period_start": date.fromisoformat(
                    rows[0]["bill/BillingPeriodStartDate"][:10]
                ),
                "billing_period_end": date.fromisoformat(rows[0]["bill/BillingPeriodEndDate"][:10]),
                "currency_code": rows[0]["lineItem/CurrencyCode"],
                "source_file_sha256": hashlib.sha256(blob).hexdigest(),
                "source_row_count": len(rows),
                "source_cost_total": sum(
                    (Decimal(r["lineItem/UnblendedCost"]) for r in rows), Decimal(0)
                ),
            }
        # The fixture's projection is frozen at refresh; canonical reads happen
        # afterwards. A shared revision is supplied explicitly by this fake only.
        projection = replace(self.refresher.projection, observed_at=datetime.now(timezone.utc))
        canonical = CanonicalEvidence(
            tenant.organization_id,
            tenant.tenant_id,
            query,
            projection.revision,
            self.refresher.projection.observed_at,
            True,
            imports,
            facts,
            recons,
        )
        return self.mutate(ImportContributionEvidence(sources, canonical, projection))


def integration_fixture():
    import hashlib

    persistence = IntegrationPersistence()
    dashboard = IntegrationDashboard()
    refresher = IntegrationRefresher(dashboard, persistence)
    provider = IntegrationEvidenceProvider(persistence, refresher)
    reconciler = FakeReconciler(persistence)
    orchestrator = AwsFinancialIngestionOrchestrator(
        tenant_verifier=FakeTenantVerifier(),
        account_ownership=FakeAccountAuthority(),
        persistence=persistence,
        reconciler=reconciler,
        projection_refresher=refresher,
        dashboard=dashboard,
        contribution_verifier=AwsFinancialImportContributionVerifier,
        evidence_provider=provider,
    )
    query = DashboardQuery("USD", date(2026, 7, 1), date(2026, 7, 31))
    blobs = (cur_bytes(cost="12000"), cur_bytes(cost="8000"))
    provider.blobs = {hashlib.sha256(blob).hexdigest(): blob for blob in blobs}
    first = orchestrator.ingest(
        context(), io.BytesIO(blobs[0]), "first.csv", prior_import_ids=(), dashboard_query=query
    )
    assert first.gate is IngestionGate.DASHBOARD_READY, first
    return (
        orchestrator,
        first,
        blobs[1],
        query,
        provider,
        persistence,
        dashboard,
        refresher,
        reconciler,
    )


def test_multi_import_ingestion_requires_complete_proof_and_preserves_tenant_b_cache():
    orchestrator, first, blob, query, provider, _, dashboard, _, reconciler = integration_fixture()
    second = orchestrator.ingest(
        context(),
        io.BytesIO(blob),
        "second.csv",
        prior_import_ids=(first.import_id,),
        dashboard_query=query,
    )
    assert second.gate is IngestionGate.DASHBOARD_READY, second
    assert second.verified_import_ids == (first.import_id, second.import_id)
    assert second.verified_total == Decimal("20000")
    assert IngestionGate.CONTRIBUTIONS_VERIFIED in second.completed_gates
    assert len(reconciler.calls) == 2
    assert provider.calls[-1][1] == second.verified_import_ids
    assert dashboard.invalidations == [ORG_A, ORG_A]
    assert dashboard.cache[ORG_B] == "tenant-b-cache"


@pytest.mark.parametrize(
    "case",
    [
        "missing_import",
        "duplicate_import",
        "missing_membership",
        "wrong_hash",
        "foreign_evidence",
        "stale_snapshot",
        "wrong_refresh_receipt",
        "missing_verifier",
        "missing_reader",
        "missing_posture",
        "unverified_import",
        "refresh_failure",
        "reconciliation_failure",
        "partial_persistence",
        "missing_explicit_ids",
        "missing_query",
        "foreign_projection",
        "incomplete",
        "different_posture",
        "stale_timestamp",
        "missing_facts",
        "wrong_current_hash",
    ],
)
def test_multi_import_integration_fails_closed(case):
    o, first, blob, query, provider, persistence, dashboard, refresher, reconciler = (
        integration_fixture()
    )
    prior = (first.import_id,)
    if case == "duplicate_import":
        prior = (first.import_id, first.import_id)
    elif case == "missing_verifier":
        o._contribution_verifier = None
    elif case == "missing_reader":
        o._evidence_provider = None
    elif case == "missing_posture":
        dashboard.posture_enabled = False
    elif case == "refresh_failure":
        refresher.fail = True
    elif case == "reconciliation_failure":
        reconciler.fail = True
    elif case == "partial_persistence":
        persistence.fail_after_write = True
    elif case == "missing_explicit_ids":
        prior = None
    elif case == "missing_query":
        query = None
    else:

        def mutate(evidence):
            canonical, projection = evidence.canonical, evidence.projection
            if case == "missing_import":
                canonical = replace(canonical, imports=canonical.imports[1:])
            elif case == "missing_membership":
                projection = replace(projection, included_fact_ids=None)
            elif case == "wrong_hash":
                rows = list(canonical.imports)
                rows[0] = {**rows[0], "source_file_sha256": "a" * 64}
                canonical = replace(canonical, imports=tuple(rows))
            elif case == "foreign_evidence":
                canonical = replace(canonical, organization_id=ORG_B, tenant_id=ORG_B)
            elif case == "stale_snapshot":
                canonical = replace(canonical, revision="stale-revision")
            elif case == "wrong_refresh_receipt":
                projection = replace(
                    projection, refreshed_at=projection.refreshed_at - timedelta(seconds=1)
                )
            elif case == "unverified_import":
                rows = list(canonical.reconciliations)
                rows[0] = {**rows[0], "status": "failed"}
                canonical = replace(canonical, reconciliations=tuple(rows))
            elif case == "foreign_projection":
                projection = replace(projection, organization_id=ORG_B, tenant_id=ORG_B)
            elif case == "incomplete":
                canonical = replace(canonical, complete=False)
            elif case == "different_posture":
                projection = replace(
                    projection,
                    posture=replace(
                        projection.posture,
                        generated_at=projection.posture.generated_at - timedelta(seconds=1),
                    ),
                )
            elif case == "stale_timestamp":
                canonical = replace(
                    canonical, observed_at=projection.refreshed_at - timedelta(seconds=1)
                )
            elif case == "missing_facts":
                canonical = replace(canonical, facts=None)
            elif case == "wrong_current_hash":
                sources = dict(evidence.sources)
                current_id = projection.posture.latest_import_id
                sources[current_id] = {**sources[current_id], "source_file_sha256": "f" * 64}
                evidence = replace(evidence, sources=sources)
            return replace(evidence, canonical=canonical, projection=projection)

        provider.mutate = mutate
    result = o.ingest(
        context(), io.BytesIO(blob), "second.csv", prior_import_ids=prior, dashboard_query=query
    )
    assert result.gate is IngestionGate.PARTIAL, result
    assert IngestionGate.DASHBOARD_READY not in result.completed_gates
    assert IngestionGate.CONTRIBUTIONS_VERIFIED not in result.completed_gates
    assert result.verified_total is None
    assert dashboard.cache[ORG_B] == "tenant-b-cache"
    if case in {"partial_persistence", "reconciliation_failure", "refresh_failure"}:
        assert len(provider.calls) == 1
        assert dashboard.invalidations == [ORG_A]
