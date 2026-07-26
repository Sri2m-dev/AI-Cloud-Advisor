"""Opt-in PVT-003B engine certification against disposable PostgreSQL only."""
from __future__ import annotations

import io
import json
import os
import uuid
from pathlib import Path

import psycopg2
import pytest
from psycopg2 import sql
from psycopg2.extras import Json, RealDictCursor

from data_fabric.foundation import TenantContext
from services.aws_cur_ingestion_engine import AccountMapping, AwsCurIngestionEngine, CurState


DATABASE_URL = os.getenv("PVT003B_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason="requires an explicitly supplied disposable PVT003B_DATABASE_URL",
)
MIGRATION = Path(__file__).parents[2] / "supabase/migrations/202607260001_aws_cur_ingestion_foundation.sql"
HEADERS = [
    "bill_payer_account_id", "line_item_usage_account_id",
    "bill_billing_period_start_date", "bill_billing_period_end_date",
    "line_item_usage_start_date", "line_item_usage_end_date",
    "product_servicecode", "line_item_product_code", "line_item_line_item_type",
    "line_item_unblended_cost", "line_item_currency_code",
]


def _cur(member: str = "member-a", cost: str = "1.25") -> bytes:
    row = [
        "payer-a", member, "2026-07-01T00:00:00Z", "2026-07-31T23:59:59Z",
        "2026-07-02T00:00:00Z", "2026-07-02T01:00:00Z", "EC2", "AmazonEC2",
        "Usage", cost, "USD",
    ]
    return b"\xef\xbb\xbf" + (
        ",".join(HEADERS) + "\n" + ",".join(row) + "\n"
    ).encode()


class PostgresStore:
    def __init__(self, connection):
        self.connection = connection

    @staticmethod
    def _values(payload):
        return [Json(value) if isinstance(value, (dict, list)) else value for value in payload.values()]

    def _insert(self, table, payload, conflict=None):
        columns = list(payload)
        statement = sql.SQL("insert into {} ({}) values ({})").format(
            sql.Identifier("public", table),
            sql.SQL(", ").join(map(sql.Identifier, columns)),
            sql.SQL(", ").join(sql.Placeholder() for _ in columns),
        )
        if conflict:
            statement += sql.SQL(" on conflict ({}) do update set {} ").format(
                sql.SQL(", ").join(map(sql.Identifier, conflict)),
                sql.SQL(", ").join(
                    sql.SQL("{} = excluded.{}").format(sql.Identifier(col), sql.Identifier(col))
                    for col in columns if col not in conflict
                ),
            )
        with self.connection.cursor() as cursor:
            cursor.execute(statement, self._values(payload))

    def find_import(self, context, payer, file_hash):
        with self.connection.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(
                "select * from public.cloud_cost_import where organization_id=%s and tenant_id=%s and payer_account_id=%s and source_file_sha256=%s",
                (context.organization_id, context.tenant_id, payer, file_hash),
            )
            return cursor.fetchone()

    def list_account_mappings(self, context):
        with self.connection.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(
                "select organization_id, tenant_id, payer_account_id, account_id, status from public.cloud_account_mapping where organization_id=%s and tenant_id=%s",
                (context.organization_id, context.tenant_id),
            )
            return tuple(AccountMapping(**dict(row)) for row in cursor.fetchall())

    def create_import(self, context, payload): self._insert("cloud_cost_import", payload)
    def create_part(self, context, payload): self._insert("cloud_cost_import_part", payload, ("organization_id", "tenant_id", "import_id", "part_key"))

    def update_import(self, context, import_id, payload): self._update("cloud_cost_import", "import_id", import_id, payload)
    def update_part(self, context, part_id, payload): self._update("cloud_cost_import_part", "import_part_id", part_id, payload)

    def _update(self, table, key, value, payload):
        columns = list(payload)
        with self.connection.cursor() as cursor:
            cursor.execute(
                sql.SQL("update {} set {} where {} = %s").format(
                    sql.Identifier("public", table),
                    sql.SQL(", ").join(sql.SQL("{} = %s").format(sql.Identifier(col)) for col in columns),
                    sql.Identifier(key),
                ),
                self._values(payload) + [value],
            )

    def write_facts(self, context, facts):
        written = 0
        for fact in facts:
            columns = list(fact)
            with self.connection.cursor() as cursor:
                cursor.execute(
                    sql.SQL("insert into public.cloud_cost_fact ({}) values ({}) on conflict (organization_id, tenant_id, import_id, source_row_hash) do nothing").format(
                        sql.SQL(", ").join(map(sql.Identifier, columns)),
                        sql.SQL(", ").join(sql.Placeholder() for _ in columns),
                    ),
                    self._values(fact),
                )
                written += cursor.rowcount
        return written

    def upsert_reconciliation(self, context, payload):
        self._insert("cloud_cost_reconciliation", payload, ("organization_id", "tenant_id", "import_id"))


def test_pvt003b_engine_disposable_postgres_certification():
    connection = psycopg2.connect(DATABASE_URL)
    connection.autocommit = True
    org = str(uuid.uuid4())
    try:
        with connection.cursor() as cursor:
            cursor.execute("create schema if not exists auth")
            cursor.execute("do $$ begin create role anon nologin; exception when duplicate_object then null; end $$")
            cursor.execute("do $$ begin create role authenticated nologin; exception when duplicate_object then null; end $$")
            cursor.execute("do $$ begin create role service_role nologin bypassrls; exception when duplicate_object then null; end $$")
            cursor.execute("create table public.organizations (id uuid primary key)")
            cursor.execute("create table public.users (id uuid primary key, email text not null, org_id uuid not null references public.organizations(id))")
            cursor.execute("create or replace function auth.jwt() returns jsonb language sql stable as $$ select '{}'::jsonb $$")
            cursor.execute("insert into public.organizations values (%s)", (org,))
            cursor.execute(MIGRATION.read_text(encoding="utf-8"))
            cursor.execute(MIGRATION.read_text(encoding="utf-8"))
            cursor.execute(
                "insert into public.cloud_account_mapping (cloud_account_mapping_id, organization_id, tenant_id, provider, payer_account_id, account_id, account_kind, status, effective_from, mapping_source) values (%s,%s,%s,'aws','payer-a','payer-a','payer','active',date '2026-07-01','synthetic'),(%s,%s,%s,'aws','payer-a','member-a','member','active',date '2026-07-01','synthetic')",
                (str(uuid.uuid4()), org, org, str(uuid.uuid4()), org, org),
            )
        context = TenantContext(org, org)
        store = PostgresStore(connection)
        first = AwsCurIngestionEngine(store).ingest(context, io.BytesIO(_cur()), "synthetic.csv")
        replay = AwsCurIngestionEngine(store).ingest(context, io.BytesIO(_cur()), "synthetic.csv")
        quarantine = AwsCurIngestionEngine(store).ingest(context, io.BytesIO(_cur("unknown")), "unknown.csv")
        assert first.status is CurState.COMPLETED and replay.replayed
        assert quarantine.status is CurState.AWAITING_ACCOUNT_RESOLUTION
        with connection.cursor() as cursor:
            cursor.execute("select count(*) from public.cloud_cost_fact")
            assert cursor.fetchone() == (2,)
            cursor.execute("select count(*) from public.cloud_cost_reconciliation")
            assert cursor.fetchone() == (2,)
    finally:
        connection.close()
