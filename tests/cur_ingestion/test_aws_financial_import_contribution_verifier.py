"""Synthetic offline evidence; no client, database or service composition."""

from dataclasses import replace
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

import pytest

from auth.authenticated_tenant import AuthenticatedTenantContext
from data_fabric.foundation import TenantContext
from models.contracts.enterprise_financial_posture import EnterpriseFinancialPosture
from services.aws_financial_import_contribution_verifier import (
    AwsFinancialImportContributionVerifier,
    CanonicalEvidence,
    DashboardQuery,
    ProjectionEvidence,
    ProofStatus,
)
from services.demo_tenant_service import DEMO_ORGANIZATION_ID

ORG_A, ORG_B = str(uuid4()), str(uuid4())
START, END = date(2026, 7, 1), date(2026, 7, 31)
COMPLETED = datetime(2026, 8, 1, tzinfo=timezone.utc)
REFRESHED = COMPLETED + timedelta(minutes=1)
OBSERVED = REFRESHED + timedelta(minutes=1)
QUERY = DashboardQuery("USD", START, END)
IDS = ("import-1", "import-2")


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


class EvidenceReaders:
    def __init__(self):
        self.verified = True
        self.calls = []
        self.sources = {}
        imports, facts, recons, projected = [], [], [], []
        for number, amount in enumerate(("12000", "8000"), 1):
            iid = f"import-{number}"
            identity = dict(
                organization_id=ORG_A,
                tenant_id=ORG_A,
                import_id=iid,
                payer_account_id="PAYER-A",
                currency_code="USD",
                billing_period_start=START,
                billing_period_end=END,
            )
            source = dict(
                identity,
                source_file_sha256=str(number) * 64,
                source_row_count=1,
                source_cost_total=Decimal(amount),
            )
            self.sources[iid] = source
            imports.append(
                dict(
                    source,
                    status="completed",
                    accepted_row_count=1,
                    duplicate_row_count=0,
                    rejected_row_count=0,
                    normalized_cost_total=Decimal(amount),
                    supersedes_import_id=None,
                    completed_at=COMPLETED,
                )
            )
            facts.append(
                dict(
                    identity,
                    cloud_cost_fact_id=f"fact-{number}",
                    source_row_key=f"row-{number}",
                    source_row_hash=str(number) * 64,
                    fact_status="active",
                    supersedes_fact_id=None,
                    unblended_cost=Decimal(amount),
                    ingested_at=COMPLETED,
                )
            )
            recons.append(
                dict(
                    identity,
                    status="reconciled",
                    source_row_count=1,
                    normalized_row_count=1,
                    rejected_row_count=0,
                    duplicate_row_count=0,
                    source_cost_total=Decimal(amount),
                    normalized_cost_total=Decimal(amount),
                    variance_amount=Decimal(0),
                    reconciled_at=COMPLETED,
                )
            )
            projected.append(
                dict(identity, persisted_facts=1, total_unblended_spend=Decimal(amount))
            )
        self.canonical = CanonicalEvidence(
            ORG_A,
            ORG_A,
            QUERY,
            "synthetic-revision",
            OBSERVED,
            True,
            tuple(imports),
            tuple(facts),
            tuple(recons),
        )
        posture = EnterpriseFinancialPosture(
            organization_id=ORG_A,
            currency="USD",
            period_start=START,
            period_end=END,
            generated_at=OBSERVED,
            import_count=2,
            latest_import_id=IDS[1],
            latest_import_status="completed",
            source_rows=2,
            persisted_facts=2,
            total_ingested_spend=Decimal("20000"),
            cloud_spend=Decimal("20000"),
            resolved_spend=Decimal("20000"),
            unallocated_resolved_spend=Decimal("20000"),
            reconciled_spend=Decimal("20000"),
            reconciliation_status="reconciled",
        )
        self.projection = ProjectionEvidence(
            ORG_A,
            ORG_A,
            QUERY,
            "synthetic-revision",
            OBSERVED,
            REFRESHED,
            True,
            tuple(projected),
            ("fact-1", "fact-2"),
            Decimal("20000"),
            posture,
        )

    def verify(self, tenant):
        self.calls.append(("verify", tenant.organization_id))
        return self.verified

    def read_source(self, tenant, import_id):
        self.calls.append(("source", tenant.organization_id, import_id))
        return self.sources.get(import_id)

    def read_canonical(self, tenant, query):
        self.calls.append(("canonical", tenant.organization_id, query))
        return self.canonical

    def read_projection(self, tenant, query):
        self.calls.append(("projection", tenant.organization_id, query))
        return self.projection

    def verifier(self, **overrides):
        dependencies = dict(
            tenant_verifier=self, source_reader=self, canonical_reader=self, projection_reader=self
        )
        dependencies.update(overrides)
        return AwsFinancialImportContributionVerifier(**dependencies)


def change_row(readers, collection, index=1, **changes):
    holder = readers.projection if collection == "contributions" else readers.canonical
    rows = list(getattr(holder, collection))
    rows[index] = dict(rows[index], **changes)
    updated = replace(holder, **{collection: tuple(rows)})
    if collection == "contributions":
        readers.projection = updated
    else:
        readers.canonical = updated


def test_two_independently_verified_imports_prove_twenty_thousand():
    readers = EvidenceReaders()
    result = readers.verifier().verify(context(), IDS, QUERY)
    assert result.status is ProofStatus.PASS, result
    assert result.verified_import_ids == IDS
    assert result.verified_total == Decimal("20000")
    assert len([x for x in readers.calls if x[0] == "source"]) == 2


@pytest.mark.parametrize(
    "case,status",
    [
        ("missing_import", ProofStatus.BLOCKED),
        ("missing_source", ProofStatus.BLOCKED),
        ("failed_reconciliation", ProofStatus.PARTIAL),
        ("missing_reconciliation", ProofStatus.BLOCKED),
        ("variance", ProofStatus.PARTIAL),
        ("duplicate_import", ProofStatus.FAILED),
        ("duplicate_source", ProofStatus.FAILED),
        ("duplicate_fact", ProofStatus.FAILED),
        ("superseded_import", ProofStatus.PARTIAL),
        ("replacement_import", ProofStatus.PARTIAL),
        ("superseded_fact", ProofStatus.PARTIAL),
        ("quarantined", ProofStatus.PARTIAL),
        ("currency", ProofStatus.FAILED),
        ("period", ProofStatus.FAILED),
        ("aggregate_total", ProofStatus.FAILED),
        ("stale_projection", ProofStatus.PARTIAL),
        ("foreign_import", ProofStatus.BLOCKED),
        ("foreign_fact", ProofStatus.BLOCKED),
        ("foreign_reconciliation", ProofStatus.BLOCKED),
        ("foreign_projection", ProofStatus.BLOCKED),
        ("provenance", ProofStatus.BLOCKED),
        ("missing_facts", ProofStatus.BLOCKED),
        ("omitted_fact", ProofStatus.FAILED),
        ("missing_membership", ProofStatus.BLOCKED),
        ("wrong_membership", ProofStatus.FAILED),
        ("duplicate_membership", ProofStatus.FAILED),
        ("incomplete", ProofStatus.BLOCKED),
        ("revision", ProofStatus.BLOCKED),
        ("source_hash", ProofStatus.FAILED),
        ("precision", ProofStatus.FAILED),
        ("nonfinite", ProofStatus.FAILED),
        ("wrong_fact_amount", ProofStatus.FAILED),
        ("missing_posture", ProofStatus.BLOCKED),
        ("stale_posture", ProofStatus.PARTIAL),
        ("foreign_posture", ProofStatus.BLOCKED),
        ("posture_amount", ProofStatus.FAILED),
    ],
)
def test_incomplete_or_inconsistent_contributions_fail_closed(case, status):
    r = EvidenceReaders()
    if case == "missing_import":
        r.canonical = replace(r.canonical, imports=r.canonical.imports[:1])
    elif case == "missing_source":
        r.sources.pop(IDS[1])
    elif case == "failed_reconciliation":
        change_row(r, "reconciliations", status="failed")
    elif case == "missing_reconciliation":
        r.canonical = replace(r.canonical, reconciliations=r.canonical.reconciliations[:1])
    elif case == "variance":
        change_row(r, "reconciliations", variance_amount=Decimal("1"))
    elif case == "duplicate_import":
        r.canonical = replace(r.canonical, imports=r.canonical.imports + r.canonical.imports[:1])
    elif case == "duplicate_source":
        r.sources[IDS[1]]["source_file_sha256"] = "1" * 64
        change_row(r, "imports", source_file_sha256="1" * 64)
    elif case == "duplicate_fact":
        r.canonical = replace(r.canonical, facts=r.canonical.facts + r.canonical.facts[:1])
    elif case == "superseded_import":
        change_row(r, "imports", status="superseded")
    elif case == "replacement_import":
        change_row(r, "imports", supersedes_import_id=IDS[0])
    elif case == "superseded_fact":
        change_row(r, "facts", supersedes_fact_id="older-fact")
    elif case == "quarantined":
        change_row(r, "facts", fact_status="quarantined", unblended_cost=Decimal("8000"))
    elif case == "currency":
        change_row(r, "imports", currency_code="EUR")
    elif case == "period":
        change_row(r, "imports", billing_period_end=date(2026, 8, 31))
    elif case == "aggregate_total":
        r.projection = replace(r.projection, total=Decimal("20001"))
    elif case == "stale_projection":
        r.projection = replace(r.projection, refreshed_at=COMPLETED - timedelta(seconds=1))
    elif case.startswith("foreign_") and case != "foreign_posture":
        collection = {
            "foreign_import": "imports",
            "foreign_fact": "facts",
            "foreign_reconciliation": "reconciliations",
            "foreign_projection": "contributions",
        }[case]
        change_row(r, collection, organization_id=ORG_B, tenant_id=ORG_B)
    elif case == "provenance":
        row = dict(r.canonical.imports[1])
        row.pop("source_file_sha256")
        r.canonical = replace(r.canonical, imports=(r.canonical.imports[0], row))
    elif case == "missing_facts":
        r.canonical = replace(r.canonical, facts=None)
    elif case == "omitted_fact":
        r.canonical = replace(r.canonical, facts=r.canonical.facts[:1])
    elif case == "missing_membership":
        r.projection = replace(r.projection, included_fact_ids=None)
    elif case == "wrong_membership":
        r.projection = replace(r.projection, included_fact_ids=("fact-1", "foreign-fact"))
    elif case == "duplicate_membership":
        r.projection = replace(r.projection, included_fact_ids=("fact-1", "fact-1"))
    elif case == "incomplete":
        r.canonical = replace(r.canonical, complete=False)
    elif case == "revision":
        r.projection = replace(r.projection, revision="different")
    elif case == "source_hash":
        change_row(r, "imports", source_file_sha256="a" * 64)
    elif case == "precision":
        change_row(r, "facts", unblended_cost=Decimal("8000.00000000001"))
    elif case == "nonfinite":
        change_row(r, "facts", unblended_cost=Decimal("NaN"))
    elif case == "wrong_fact_amount":
        change_row(r, "facts", unblended_cost=Decimal("7999"))
    elif case == "missing_posture":
        r.projection = replace(r.projection, posture=None)
    elif case == "stale_posture":
        r.projection = replace(
            r.projection, posture=replace(r.projection.posture, generated_at=COMPLETED)
        )
    elif case == "foreign_posture":
        r.projection = replace(
            r.projection, posture=replace(r.projection.posture, organization_id=ORG_B)
        )
    elif case == "posture_amount":
        r.projection = replace(
            r.projection, posture=replace(r.projection.posture, cloud_spend=Decimal("1"))
        )
    else:
        pytest.fail(f"unhandled fixture {case}")
    result = r.verifier().verify(context(), IDS, QUERY)
    assert result.status is status, result
    assert result.verified_total is None


@pytest.mark.parametrize(
    "dependency", ["tenant_verifier", "source_reader", "canonical_reader", "projection_reader"]
)
def test_missing_dependency_is_blocked(dependency):
    r = EvidenceReaders()
    result = r.verifier(**{dependency: None}).verify(context(), IDS, QUERY)
    assert result.status is ProofStatus.BLOCKED
    assert r.calls == []


@pytest.mark.parametrize("tenant", [context(DEMO_ORGANIZATION_ID), TenantContext(ORG_A, ORG_A)])
def test_demo_and_unverified_context_types_blocked(tenant):
    r = EvidenceReaders()
    result = r.verifier().verify(tenant, IDS, QUERY)
    assert result.status is ProofStatus.BLOCKED
    assert all(x[0] == "verify" for x in r.calls)


def test_unverified_tenant_does_not_read_evidence():
    r = EvidenceReaders()
    r.verified = False
    assert r.verifier().verify(context(), IDS, QUERY).status is ProofStatus.BLOCKED
    assert [x[0] for x in r.calls] == ["verify"]


@pytest.mark.parametrize(
    "ids,status", [((), ProofStatus.BLOCKED), ((IDS[0], IDS[0]), ProofStatus.FAILED)]
)
def test_explicit_unique_ids_required(ids, status):
    r = EvidenceReaders()
    assert r.verifier().verify(context(), ids, QUERY).status is status
    assert [x[0] for x in r.calls] == ["verify"]


@pytest.mark.parametrize("multiple,status", [(False, ProofStatus.FAILED), (True, ProofStatus.PASS)])
def test_multiple_billing_periods_require_explicit_spanning_query(multiple, status):
    r = EvidenceReaders()
    august_start, august_end = date(2026, 8, 1), date(2026, 8, 31)
    query = DashboardQuery("USD", START, august_end, multiple)
    r.sources[IDS[1]].update(billing_period_start=august_start, billing_period_end=august_end)
    for collection in ("imports", "facts", "reconciliations", "contributions"):
        change_row(r, collection, billing_period_start=august_start, billing_period_end=august_end)
    r.canonical = replace(r.canonical, query=query)
    r.projection = replace(
        r.projection, query=query, posture=replace(r.projection.posture, period_end=august_end)
    )
    result = r.verifier().verify(context(), IDS, query)
    assert result.status is status, result


def test_reader_failure_returns_blocked_without_exception():
    class Unavailable:
        def read_canonical(self, tenant, query):
            raise RuntimeError("synthetic reader failure")

    r = EvidenceReaders()
    result = r.verifier(canonical_reader=Unavailable()).verify(context(), IDS, QUERY)
    assert result.status is ProofStatus.BLOCKED


def test_tenant_b_request_cannot_consume_tenant_a_snapshot():
    r = EvidenceReaders()
    assert r.verifier().verify(context(ORG_B), IDS, QUERY).status is ProofStatus.BLOCKED


@pytest.mark.parametrize(
    "collection,key",
    [
        ("imports", "supersedes_import_id"),
        ("facts", "supersedes_fact_id"),
        ("facts", "source_row_hash"),
        ("reconciliations", "variance_amount"),
        ("reconciliations", "reconciled_at"),
    ],
)
def test_missing_provenance_is_blocked(collection, key):
    r = EvidenceReaders()
    rows = list(getattr(r.canonical, collection))
    rows[1] = dict(rows[1])
    rows[1].pop(key)
    r.canonical = replace(r.canonical, **{collection: tuple(rows)})
    result = r.verifier().verify(context(), IDS, QUERY)
    assert result.status is ProofStatus.BLOCKED, result


def test_exact_ten_decimal_contributions_and_negative_credits():
    r = EvidenceReaders()
    amounts = (Decimal("12000.0000000001"), Decimal("-8000.0000000001"))
    for index, amount in enumerate(amounts):
        r.sources[IDS[index]]["source_cost_total"] = amount
        for collection in ("imports", "reconciliations"):
            change_row(r, collection, index, source_cost_total=amount, normalized_cost_total=amount)
        change_row(r, "facts", index, unblended_cost=amount)
        change_row(r, "contributions", index, total_unblended_spend=amount)
    total = sum(amounts)
    r.projection = replace(
        r.projection,
        total=total,
        posture=replace(
            r.projection.posture,
            total_ingested_spend=total,
            cloud_spend=total,
            resolved_spend=total,
            unallocated_resolved_spend=total,
            reconciled_spend=total,
        ),
    )
    result = r.verifier().verify(context(), IDS, QUERY)
    assert result.status is ProofStatus.PASS, result
    assert result.verified_total == Decimal("4000")


def test_correct_total_cannot_mask_opposing_wrong_import_contributions():
    r = EvidenceReaders()
    change_row(r, "contributions", 0, total_unblended_spend=Decimal("11000"))
    change_row(r, "contributions", 1, total_unblended_spend=Decimal("9000"))
    result = r.verifier().verify(context(), IDS, QUERY)
    assert result.status is ProofStatus.FAILED, result


def test_caller_organization_override_is_not_an_authorization_parameter():
    r = EvidenceReaders()
    with pytest.raises(TypeError, match="organization_id_override"):
        r.verifier().verify(context(), IDS, QUERY, organization_id_override=ORG_B)
    assert r.calls == []
