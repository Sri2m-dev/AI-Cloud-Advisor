"""Opt-in PostgreSQL certification for the exact PVT-003A migration.

Set PVT003A_DATABASE_URL only for a disposable database. This test never
discovers or connects to a project, DEV, or Production database.
"""

from __future__ import annotations

import os
from pathlib import Path

import psycopg2
import pytest


DATABASE_URL = os.getenv("PVT003A_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason="requires an explicitly supplied disposable PVT003A_DATABASE_URL",
)

MIGRATION = (
    Path(__file__).parents[2]
    / "supabase"
    / "migrations"
    / "202607260001_aws_cur_ingestion_foundation.sql"
)

ORG_A = "11111111-1111-1111-1111-111111111111"
ORG_B = "22222222-2222-2222-2222-222222222222"
TENANT_FUTURE = "33333333-3333-3333-3333-333333333333"
IMPORT_A = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
IMPORT_B = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
IMPORT_A_CORRECTED = "cccccccc-cccc-cccc-cccc-cccccccccccc"
PART_A = "dddddddd-dddd-dddd-dddd-dddddddddddd"
PART_B = "eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee"
PART_A_CORRECTED = "12121212-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
FACT_A = "ffffffff-ffff-ffff-ffff-ffffffffffff"
FACT_B = "99999999-9999-9999-9999-999999999999"
FACT_A_CORRECTED = "13131313-aaaa-aaaa-aaaa-aaaaaaaaaaaa"


def _execute(connection, statement: str, params=None):
    with connection.cursor() as cursor:
        cursor.execute(statement, params)
        try:
            return cursor.fetchall()
        except psycopg2.ProgrammingError:
            return []


def _expect_database_error(connection, statement: str, params=None):
    with pytest.raises(psycopg2.Error):
        _execute(connection, statement, params)
    # The migration owns an explicit BEGIN/COMMIT while this connection uses
    # autocommit so it can replay complete migration scripts. Roll back the
    # explicit failed transaction rather than relying on driver state.
    with connection.cursor() as cursor:
        cursor.execute("rollback")


def _setup_supabase_compatible_fixture(connection):
    _execute(
        connection,
        """
        create schema if not exists auth;
        do $$ begin create role anon nologin; exception when duplicate_object then null; end $$;
        do $$ begin create role authenticated nologin; exception when duplicate_object then null; end $$;
        do $$ begin create role service_role nologin bypassrls; exception when duplicate_object then null; end $$;
        create table if not exists public.organizations (id uuid primary key);
        create table if not exists public.users (
            id uuid primary key,
            email text not null unique,
            org_id uuid not null references public.organizations(id)
        );
        create or replace function auth.jwt() returns jsonb language sql stable as $$
            select coalesce(nullif(current_setting('request.jwt.claims', true), '')::jsonb, '{}'::jsonb)
        $$;
        grant usage on schema public, auth to authenticated, anon, service_role;
        grant select on public.users to authenticated;
        alter table public.users enable row level security;
        drop policy if exists users_self on public.users;
        create policy users_self on public.users for select to authenticated
            using (lower(email) = lower(auth.jwt() ->> 'email'));
        """,
    )
    _execute(
        connection,
        "insert into public.organizations (id) values (%s), (%s), (%s)",
        (ORG_A, ORG_B, TENANT_FUTURE),
    )
    _execute(
        connection,
        "insert into public.users (id, email, org_id) values (%s, %s, %s), (%s, %s, %s)",
        (
            "aaaaaaaa-1111-1111-1111-111111111111",
            "a@example.test",
            ORG_A,
            "bbbbbbbb-2222-2222-2222-222222222222",
            "b@example.test",
            ORG_B,
        ),
    )


def _insert_import(connection, import_id, organization_id, tenant_id, file_hash, *, supersedes=None):
    _execute(
        connection,
        """
        insert into public.cloud_cost_import (
            import_id, organization_id, tenant_id, import_key, payer_account_id,
            billing_period_start, billing_period_end, source_file_name,
            source_file_sha256, compression, parser_profile, status,
            supersedes_import_id, source_evidence
        ) values (%s, %s, %s, %s, %s, date '2026-07-01', date '2026-07-31',
                  'synthetic-cur.csv.gz', %s, 'gzip', 'aws-cur-v1', 'completed', %s,
                  '{"synthetic": true}'::jsonb)
        """,
        (import_id, organization_id, tenant_id, f"import:{file_hash}", "payer-a", file_hash, supersedes),
    )


def _insert_part(connection, part_id, import_id, organization_id, tenant_id):
    _execute(
        connection,
        """
        insert into public.cloud_cost_import_part (
            import_part_id, organization_id, tenant_id, import_id, part_key,
            part_name, part_sha256, row_start, row_end, checkpoint_row, status
        ) values (%s, %s, %s, %s, %s, 'part-0001.csv.gz', %s, 1, 10, 10, 'completed')
        """,
        (part_id, organization_id, tenant_id, import_id, f"part:{part_id}", "1" * 64),
    )


def _insert_fact(connection, fact_id, import_id, part_id, organization_id, tenant_id, row_key, *, supersedes=None):
    _execute(
        connection,
        """
        insert into public.cloud_cost_fact (
            cloud_cost_fact_id, organization_id, tenant_id, import_id, import_part_id,
            source_row_key, source_row_hash, supersedes_fact_id, fact_status,
            payer_account_id, member_account_id, billing_period_start, billing_period_end,
            line_item_type, currency_code, unblended_cost, raw_fields, source_evidence
        ) values (%s, %s, %s, %s, %s, %s, %s, %s, 'active', 'payer-a', 'member-a1',
                  date '2026-07-01', date '2026-07-31', 'Usage', 'USD', 12.34,
                  '{"lineItem": "synthetic"}'::jsonb, '{"part": "synthetic"}'::jsonb)
        """,
        (fact_id, organization_id, tenant_id, import_id, part_id, row_key, "2" * 64, supersedes),
    )


def _set_authenticated(connection, email: str, tenant_id: str):
    _execute(connection, "set role authenticated")
    _execute(
        connection,
        "select set_config('request.jwt.claims', %s, false)",
        (f'{{"email":"{email}","tenant_id":"{tenant_id}"}}',),
    )


def _reset_role(connection):
    _execute(connection, "reset role")
    _execute(connection, "select set_config('request.jwt.claims', '', false)")


def test_pvt003a_disposable_postgres_certification():
    connection = psycopg2.connect(DATABASE_URL)
    connection.autocommit = True
    try:
        _setup_supabase_compatible_fixture(connection)
        migration_sql = MIGRATION.read_text(encoding="utf-8")

        # A pre-commit failure must leave no partially-created CUR tables.
        failed_migration = migration_sql.replace(
            "\ncommit;", "\nselect * from public.pvt003a_intentional_failure;\ncommit;"
        )
        _expect_database_error(connection, failed_migration)
        assert _execute(connection, "select to_regclass('public.cloud_cost_import')") == [(None,)]

        _execute(connection, migration_sql)
        _execute(connection, migration_sql)  # approved replay/idempotency check

        expected_tables = {
            "cloud_cost_tenant_scope",
            "cloud_cost_import",
            "cloud_cost_import_part",
            "cloud_account_mapping",
            "cloud_cost_fact",
            "cloud_cost_reconciliation",
        }
        rows = _execute(
            connection,
            """
            select c.relname, c.relrowsecurity
            from pg_class c join pg_namespace n on n.oid = c.relnamespace
            where n.nspname = 'public' and c.relname = any(%s)
            """,
            (list(expected_tables),),
        )
        assert {name for name, _ in rows} == expected_tables
        assert all(enabled for _, enabled in rows)
        indexes = {row[0] for row in _execute(connection, "select indexname from pg_indexes where schemaname = 'public'")}
        assert {
            "cloud_cost_import_tenant_period_idx",
            "cloud_cost_import_part_resume_idx",
            "cloud_account_mapping_lookup_idx",
            "cloud_cost_fact_tenant_period_idx",
            "cloud_cost_fact_rollup_idx",
            "cloud_cost_reconciliation_tenant_period_idx",
        } <= indexes

        # Current convention is seeded; a future tenant can be associated with
        # organization A without allowing organization A to use organization B.
        assert _execute(
            connection,
            "select organization_id, tenant_id from public.cloud_cost_tenant_scope order by organization_id",
        ) == [(ORG_A, ORG_A), (ORG_B, ORG_B), (TENANT_FUTURE, TENANT_FUTURE)]
        _execute(
            connection,
            "insert into public.cloud_cost_tenant_scope (organization_id, tenant_id) values (%s, %s)",
            (ORG_A, TENANT_FUTURE),
        )

        _execute(connection, "set role service_role")
        _insert_import(connection, IMPORT_A, ORG_A, ORG_A, "a" * 64)
        _insert_import(connection, IMPORT_B, ORG_B, ORG_B, "b" * 64)
        _insert_import(connection, IMPORT_A_CORRECTED, ORG_A, ORG_A, "c" * 64, supersedes=IMPORT_A)
        _expect_database_error(
            connection,
            """
            insert into public.cloud_cost_import (
                import_id, organization_id, tenant_id, import_key, payer_account_id,
                billing_period_start, billing_period_end, source_file_name,
                source_file_sha256, compression, parser_profile, status
            ) values ('12121212-1212-1212-1212-121212121212', %s, %s, 'duplicate', 'payer-a',
                      date '2026-07-01', date '2026-07-31', 'duplicate.csv', %s, 'csv', 'aws-cur-v1', 'received')
            """,
            (ORG_A, ORG_A, "a" * 64),
        )
        _insert_part(connection, PART_A, IMPORT_A, ORG_A, ORG_A)
        _insert_part(connection, PART_B, IMPORT_B, ORG_B, ORG_B)
        _insert_part(
            connection,
            PART_A_CORRECTED,
            IMPORT_A_CORRECTED,
            ORG_A,
            ORG_A,
        )
        _insert_fact(connection, FACT_A, IMPORT_A, PART_A, ORG_A, ORG_A, "row:a")
        _insert_fact(connection, FACT_B, IMPORT_B, PART_B, ORG_B, ORG_B, "row:b")
        _insert_fact(
            connection,
            FACT_A_CORRECTED,
            IMPORT_A_CORRECTED,
            PART_A_CORRECTED,
            ORG_A,
            ORG_A,
            "row:a-corrected",
            supersedes=FACT_A,
        )
        _expect_database_error(
            connection,
            """
            insert into public.cloud_cost_fact (
                cloud_cost_fact_id, organization_id, tenant_id, import_id, import_part_id,
                source_row_key, source_row_hash, fact_status, payer_account_id, member_account_id,
                billing_period_start, billing_period_end, line_item_type, currency_code
            ) values ('14141414-1414-1414-1414-141414141414', %s, %s, %s, %s, 'row:a', %s,
                      'active', 'payer-a', 'member-a1', date '2026-07-01', date '2026-07-31', 'Usage', 'USD')
            """,
            (ORG_A, ORG_A, IMPORT_A, PART_A, "2" * 64),
        )
        _expect_database_error(
            connection,
            """
            insert into public.cloud_cost_import (
                import_id, organization_id, tenant_id, import_key, payer_account_id,
                billing_period_start, billing_period_end, source_file_name,
                source_file_sha256, compression, parser_profile, status, supersedes_import_id
            ) values ('15151515-1515-1515-1515-151515151515', %s, %s, 'cross-supersession', 'payer-a',
                      date '2026-07-01', date '2026-07-31', 'cross.csv', %s, 'csv', 'aws-cur-v1', 'received', %s)
            """,
            (ORG_A, ORG_A, "5" * 64, IMPORT_B),
        )
        _expect_database_error(
            connection,
            """
            insert into public.cloud_cost_fact (
                cloud_cost_fact_id, organization_id, tenant_id, import_id, import_part_id,
                source_row_key, source_row_hash, supersedes_fact_id, fact_status,
                payer_account_id, member_account_id, billing_period_start, billing_period_end,
                line_item_type, currency_code
            ) values ('16161616-1616-1616-1616-161616161616', %s, %s, %s, %s, 'cross-superseded', %s, %s,
                      'active', 'payer-a', 'member-a1', date '2026-07-01', date '2026-07-31', 'Usage', 'USD')
            """,
            (ORG_A, ORG_A, IMPORT_A, PART_A, "6" * 64, FACT_B),
        )
        assert _execute(
            connection,
            "select raw_fields ->> 'lineItem', source_evidence ->> 'part' from public.cloud_cost_fact where cloud_cost_fact_id = %s",
            (FACT_A,),
        ) == [("synthetic", "synthetic")]

        _execute(
            connection,
            """
            insert into public.cloud_account_mapping (
                cloud_account_mapping_id, organization_id, tenant_id, provider,
                payer_account_id, account_id, account_kind, status, effective_from, mapping_source
            ) values
            ('10101010-1010-1010-1010-101010101010', %s, %s, 'aws', 'payer-a', 'member-a1', 'member', 'active', date '2026-07-01', 'synthetic'),
            ('20202020-2020-2020-2020-202020202020', %s, %s, 'aws', 'payer-a', 'unknown-member', 'member', 'quarantined', date '2026-07-01', 'synthetic'),
            ('30303030-3030-3030-3030-303030303030', %s, %s, 'aws', 'payer-b', 'member-b1', 'member', 'active', date '2026-07-01', 'synthetic')
            """,
            (ORG_A, ORG_A, ORG_A, ORG_A, ORG_B, ORG_B),
        )
        _execute(
            connection,
            """
            insert into public.cloud_cost_reconciliation (
                cloud_cost_reconciliation_id, organization_id, tenant_id, import_id,
                billing_period_start, billing_period_end, payer_account_id,
                source_row_count, normalized_row_count, rejected_row_count, duplicate_row_count,
                source_cost_total, normalized_cost_total, variance_amount, currency_code, status
            ) values
            ('40404040-4040-4040-4040-404040404040', %s, %s, %s, date '2026-07-01', date '2026-07-31', 'payer-a', 10, 10, 0, 0, 12.34, 12.34, 0, 'USD', 'reconciled'),
            ('50505050-5050-5050-5050-505050505050', %s, %s, %s, date '2026-07-01', date '2026-07-31', 'payer-b', 10, 10, 0, 0, 56.78, 56.78, 0, 'USD', 'reconciled')
            """,
            (ORG_A, ORG_A, IMPORT_A, ORG_B, ORG_B, IMPORT_B),
        )
        _expect_database_error(
            connection,
            """
            insert into public.cloud_account_mapping (
                cloud_account_mapping_id, organization_id, tenant_id, provider,
                payer_account_id, account_id, account_kind, status, effective_from, mapping_source
            ) values ('60606060-6060-6060-6060-606060606060', %s, %s, 'aws', 'payer-a', 'cross', 'member', 'active', date '2026-07-01', 'synthetic')
            """,
            (ORG_A, ORG_B),
        )
        _expect_database_error(
            connection,
            """
            insert into public.cloud_cost_import_part (
                import_part_id, organization_id, tenant_id, import_id, part_key,
                part_name, part_sha256, row_start, status
            ) values ('70707070-7070-7070-7070-707070707070', %s, %s, %s, 'cross', 'cross.csv', %s, 1, 'pending')
            """,
            (ORG_A, ORG_A, IMPORT_B, "7" * 64),
        )
        _expect_database_error(
            connection,
            """
            insert into public.cloud_cost_fact (
                cloud_cost_fact_id, organization_id, tenant_id, import_id, import_part_id,
                source_row_key, source_row_hash, fact_status, payer_account_id, member_account_id,
                billing_period_start, billing_period_end, line_item_type, currency_code
            ) values ('80808080-8080-8080-8080-808080808080', %s, %s, %s, %s, 'cross', %s, 'active', 'payer-a', 'member-a1', date '2026-07-01', date '2026-07-31', 'Usage', 'USD')
            """,
            (ORG_A, ORG_A, IMPORT_B, PART_B, "8" * 64),
        )
        _expect_database_error(
            connection,
            """
            insert into public.cloud_cost_reconciliation (
                cloud_cost_reconciliation_id, organization_id, tenant_id, import_id,
                billing_period_start, billing_period_end, payer_account_id,
                source_row_count, normalized_row_count, rejected_row_count, duplicate_row_count, status
            ) values ('90909090-9090-9090-9090-909090909090', %s, %s, %s, date '2026-07-01', date '2026-07-31', 'payer-a', 0, 0, 0, 0, 'pending')
            """,
            (ORG_A, ORG_A, IMPORT_B),
        )
        _reset_role(connection)

        _set_authenticated(connection, "a@example.test", ORG_A)
        assert _execute(connection, "select count(*) from public.cloud_cost_import") == [(2,)]
        assert _execute(connection, "select count(*) from public.cloud_cost_import_part") == [(2,)]
        assert _execute(connection, "select count(*) from public.cloud_account_mapping") == [(2,)]
        assert _execute(connection, "select count(*) from public.cloud_cost_reconciliation") == [(1,)]
        _expect_database_error(connection, "select * from public.cloud_cost_fact")
        _expect_database_error(
            connection,
            "update public.cloud_cost_import set status = 'failed' where import_id = %s",
            (IMPORT_A,),
        )
        _reset_role(connection)

        _set_authenticated(connection, "b@example.test", ORG_B)
        assert _execute(connection, "select count(*) from public.cloud_cost_import") == [(1,)]
        assert _execute(connection, "select count(*) from public.cloud_account_mapping") == [(1,)]
        assert _execute(connection, "select count(*) from public.cloud_cost_reconciliation") == [(1,)]
        _reset_role(connection)

        _execute(connection, "set role anon")
        _expect_database_error(connection, "select * from public.cloud_cost_import")
        _expect_database_error(connection, "insert into public.cloud_cost_import default values")
        _reset_role(connection)
    finally:
        connection.close()
