from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import Lock

import pytest

from auth.tenant_authorization import TenantAuthorizationContext, TenantAuthorizationError
from canonical_stewardship.exceptions import (
    StewardshipPolicyScopeError,
    StewardshipRepositoryInvariantError,
)
from canonical_stewardship.models import AuthorityRule, FreshnessPolicy, ReviewItem, ReviewState
from canonical_stewardship.service import StewardshipService
from canonical_stewardship.supabase_repository import SupabaseStewardshipRepository

NOW = datetime(2026, 7, 21, tzinfo=timezone.utc)


class Repo:
    def __init__(self):
        self.item = None
        self.keys = {}
        self.audit = []
        self.lock = Lock()

    def create_review(self, item, *, actor, idempotency_key, correlation_id):
        with self.lock:
            key = ("review_created", idempotency_key)
            previous = self.keys.get(key)
            if previous and previous[0] != item.payload_hash:
                raise ValueError("idempotency conflict")
            if previous:
                return previous[1]
            self.item = item
            self.keys[key] = (item.payload_hash, item)
            self.audit.append(key)
            return item

    def transition(
        self,
        review_id,
        target,
        *,
        expected_revision,
        actor,
        rationale,
        idempotency_key,
        correlation_id,
    ):
        with self.lock:
            key = ("state_transition", idempotency_key)
            request_hash = (review_id, target, expected_revision, rationale)
            previous = self.keys.get(key)
            if previous and previous[0] != request_hash:
                raise ValueError("idempotency conflict")
            if previous:
                return previous[1]
            if self.item.review_id != review_id:
                raise KeyError(review_id)
            if self.item.revision != expected_revision:
                raise ValueError("revision conflict")
            self.item = replace(self.item, state=target, revision=expected_revision + 1)
            self.keys[key] = (request_hash, self.item)
            self.audit.append(key)
            return self.item


def item(tenant="tenant-a", payload_hash="hash-a"):
    return ReviewItem(
        "r1",
        "org",
        tenant,
        "key",
        "identity",
        "technology",
        "technology",
        "t1",
        payload_hash=payload_hash,
    )


def test_authority_is_tenant_scoped_and_equal_priority_conflicts():
    rules = [
        AuthorityRule("org", "tenant-a", "technology", "name", "cmdb", "domain", NOW, priority=1),
        AuthorityRule("org", "tenant-b", "technology", "name", "other", "domain", NOW, priority=9),
    ]
    assert (
        StewardshipService.resolve_authority(
            rules,
            organization_id="org",
            tenant_id="tenant-a",
            domain="technology",
            subject="name",
            at=NOW,
        ).source_system
        == "cmdb"
    )
    with pytest.raises(ValueError, match="manual review"):
        StewardshipService.resolve_authority(
            [
                rules[0],
                AuthorityRule(
                    "org", "tenant-a", "technology", "name", "inventory", "domain", NOW, priority=1
                ),
            ],
            organization_id="org",
            tenant_id="tenant-a",
            domain="technology",
            subject="name",
            at=NOW,
        )


def test_freshness_boundaries_and_coverage_reconcile():
    policy = FreshnessPolicy(
        "org",
        "tenant-a",
        "technology",
        timedelta(hours=1),
        timedelta(hours=2),
        timedelta(hours=4),
        timedelta(hours=8),
    )
    rows = [
        {"canonical_id": "c1", "source_system": "cmdb", "observed_at": NOW - timedelta(hours=1)},
        {
            "canonical_id": None,
            "source_system": None,
            "observed_at": NOW - timedelta(hours=4),
            "unresolved": True,
        },
        {"excluded": True},
    ]
    result = StewardshipService.coverage(
        organization_id="org",
        tenant_id="tenant-a",
        domain="technology",
        inventory=rows,
        policy=policy,
        now=NOW,
    )
    assert (
        result.eligible,
        result.covered,
        result.excluded,
        result.unresolved,
        result.missing_source,
    ) == (2, 1, 1, 1, 1)
    assert sum(result.freshness.values()) == result.eligible
    assert result.freshness["stale"] == 1


def test_freshness_policy_rejects_non_monotonic_thresholds():
    with pytest.raises(ValueError, match="monotonic"):
        FreshnessPolicy(
            "org",
            "tenant",
            "applications",
            timedelta(hours=2),
            timedelta(hours=1),
            timedelta(hours=3),
            timedelta(hours=4),
        )


@pytest.mark.parametrize(
    ("organization_id", "tenant_id", "domain"),
    [
        ("other-org", "tenant-a", "technology"),
        ("org", "tenant-b", "technology"),
        ("org", "tenant-a", "applications"),
    ],
)
def test_coverage_rejects_policy_outside_canonical_scope(
    organization_id, tenant_id, domain
):
    policy = FreshnessPolicy(
        "org",
        "tenant-a",
        "technology",
        timedelta(hours=1),
        timedelta(hours=2),
        timedelta(hours=4),
        timedelta(hours=8),
    )
    with pytest.raises(StewardshipPolicyScopeError, match="policy scope"):
        StewardshipService.coverage(
            organization_id=organization_id,
            tenant_id=tenant_id,
            domain=domain,
            inventory=[],
            policy=policy,
            now=NOW,
        )


def test_replay_and_revision_collision():
    repo = Repo()
    first = repo.create_review(item(), actor="steward", idempotency_key="k", correlation_id="c")
    assert (
        repo.create_review(item(), actor="steward", idempotency_key="k", correlation_id="c")
        is first
    )
    with pytest.raises(ValueError, match="idempotency"):
        repo.create_review(
            item(payload_hash="other"), actor="steward", idempotency_key="k", correlation_id="c"
        )


def test_transition_replay_returns_original_result_after_later_transition():
    repo = Repo()
    repo.create_review(item(), actor="steward", idempotency_key="create", correlation_id="c")
    transition_a = repo.transition(
        "r1",
        ReviewState.CLASSIFIED,
        expected_revision=1,
        actor="steward",
        rationale="classify",
        idempotency_key="transition-a",
        correlation_id="c-a",
    )
    transition_b = repo.transition(
        "r1",
        ReviewState.UNDER_REVIEW,
        expected_revision=2,
        actor="steward",
        rationale="review",
        idempotency_key="transition-b",
        correlation_id="c-b",
    )
    audit_count = len(repo.audit)

    replay_a = repo.transition(
        "r1",
        ReviewState.CLASSIFIED,
        expected_revision=1,
        actor="steward",
        rationale="classify",
        idempotency_key="transition-a",
        correlation_id="retry",
    )

    assert (transition_a.revision, transition_a.state) == (2, ReviewState.CLASSIFIED)
    assert (transition_b.revision, transition_b.state) == (3, ReviewState.UNDER_REVIEW)
    assert replay_a is transition_a
    assert replay_a.revision != repo.item.revision
    assert len(repo.audit) == audit_count


def test_concurrent_identical_transitions_converge_without_duplicate_mutation():
    repo = Repo()
    repo.create_review(item(), actor="steward", idempotency_key="create", correlation_id="c")

    def transition():
        return repo.transition(
            "r1",
            ReviewState.CLASSIFIED,
            expected_revision=1,
            actor="steward",
            rationale="classify",
            idempotency_key="same-key",
            correlation_id="concurrent",
        )

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda _: transition(), range(16)))

    assert {(result.state, result.revision) for result in results} == {
        (ReviewState.CLASSIFIED, 2)
    }
    assert repo.audit.count(("state_transition", "same-key")) == 1
    assert repo.item.revision == 2

    with pytest.raises(ValueError, match="idempotency"):
        repo.transition(
            "r1",
            ReviewState.UNDER_REVIEW,
            expected_revision=2,
            actor="steward",
            rationale="different",
            idempotency_key="same-key",
            correlation_id="conflict",
        )
    with pytest.raises(ValueError, match="revision"):
        repo.transition(
            "r1",
            ReviewState.UNDER_REVIEW,
            expected_revision=1,
            actor="steward",
            rationale="stale",
            idempotency_key="different-key",
            correlation_id="stale",
        )
def test_migrations_have_exact_tables_rls_security_and_append_only_controls():
    root = Path(__file__).parents[2]
    schema = (root / "migrations/data_fabric/0019_create_stewardship_persistence.sql").read_text()
    rpc = (root / "migrations/data_fabric/0020_create_stewardship_rpcs.sql").read_text()
    assert schema.count("create table if not exists") == 3
    for table in ("stewardship_policies", "stewardship_review_items", "stewardship_audit_events"):
        assert f"alter table data_fabric.{table} enable row level security" in schema
    assert (
        "before update on data_fabric.stewardship_audit_events" in schema
        and "before delete on data_fabric.stewardship_audit_events" in schema
    )
    assert rpc.count("security definer set search_path = data_fabric, pg_temp") == 2
    assert rpc.count("revoke all on function") == 2 and rpc.count("grant execute on function") == 2
    assert schema.count("tgrelid='data_fabric.stewardship_audit_events'::regclass") == 2
    assert schema.count("tgrelid='data_fabric.stewardship_policies'::regclass") == 1
    assert schema.count("tgrelid='data_fabric.stewardship_review_items'::regclass") == 1
    assert "resulting_revision integer not null" in schema
    assert "unique(organization_id,tenant_id,event_type,idempotency_key)" in schema
    assert rpc.count("pg_advisory_xact_lock") == 2
    assert rpc.count("v_existing.resulting_revision") >= 4
    current_row_replay = (
        "select * into v_current from data_fabric.stewardship_review_items "
        "where review_id=v_existing.review_id"
    )
    assert current_row_replay not in rpc


class Response:
    def __init__(self, data):
        self.data = data
        self.error = None


class Table:
    def __init__(self, row):
        self.row = row
        self.filters = []

    def select(self, *_):
        return self

    def eq(self, k, v):
        self.filters.append((k, v))
        return self

    def limit(self, *_):
        return self

    def execute(self):
        return Response([self.row] if all(self.row.get(k) == v for k, v in self.filters) else [])


class Client:
    def __init__(self, row):
        self.row = row
        self.calls = []
        self.table_op = None

    def rpc(self, name, params):
        self.calls.append((name, params))
        return Response({"review_id": "r1", "state": "discovered", "revision": 1})

    def table(self, _):
        self.table_op = Table(self.row)
        return self.table_op

    def execute(self, fn):
        return fn()


def test_supabase_adapter_scopes_reads_and_builds_authorized_rpc():
    row = {
        "review_id": "r1",
        "organization_id": "org",
        "tenant_id": "tenant-a",
        "review_key": "key",
        "review_type": "identity",
        "domain": "technology",
        "subject_type": "technology",
        "subject_id": "t1",
        "state": "discovered",
        "revision": 1,
        "payload_hash": "hash-a",
    }
    client = Client(row)
    context = TenantAuthorizationContext(
        "org",
        "tenant-a",
        "steward",
        "user",
        permissions=frozenset({"stewardship.review.create", "stewardship.review.transition"}),
        source_boundary="stewardship",
    )
    repo = SupabaseStewardshipRepository(client, context)
    assert (
        repo.create_review(
            item(), actor="steward", idempotency_key="k", correlation_id="c"
        ).review_id
        == "r1"
    )
    assert client.calls[0][0] == "stewardship_create_review"
    assert ("organization_id", "org") in client.table_op.filters and (
        "tenant_id",
        "tenant-a",
    ) in client.table_op.filters


def test_supabase_adapter_denies_cross_tenant_before_rpc():
    context = TenantAuthorizationContext(
        "org",
        "tenant-a",
        "steward",
        "user",
        permissions=frozenset({"stewardship.review.create"}),
        source_boundary="stewardship",
    )
    client = Client({})
    with pytest.raises(TenantAuthorizationError, match="tenant boundary"):
        SupabaseStewardshipRepository(client, context).create_review(
            item("tenant-b"), actor="steward", idempotency_key="k", correlation_id="c"
        )
    assert client.calls == []


def test_supabase_adapter_fails_closed_when_created_row_cannot_be_verified():
    context = TenantAuthorizationContext(
        "org",
        "tenant-a",
        "steward",
        "user",
        permissions=frozenset({"stewardship.review.create"}),
        source_boundary="stewardship",
    )
    client = Client({})
    with pytest.raises(StewardshipRepositoryInvariantError, match="create RPC succeeded"):
        SupabaseStewardshipRepository(client, context).create_review(
            item(), actor="steward", idempotency_key="k", correlation_id="c"
        )
    assert [call[0] for call in client.calls] == ["stewardship_create_review"]


def test_supabase_adapter_fails_closed_when_transitioned_row_cannot_be_verified():
    context = TenantAuthorizationContext(
        "org",
        "tenant-a",
        "steward",
        "user",
        permissions=frozenset({"stewardship.review.transition"}),
        source_boundary="stewardship",
    )
    client = Client({})
    with pytest.raises(StewardshipRepositoryInvariantError, match="transition RPC succeeded"):
        SupabaseStewardshipRepository(client, context).transition(
            "r1",
            ReviewState.CLASSIFIED,
            expected_revision=1,
            actor="steward",
            rationale="classify",
            idempotency_key="k",
            correlation_id="c",
        )
    assert [call[0] for call in client.calls] == ["stewardship_transition_review"]
