"""Fresh local cluster only. Never consumes a URL, credentials or existing service.

Authority fixtures model synthetic capabilities; they do not validate Supabase Auth.
"""

from __future__ import annotations

import csv
import io
import json
import os
import socket
import subprocess
import tempfile
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import psycopg2
import pytest
from psycopg2 import sql
from psycopg2.extras import Json, RealDictCursor, register_default_jsonb

from auth.authenticated_tenant import AuthenticatedTenantContext
from components.aws_financial_publication import render_aws_financial_publication
from repositories.aws_financial_evidence_repository import AwsFinancialEvidenceRepository
from repositories.aws_financial_evidence_repository import PostgresFinancialRpcClient as RpcClient
from services.aws_cur_ingestion_engine import AccountMapping
from services.aws_financial_dashboard_adapter import AwsFinancialDashboardAdapter
from services.aws_financial_import_contribution_verifier import (
    AwsFinancialImportContributionVerifier,
    DashboardQuery,
)
from services.aws_financial_ingestion_orchestrator import (
    AwsFinancialIngestionOrchestrator,
    IngestionGate,
    ReconciliationEvidence,
)
from services.demo_tenant_service import DEMO_ORGANIZATION_ID

ROOT = Path(__file__).resolve().parents[2]
QUERY = DashboardQuery("USD", date(2026, 7, 1), date(2026, 7, 31))
BINS = Path("C:/Program Files/PostgreSQL/18/bin")
register_default_jsonb(loads=lambda s: json.loads(s, parse_float=Decimal))


@pytest.fixture(scope="module")
def cluster():
    if os.getenv("NXR_DASH10_LOCAL_PG") != "1":
        pytest.skip("set NXR_DASH10_LOCAL_PG=1 to create a fresh synthetic-only local cluster")
    if not (BINS / "initdb.exe").is_file():
        pytest.skip("PostgreSQL 18 local initdb binary unavailable")
    with tempfile.TemporaryDirectory(prefix="nxr-dash10-synthetic-") as temp:
        temp = Path(temp).resolve()
        data = temp / "cluster"
        assert temp.is_relative_to(Path(tempfile.gettempdir()).resolve())
        assert temp.name.startswith("nxr-dash10-synthetic-") and not data.exists()
        owner = "nxr_test_" + uuid4().hex

        def run(*args):
            with (temp / "harness.log").open("a") as log:
                result = subprocess.run(
                    [str(BINS / args[0]), *map(str, args[1:])],
                    stdout=log,
                    stderr=subprocess.STDOUT,
                    timeout=45,
                    creationflags=subprocess.CREATE_NO_WINDOW,
                )
            assert result.returncode == 0, (temp / "harness.log").read_text()
            return result

        run("initdb.exe", "-D", data, "-U", owner, "-A", "trust", "--encoding=UTF8", "--no-locale")
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        run(
            "pg_ctl.exe",
            "-D",
            data,
            "-l",
            temp / "postgres.log",
            "-w",
            "start",
            "-o",
            f"-h 127.0.0.1 -p {port} -c max_connections=12 -c fsync=off",
        )

        def connect(dbname="postgres"):
            return psycopg2.connect(
                host="127.0.0.1", port=port, user=owner, dbname=dbname, connect_timeout=5
            )

        try:
            with connect() as connection:
                with connection.cursor() as cur:
                    cur.execute(
                        "select current_user, session_user, host(inet_server_addr()), "
                        "current_database()"
                    )
                    assert cur.fetchone() == (owner, owner, "127.0.0.1", "postgres")
                    cur.execute("show data_directory")
                    assert Path(cur.fetchone()[0]).resolve() == data.resolve()
                    cur.execute("select datname from pg_database where not datistemplate")
                    assert cur.fetchall() == [("postgres",)]
                    cur.execute("select system_identifier::text from pg_control_system()")
                    system_id = cur.fetchone()[0]
                    cur.execute(
                        "select count(*) from pg_class where relnamespace='public'::regnamespace"
                    )
                    assert cur.fetchone()[0] == 0
            print(
                f"ISOLATION: PostgreSQL18 fresh cluster={data}; system_identifier={system_id}; "
                f"loopback_port={port}; bootstrap_role={owner}; "
                "scope=synthetic-only; no pre-existing application relations; "
                "disposable/recreatable"
            )
            yield connect
        finally:
            run("pg_ctl.exe", "-D", data, "-w", "stop", "-m", "immediate")


@pytest.fixture
def db(cluster):
    name = "nxr_dash10_" + uuid4().hex
    conn = cluster()
    conn.autocommit = True
    with conn.cursor() as cur:
        cur.execute(sql.SQL("create database {}").format(sql.Identifier(name)))
    conn.close()
    connection = cluster(name)
    connection.autocommit = True
    with connection.cursor() as cur:
        # These are minimal canonical fixtures, not migration-chain replay.
        cur.execute("create schema auth; create table auth.users(id uuid primary key);")
        for role in ("anon", "authenticated", "service_role"):
            cur.execute(
                sql.SQL(
                    "do $$ begin create role {} nologin; exception when duplicate_object then "
                    "null; end $$"
                ).format(sql.Identifier(role))
            )
        cur.execute(
            "create table public.organizations(id uuid primary key); "
            "create table public.users(id uuid primary key,auth_user_id uuid unique references "
            "auth.users(id),org_id uuid references public.organizations(id),email text);"
        )
        foundation = (
            ROOT / "supabase/migrations/202607260001_aws_cur_ingestion_foundation.sql"
        ).read_text()
        import re

        definitions = re.findall(r"create table if not exists .*?\n\);", foundation, re.S)
        assert len(definitions) == 6
        for definition in definitions:
            cur.execute(definition)
        cur.execute((ROOT / "database/contracts/nxr_dash_10_financial_evidence.sql").read_text())
    yield connection, lambda: cluster(name)
    connection.close()


class Store:
    def __init__(self, connection):
        self.connection = connection

    def rows(self, statement, params=()):
        with self.connection.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(statement, params)
            return [dict(x) for x in cur.fetchall()]

    def insert(self, table, payload, conflict=None):
        columns = list(payload)
        statement = sql.SQL("insert into public.{} ({}) values ({})").format(
            sql.Identifier(table),
            sql.SQL(",").join(map(sql.Identifier, columns)),
            sql.SQL(",").join(sql.Placeholder() for _ in columns),
        )
        if conflict:
            statement += sql.SQL(" on conflict ({}) do update set {}").format(
                sql.SQL(",").join(map(sql.Identifier, conflict)),
                sql.SQL(",").join(
                    sql.SQL("{}=excluded.{}").format(sql.Identifier(k), sql.Identifier(k))
                    for k in columns
                    if k not in conflict
                ),
            )
        with self.connection.cursor() as cur:
            cur.execute(
                statement, [Json(v) if isinstance(v, (dict, list)) else v for v in payload.values()]
            )

    def find_import(self, context, payer, file_hash):
        rows = self.rows(
            "select * from cloud_cost_import where organization_id=%s and tenant_id=%s "
            "and payer_account_id=%s and source_file_sha256=%s",
            (context.organization_id, context.tenant_id, payer, file_hash),
        )
        return rows[0] if rows else None

    def create_import(self, context, payload):
        self.insert("cloud_cost_import", payload)

    def create_part(self, context, payload):
        self.insert(
            "cloud_cost_import_part",
            payload,
            ("organization_id", "tenant_id", "import_id", "part_key"),
        )

    def update_import(self, context, iid, payload):
        self.update("cloud_cost_import", "import_id", iid, context, payload)

    def update_part(self, context, iid, payload):
        self.update("cloud_cost_import_part", "import_part_id", iid, context, payload)

    def update(self, table, key, iid, context, payload):
        with self.connection.cursor() as cur:
            cur.execute(
                sql.SQL(
                    "update public.{} set {} where {}=%s and organization_id=%s and tenant_id=%s"
                ).format(
                    sql.Identifier(table),
                    sql.SQL(",").join(sql.SQL("{}=%s").format(sql.Identifier(k)) for k in payload),
                    sql.Identifier(key),
                ),
                [Json(v) if isinstance(v, dict) else v for v in payload.values()]
                + [iid, context.organization_id, context.tenant_id],
            )

    def write_facts(self, context, facts):
        for fact in facts:
            self.insert("cloud_cost_fact", fact)
        return len(facts)

    def upsert_reconciliation(self, context, payload):
        self.insert(
            "cloud_cost_reconciliation", payload, ("organization_id", "tenant_id", "import_id")
        )

    def list_account_mappings(self, context):
        return tuple(
            AccountMapping(**x)
            for x in self.rows(
                "select "
                "organization_id::text,tenant_id::text,payer_account_id,account_id,status,effect"
                "ive_from,effective_to,account_kind "
                "from cloud_account_mapping where organization_id=%s and tenant_id=%s",
                (context.organization_id, context.tenant_id),
            )
        )


def tenant(conn):
    org, actor = str(uuid4()), str(uuid4())
    with conn.cursor() as cur:
        cur.execute(
            "insert into organizations values(%s); insert into auth.users values(%s); "
            "insert into users values(%s,%s,%s,'fixture@example.test'); "
            "insert into cloud_cost_tenant_scope values(%s,%s,now())",
            (org, actor, str(uuid4()), actor, org, org, org),
        )
        for account, kind in (("PAYER-A", "payer"), ("MEMBER-A", "member")):
            cur.execute(
                "insert into "
                "cloud_account_mapping(cloud_account_mapping_id,organization_id,tenant_id,provid"
                "er,payer_account_id,account_id,account_kind,status,effective_from,mapping_sourc"
                "e) "
                "values(%s,%s,%s,'aws','PAYER-A',%s,%s,'active','2026-01-01','synthetic')",
                (str(uuid4()), org, org, account, kind),
            )
    return AuthenticatedTenantContext(
        org, "Synthetic", actor, "fixture@example.test", "cio", frozenset(), org
    )


def cur_bytes(cost, member="MEMBER-A"):
    from tests.cur_ingestion.test_aws_financial_ingestion_orchestrator import cur_bytes as fixture

    return fixture(cost=cost, member=member)


class Verifier:
    def __init__(self, context):
        self.context = context

    def verify(self, context):
        return context == self.context


class Reconciler:
    """Test-only independent CSV parser observes actual fixture bytes, never normalized totals."""

    def __init__(self, store):
        self.store = store

    def verify(self, context, iid, source, evidence):
        source.seek(0)
        raw = source.read()
        source.seek(0)
        rows = list(csv.DictReader(io.StringIO(raw.decode())))
        amount = sum((Decimal(r["lineItem/UnblendedCost"]) for r in rows), Decimal(0))
        facts = self.store.rows(
            "select unblended_cost from cloud_cost_fact where organization_id=%s and "
            "tenant_id=%s and import_id=%s",
            (context.organization_id, context.tenant_id, iid),
        )
        total = sum((f["unblended_cost"] for f in facts), Decimal(0))
        assert amount == total
        import hashlib

        digest = hashlib.sha256(raw).hexdigest()
        with self.store.connection.cursor() as cur:
            cur.execute(
                "insert into financial_evidence.source_attestation values "
                "(%s,%s,%s,%s,%s,%s,%s,'PAYER-A','USD','synthetic-csv-independent-v1','TEST_ONLY"
                "_ATTESTER',"
                "'2026-07-01','2026-07-31',%s,%s,now(),'verified')",
                (
                    context.organization_id,
                    context.tenant_id,
                    iid,
                    str(uuid4()),
                    "fixture:" + digest,
                    digest,
                    digest,
                    len(rows),
                    amount,
                ),
            )
            cur.execute(
                "update cloud_cost_reconciliation set "
                "source_cost_total=%s,normalized_cost_total=%s,variance_amount=%s,reconciled_at="
                "now() "
                "where organization_id=%s and tenant_id=%s and import_id=%s",
                (amount, total, amount - total, context.organization_id, context.tenant_id, iid),
            )
        return ReconciliationEvidence(
            context.organization_id,
            context.tenant_id,
            iid,
            digest,
            len(rows),
            len(facts),
            amount,
            total,
            "USD",
        )


def enable_test_authority(conn):
    # Only inside freshly created fixture database; never part of application or SQL candidate.
    with conn.cursor() as cur:
        cur.execute(
            "create or replace function financial_evidence.require_approved_authority() returns "
            "void "
            "language plpgsql security invoker set search_path=pg_catalog as $$ begin null; end $$"
        )


def grants(conn):
    def issue(op):
        assert op.context.organization_name == "Synthetic"
        grant = str(uuid4())
        with conn.cursor() as cur:
            cur.execute(
                "select financial_evidence.fingerprint(%s,%s,%s::uuid[],%s,%s,%s,%s,%s,%s,%s,%s)",
                (
                    op.context.organization_id,
                    op.context.tenant_id,
                    list(op.import_ids),
                    op.query.currency,
                    op.query.period_start,
                    op.query.period_end,
                    op.query.spans_multiple_periods,
                    op.permission,
                    op.trigger_import_id,
                    op.request_id,
                    op.expected_previous_generation_id,
                ),
            )
            fp = cur.fetchone()[0]
            cur.execute(
                "insert into financial_evidence.operation_authorization_grant values "
                "(%s,%s,%s,%s,%s,%s,now(),now()+interval '10 minutes',null,'TEST_ONLY_ISSUER')",
                (
                    op.context.organization_id,
                    op.context.tenant_id,
                    grant,
                    op.context.user_id,
                    op.permission,
                    fp,
                ),
            )
        return grant

    return issue


def ingest_pair(conn, factory):
    enable_test_authority(conn)
    context = tenant(conn)
    store = Store(conn)
    repository = AwsFinancialEvidenceRepository(RpcClient(factory), grant_provider=grants(conn))
    ids = []
    adapter = None
    for cost in ("12000", "8000"):
        adapter = AwsFinancialDashboardAdapter(
            repository,
            context=context,
            query=QUERY,
            prior_import_ids=tuple(ids),
            request_id=str(uuid4()),
            expected_previous_generation_id=adapter.receipt["generation_id"] if adapter else None,
            tenant_verifier=Verifier(context),
        )
        result = AwsFinancialIngestionOrchestrator(
            tenant_verifier=Verifier(context),
            account_ownership=store,
            persistence=store,
            reconciler=Reconciler(store),
            projection_refresher=adapter,
            dashboard=adapter,
            contribution_verifier=AwsFinancialImportContributionVerifier,
            evidence_provider=adapter,
        ).ingest(
            context,
            io.BytesIO(cur_bytes(cost)),
            "synthetic.csv",
            prior_import_ids=tuple(ids),
            dashboard_query=QUERY,
        )
        assert result.gate is IngestionGate.DASHBOARD_READY, result.reason
        ids.append(result.import_id)
    assert result.verified_total == Decimal("20000")
    return context, store, repository, adapter, tuple(ids)


def test_database_schema_default_deny(db):
    conn, factory = db
    with conn.cursor() as cur:
        cur.execute(
            "select count(*) from pg_tables where schemaname='financial_evidence' and rowsecurity"
        )
        assert cur.fetchone()[0] == 6
        cur.execute(
            "select "
            "has_function_privilege('service_role','public.read_aws_financial_contribution_evide"
            "nce_v1(uuid,uuid,uuid[],text,date,date,boolean,uuid)','execute')"
        )
        assert cur.fetchone()[0] is False
        with pytest.raises(psycopg2.errors.InsufficientPrivilege):
            cur.execute("select financial_evidence.require_approved_authority()")


def test_source_to_dashboard_20000(db):
    conn, factory = db
    context, store, repo, adapter, ids = ingest_pair(conn, factory)
    status = adapter.status(context, ids)
    assert status.readiness == "READY"
    assert status.posture.cloud_spend == Decimal("20000")
    assert status.posture.import_count == 2
    assert status.posture.persisted_facts == 2
    assert status.published_at == status.posture.generated_at

    class UI:
        def __init__(self):
            self.metrics = []

        def metric(self, *args):
            self.metrics.append(args)

        def __getattr__(self, name):
            return lambda *args, **kwargs: None

    ui = UI()
    render_aws_financial_publication(context, ui=ui, adapter=adapter, import_ids=ids)
    assert ("AWS total spend", "20,000.00 USD") in ui.metrics
    print(
        "E2E: source->engine->canonical facts->independent "
        "reconciliation->generation->RPC->adapter->dashboard = USD 20000"
    )


def test_negative_tenant_stale_unverified_and_demo(db):
    conn, factory = db
    context, store, repo, adapter, ids = ingest_pair(conn, factory)
    other = tenant(conn)
    assert adapter.status(other, ids).readiness == "NOT_READY"
    # B can get B's own capability but cannot use A's imports to obtain complete evidence.
    with pytest.raises(ValueError):
        repo.read(other, ids, QUERY)
    with conn.cursor() as cur:
        cur.execute(
            "update cloud_cost_fact set unblended_cost=unblended_cost+1 where import_id=%s",
            (ids[0],),
        )
    assert adapter.status(context, ids).readiness == "NOT_READY"
    with conn.cursor() as cur:
        cur.execute(
            "update cloud_cost_fact set unblended_cost=unblended_cost-1 where import_id=%s",
            (ids[0],),
        )
        cur.execute(
            "update financial_evidence.source_attestation set attestation_status='revoked' where "
            "import_id=%s",
            (ids[1],),
        )
    assert adapter.status(context, ids).readiness == "NOT_READY"
    demo = AuthenticatedTenantContext(
        DEMO_ORGANIZATION_ID,
        "Synthetic",
        str(uuid4()),
        "demo@example.test",
        "cio",
        frozenset(),
        DEMO_ORGANIZATION_ID,
    )
    with pytest.raises(ValueError):
        repo.read(demo, ids, QUERY)


def test_refresh_retry_atomic_rollback_and_immutable(db):
    conn, factory = db
    context, store, repo, adapter, ids = ingest_pair(conn, factory)
    receipt = adapter.receipt
    replay = repo.refresh(
        context,
        ids,
        QUERY,
        trigger_import_id=ids[-1],
        request_id=receipt["request_id"],
        expected_previous_generation_id=receipt["previous_generation_id"],
    )
    assert replay["replayed"] is True
    assert replay["generation_id"] == receipt["generation_id"]
    assert replay["published_at"] == receipt["published_at"]
    with conn.cursor() as cur:
        with pytest.raises(psycopg2.errors.CheckViolation):
            cur.execute(
                "update financial_evidence.published_fact_membership set included_in_resolved=false"
            )
        cur.execute(
            "create function public.fail_test_pointer() returns trigger language plpgsql as $$ "
            "begin raise exception 'synthetic failure'; end $$; "
            "create trigger fail_test_pointer after update on "
            "financial_evidence.published_generation_pointer for each row execute function "
            "public.fail_test_pointer()"
        )
    with pytest.raises(psycopg2.Error):
        repo.refresh(
            context,
            ids,
            QUERY,
            trigger_import_id=ids[-1],
            request_id=str(uuid4()),
            expected_previous_generation_id=receipt["generation_id"],
        )
    with conn.cursor() as cur:
        cur.execute(
            "select generation_id::text from financial_evidence.published_generation_pointer"
        )
        assert cur.fetchone()[0] == receipt["generation_id"]
        cur.execute("select count(*) from financial_evidence.projection_generation")
        assert cur.fetchone()[0] == 2


def test_unknown_account_blocks_and_concurrent_publication(db):
    conn, factory = db
    context, store, repo, adapter, ids = ingest_pair(conn, factory)
    # Grant issuance on main connection happens before concurrency to avoid shared connection use.
    requests = [str(uuid4()), str(uuid4())]
    clients = []
    for request in requests:
        from repositories.aws_financial_evidence_repository import FinancialOperation

        op = FinancialOperation(
            context, ids, QUERY, "refresh", ids[-1], request, adapter.receipt["generation_id"]
        )
        grant = grants(conn)(op)
        clients.append(
            AwsFinancialEvidenceRepository(RpcClient(factory), grant_provider=lambda op, g=grant: g)
        )

    def publish(pair):
        client, request = pair
        try:
            return client.refresh(
                context,
                ids,
                QUERY,
                trigger_import_id=ids[-1],
                request_id=request,
                expected_previous_generation_id=adapter.receipt["generation_id"],
            )
        except psycopg2.errors.SerializationFailure:
            return None

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(publish, zip(clients, requests)))
    assert sum(x is not None for x in results) == 1
    with conn.cursor() as cur:
        cur.execute(
            "update cloud_account_mapping set status='inactive' where organization_id=%s and "
            "account_kind='member'",
            (context.organization_id,),
        )
    with pytest.raises(psycopg2.errors.CheckViolation):
        repo.refresh(
            context,
            ids,
            QUERY,
            trigger_import_id=ids[-1],
            request_id=str(uuid4()),
            expected_previous_generation_id=next(x for x in results if x)["generation_id"],
        )
    assert adapter.status(context, ids).readiness == "NOT_READY"


def test_actual_role_denials_and_wrong_operation(db):
    conn, factory = db
    for role in ("anon", "authenticated", "service_role"):
        connection = factory()
        try:
            connection.autocommit = True
            with connection.cursor() as cur:
                cur.execute(sql.SQL("set role {}").format(sql.Identifier(role)))
                with pytest.raises(psycopg2.errors.InsufficientPrivilege):
                    cur.execute("select * from financial_evidence.source_attestation")
                with pytest.raises(psycopg2.errors.InsufficientPrivilege):
                    cur.execute(
                        "select "
                        "public.read_aws_financial_contribution_evidence_v1(null,null,null,null,"
                        "null,null,null,null)"
                    )
        finally:
            connection.close()
    context, store, repo, adapter, ids = ingest_pair(conn, factory)
    from repositories.aws_financial_evidence_repository import FinancialOperation

    read_grant = grants(conn)(FinancialOperation(context, ids, QUERY, "read"))
    wrong = AwsFinancialEvidenceRepository(RpcClient(factory), grant_provider=lambda op: read_grant)
    with pytest.raises(psycopg2.errors.InsufficientPrivilege):
        wrong.refresh(
            context,
            ids,
            QUERY,
            trigger_import_id=ids[-1],
            request_id=str(uuid4()),
            expected_previous_generation_id=adapter.receipt["generation_id"],
        )
    missing = AwsFinancialEvidenceRepository(
        RpcClient(factory), grant_provider=lambda op: str(uuid4())
    )
    with pytest.raises(psycopg2.errors.InsufficientPrivilege):
        missing.read(context, ids, QUERY)
    with conn.cursor() as cur:
        cur.execute("delete from users where auth_user_id=%s", (context.user_id,))
    with pytest.raises(psycopg2.errors.InsufficientPrivilege):
        wrong.read(context, ids, QUERY)


def test_consistent_reader_sees_complete_old_then_new_generation(db):
    conn, factory = db
    context, store, repo, adapter, ids = ingest_pair(conn, factory)
    reader = factory()
    reader.set_session(isolation_level="REPEATABLE READ", readonly=True)
    statement = (
        "select generation_id::text from financial_evidence.published_generation_pointer where "
        "organization_id=%s"
    )
    try:
        with reader.cursor() as cur:
            cur.execute(statement, (context.organization_id,))
            old = cur.fetchone()[0]
            receipt = repo.refresh(
                context,
                ids,
                QUERY,
                trigger_import_id=ids[-1],
                request_id=str(uuid4()),
                expected_previous_generation_id=old,
            )
            cur.execute(statement, (context.organization_id,))
            assert cur.fetchone()[0] == old
            cur.execute(
                "select count(*) from financial_evidence.published_fact_membership where "
                "generation_id=%s",
                (old,),
            )
            assert cur.fetchone()[0] == 2
        reader.commit()
        with reader.cursor() as cur:
            cur.execute(statement, (context.organization_id,))
            assert cur.fetchone()[0] == receipt["generation_id"]
    finally:
        reader.close()


def test_unverified_import_and_incomplete_commit_cannot_publish(db):
    conn, factory = db
    context, store, repo, adapter, ids = ingest_pair(conn, factory)
    with conn.cursor() as cur:
        cur.execute("update cloud_cost_import set status='failed' where import_id=%s", (ids[0],))
    with pytest.raises(psycopg2.errors.CheckViolation):
        repo.refresh(
            context,
            ids,
            QUERY,
            trigger_import_id=ids[-1],
            request_id=str(uuid4()),
            expected_previous_generation_id=adapter.receipt["generation_id"],
        )
    with conn.cursor() as cur:
        cur.execute(
            "select generation_id::text from financial_evidence.published_generation_pointer"
        )
        assert cur.fetchone()[0] == adapter.receipt["generation_id"]


def test_same_total_mutation_and_immutable_attestation(db):
    conn, factory = db
    context, store, repo, adapter, ids = ingest_pair(conn, factory)
    with conn.cursor() as cur:
        with pytest.raises(psycopg2.errors.CheckViolation):
            cur.execute(
                "update financial_evidence.source_attestation set source_cost_total=1 where "
                "import_id=%s",
                (ids[0],),
            )
        cur.execute(
            "update cloud_cost_fact set source_row_hash=repeat('a',64) where import_id=%s",
            (ids[0],),
        )
    assert adapter.status(context, ids).readiness == "NOT_READY"


def test_superseded_retry_and_changed_request_never_republish(db):
    conn, factory = db
    context, store, repo, adapter, ids = ingest_pair(conn, factory)
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("select * from financial_evidence.projection_generation order by published_at")
        old = dict(cur.fetchone())
    from repositories.aws_financial_evidence_repository import FinancialOperation

    op = FinancialOperation(
        context, (ids[0],), QUERY, "refresh", ids[0], str(old["request_id"]), None
    )
    grant = grants(conn)(op)
    value = (
        RpcClient(factory)
        .rpc(
            "refresh_tenant_cloud_financial_projections_v2",
            {
                "organization_id": context.organization_id,
                "tenant_id": context.tenant_id,
                "import_ids": [ids[0]],
                "currency": "USD",
                "period_start": "2026-07-01",
                "period_end": "2026-07-31",
                "spanning_periods": False,
                "trigger_import_id": ids[0],
                "request_id": str(old["request_id"]),
                "authorization_grant_id": grant,
                "expected_previous_generation_id": None,
            },
        )
        .execute()
        .data
    )
    assert value["replayed"] is True and value["is_current"] is False
    assert value["generation_id"] == str(old["generation_id"])
    with pytest.raises(psycopg2.errors.InsufficientPrivilege):
        repo.refresh(
            context,
            ids,
            QUERY,
            trigger_import_id=ids[-1],
            request_id=str(old["request_id"]),
            expected_previous_generation_id=adapter.receipt["generation_id"],
        )
    with conn.cursor() as cur:
        cur.execute(
            "select generation_id::text from financial_evidence.published_generation_pointer"
        )
        assert cur.fetchone()[0] == adapter.receipt["generation_id"]


def test_source_mismatch_blocks_publication_and_membership_append_denies(db):
    conn, factory = db
    context, store, repo, adapter, ids = ingest_pair(conn, factory)
    with conn.cursor() as cur:
        cur.execute(
            "update cloud_cost_reconciliation set source_cost_total=source_cost_total+1 where "
            "import_id=%s",
            (ids[0],),
        )
    with pytest.raises(psycopg2.errors.CheckViolation):
        repo.refresh(
            context,
            ids,
            QUERY,
            trigger_import_id=ids[-1],
            request_id=str(uuid4()),
            expected_previous_generation_id=adapter.receipt["generation_id"],
        )
    with conn.cursor() as cur:
        with pytest.raises(psycopg2.errors.CheckViolation):
            cur.execute(
                "insert into financial_evidence.published_fact_membership select * from "
                "financial_evidence.published_fact_membership limit 1"
            )


def test_adapter_rejects_forged_published_snapshots(db):
    conn, factory = db
    context, store, repo, adapter, ids = ingest_pair(conn, factory)
    original = repo.read

    def corrupted(*args):
        env = original(*args)
        env["publication"]["published_facts"][0]["unblended_cost"] = "0"
        return env

    repo.read = corrupted
    assert adapter.status(context, ids).readiness == "NOT_READY"


def test_tenant_b_publication_unchanged_by_tenant_a(db):
    conn, factory = db
    a, store_a, repo_a, adapter_a, ids_a = ingest_pair(conn, factory)
    b, store_b, repo_b, adapter_b, ids_b = ingest_pair(conn, factory)
    before = repo_b.read(b, ids_b, QUERY)["publication"]
    repo_a.refresh(
        a,
        ids_a,
        QUERY,
        trigger_import_id=ids_a[-1],
        request_id=str(uuid4()),
        expected_previous_generation_id=adapter_a.receipt["generation_id"],
    )
    after = repo_b.read(b, ids_b, QUERY)["publication"]
    assert after == before
    assert adapter_b.status(b, ids_b).posture.cloud_spend == Decimal("20000")
    with pytest.raises(ValueError):
        repo_b.read(b, ids_a, QUERY)
