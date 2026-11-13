"""Test-only disposable replay for the blocked Nexora PostgreSQL SQL chain.

This tool is deliberately not a deployment runner. It accepts no database URL,
container ID, volume, host port, or service target.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import time
import uuid
from pathlib import Path
from typing import Callable, Mapping, Sequence
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = Path("docs/cmp/CMP-P6-DEF-001/migration_manifest.json")
AUTH_FIXTURE = Path("tests/fixtures/postgres_replay/auth_prerequisites.sql")
APPROVED_IMAGE = "postgres@sha256:33f923b05f64ca54ac4401c01126a6b92afe839a0aa0a52bc5aeb5cc958e5f20"
CONTAINER_PREFIX = "nexora-test-only-pg-replay-"
OWNERSHIP_LABEL = "org.nexora.test-only-postgres-replay"
PUBLIC_STEP = "dated_public"
DATA_FABRIC_STEP = "data_fabric"
MANIFEST_STEP_NAMES = (
    "public_bootstrap",
    PUBLIC_STEP,
    DATA_FABRIC_STEP,
    "universal_evidence_local_lifecycle",
    "source_fact_local_authority",
    "live_connectors",
)
CONTAINER_READY_TIMEOUT_SECONDS = 60
CONTAINER_START_TIMEOUT_SECONDS = 90
MAX_SQL_TIMEOUT_SECONDS = 180
DOCKER_ENDPOINT_ENV = {
    "DOCKER_HOST",
    "DOCKER_CONTEXT",
    "DOCKER_TLS_VERIFY",
    "DOCKER_CERT_PATH",
    "DOCKER_API_VERSION",
    "DOCKER_CONFIG",
}
CATALOG_POLICY_IDS = (
    "public.users.users_select_self",
    "public.organizations.organizations_select_own",
    "public.clients.clients_select_own_org",
    "public.recommendations.recommendations_select_own_org",
    "public.recommendations.recommendations_insert_own_org",
    "public.report_history.report_history_select_own_org",
    "public.report_history.report_history_insert_own_org",
    "public.cloud_cost_import.cloud_cost_import_select_own_org",
    "public.cloud_cost_import_part.cloud_cost_import_part_select_own_org",
    "public.cloud_account_mapping.cloud_account_mapping_select_own_org",
    "public.cloud_cost_reconciliation.cloud_cost_reconciliation_select_own_org",
)
CATALOG_POLICY_FAILURE_CATEGORIES = (
    "CAT-POLICY-MISSING",
    "CAT-POLICY-METADATA",
    "CAT-POLICY-USING-PREDICATE",
    "CAT-POLICY-WITH-CHECK",
    "CAT-POLICY-CLAUSE-SHAPE",
    "CAT-AUTH-UUID-BINDING",
)
CATALOG_ASSERTION_IDS = frozenset(
    {
        "CAT-AUTH-TABLES-MISSING",
        "CAT-COLUMN-MISSING",
        "CAT-AUTH-UUID-COLUMN-MISSING",
        "CAT-AUTH-UUID-FK-MISSING",
        "CAT-AUTH-UUID-INDEX-MISSING",
        "CAT-RLS-MISSING",
        "CAT-UNEXPECTED-POLICY",
        "CAT-LEGACY-EMAIL-POLICY",
        "CAT-FUNCTION-MISSING",
        "CAT-SECURITY-DEFINER-SEARCH-PATH",
        "CAT-FUNCTION-PUBLIC-EXECUTE",
        "CAT-FUNCTION-GRANT",
        "CAT-AUTH-TRIGGER-REMAINS",
        "CAT-AUTH-FK-COUNT",
    }
) | frozenset(
    f"{category}:{policy_id}"
    for category in CATALOG_POLICY_FAILURE_CATEGORIES
    for policy_id in CATALOG_POLICY_IDS
)

Runner = Callable[..., subprocess.CompletedProcess[str]]


class ReplayError(RuntimeError):
    """A preflight, isolation, migration, or assertion failure."""


class DockerCommandTimeout(ReplayError):
    """A Docker CLI command timed out."""


CATALOG_ASSERTIONS = r"""
DO $assert$
DECLARE
    expected record;
    actual_count integer;
    auth_users_oid oid := to_regclass('auth.users');
    users_oid oid := to_regclass('public.users');
    function_oid oid;
    function_signature text;
    actual_policy record;
    policy_expression text;
    normalized_policy text;
BEGIN
    IF auth_users_oid IS NULL OR users_oid IS NULL THEN
        RAISE EXCEPTION 'NEXORA_CATALOG_ASSERTION: CAT-AUTH-TABLES-MISSING';
    END IF;

    FOR expected IN
        SELECT * FROM (VALUES
            ('organizations', 'id', 'uuid'),
            ('users', 'id', 'uuid'),
            ('users', 'org_id', 'uuid'),
            ('users', 'auth_user_id', 'uuid'),
            ('clients', 'org_id', 'uuid'),
            ('recommendations', 'org_id', 'uuid'),
            ('report_history', 'org_id', 'text'),
            ('report_history', 'tenant_id', 'text'),
            ('nexora_v1_approval_requests', 'organization_id', 'text'),
            ('nexora_v1_approval_history', 'tenant_id', 'text')
        ) AS column_contract(tablename, columnname, typename)
    LOOP
        IF NOT EXISTS (
            SELECT 1
            FROM pg_attribute a
            WHERE a.attrelid = to_regclass('public.' || expected.tablename)
              AND a.attname = expected.columnname AND NOT a.attisdropped
              AND a.atttypid = expected.typename::regtype
        ) THEN
            RAISE EXCEPTION 'NEXORA_CATALOG_ASSERTION: CAT-COLUMN-MISSING';
        END IF;
    END LOOP;

    IF NOT EXISTS (
        SELECT 1 FROM pg_attribute
        WHERE attrelid = users_oid AND attname = 'auth_user_id'
          AND atttypid = 'uuid'::regtype AND NOT attisdropped
    ) THEN
        RAISE EXCEPTION 'NEXORA_CATALOG_ASSERTION: CAT-AUTH-UUID-COLUMN-MISSING';
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid = users_oid AND contype = 'f'
          AND confrelid = auth_users_oid
          AND pg_get_constraintdef(oid) ILIKE '%auth_user_id%'
    ) THEN
        RAISE EXCEPTION 'NEXORA_CATALOG_ASSERTION: CAT-AUTH-UUID-FK-MISSING';
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_index i
        JOIN pg_class idx ON idx.oid = i.indexrelid
        WHERE i.indrelid = users_oid AND idx.relname = 'users_auth_user_id_uidx'
          AND i.indisunique AND pg_get_expr(i.indpred, i.indrelid) IS NOT NULL
    ) THEN
        RAISE EXCEPTION 'NEXORA_CATALOG_ASSERTION: CAT-AUTH-UUID-INDEX-MISSING';
    END IF;

    FOR expected IN
        SELECT * FROM (VALUES
            ('users', 'users_select_self', 'SELECT',
             '~auth_user_id=\(selectauth\.uid\(', NULL,
             'public.users.users_select_self'),
            ('organizations', 'organizations_select_own', 'SELECT',
             '~id=\(selectu\.org_idfrom(public\.)?usersuwhere', NULL,
             'public.organizations.organizations_select_own'),
            ('clients', 'clients_select_own_org', 'SELECT',
             '~org_id=\(selectu\.org_idfrom(public\.)?usersuwhere', NULL,
             'public.clients.clients_select_own_org'),
            ('recommendations', 'recommendations_select_own_org', 'SELECT',
             '~org_id=\(selectu\.org_idfrom(public\.)?usersuwhere', NULL,
             'public.recommendations.recommendations_select_own_org'),
            ('recommendations', 'recommendations_insert_own_org', 'INSERT',
             NULL, '~org_id=\(selectu\.org_idfrom(public\.)?usersuwhere',
             'public.recommendations.recommendations_insert_own_org'),
            ('report_history', 'report_history_select_own_org', 'SELECT',
             '~\(?org_idisnotnull\)?&~\(?tenant_idisnotnull\)?&~org_id=\(select\(?u\.org_id\)?::text\)?(asorg_id)?from(public\.)?users(as)?uwhere&~tenant_id=\(select\(?u\.org_id\)?::text\)?(asorg_id)?from(public\.)?users(as)?uwhere',
             NULL, 'public.report_history.report_history_select_own_org'),
            ('report_history', 'report_history_insert_own_org', 'INSERT',
             NULL,
             '~\(?org_idisnotnull\)?&~\(?tenant_idisnotnull\)?&~org_id=\(select\(?u\.org_id\)?::text\)?(asorg_id)?from(public\.)?users(as)?uwhere&~tenant_id=\(select\(?u\.org_id\)?::text\)?(asorg_id)?from(public\.)?users(as)?uwhere',
             'public.report_history.report_history_insert_own_org'),
            ('cloud_cost_import', 'cloud_cost_import_select_own_org', 'SELECT',
             '~organization_id=\(selectu\.org_idfrom(public\.)?usersuwhere&~tenant_id=\(selectu\.org_idfrom(public\.)?usersuwhere',
             NULL, 'public.cloud_cost_import.cloud_cost_import_select_own_org'),
            ('cloud_cost_import_part', 'cloud_cost_import_part_select_own_org', 'SELECT',
             '~organization_id=\(selectu\.org_idfrom(public\.)?usersuwhere&~tenant_id=\(selectu\.org_idfrom(public\.)?usersuwhere',
             NULL, 'public.cloud_cost_import_part.cloud_cost_import_part_select_own_org'),
            ('cloud_account_mapping', 'cloud_account_mapping_select_own_org', 'SELECT',
             '~organization_id=\(selectu\.org_idfrom(public\.)?usersuwhere&~tenant_id=\(selectu\.org_idfrom(public\.)?usersuwhere',
             NULL, 'public.cloud_account_mapping.cloud_account_mapping_select_own_org'),
            ('cloud_cost_reconciliation', 'cloud_cost_reconciliation_select_own_org', 'SELECT',
             '~organization_id=\(selectu\.org_idfrom(public\.)?usersuwhere&~tenant_id=\(selectu\.org_idfrom(public\.)?usersuwhere',
             NULL, 'public.cloud_cost_reconciliation.cloud_cost_reconciliation_select_own_org')
        ) AS policy_contract(
            tablename, policyname, command, using_pattern, check_pattern, assertion_id
        )
    LOOP
        IF NOT EXISTS (
            SELECT 1 FROM pg_class c
            WHERE c.oid = to_regclass('public.' || expected.tablename)
              AND c.relrowsecurity
        ) THEN
            RAISE EXCEPTION 'NEXORA_CATALOG_ASSERTION: CAT-RLS-MISSING';
        END IF;
        SELECT p.* INTO actual_policy
        FROM pg_policies p
        WHERE p.schemaname = 'public'
          AND p.tablename = expected.tablename
          AND p.policyname = expected.policyname;
        IF NOT FOUND THEN
            RAISE EXCEPTION 'NEXORA_CATALOG_ASSERTION: CAT-POLICY-MISSING:%',
                expected.assertion_id;
        END IF;
        IF actual_policy.cmd <> expected.command
           OR actual_policy.permissive <> 'PERMISSIVE'
           OR actual_policy.roles <> ARRAY['authenticated']::name[] THEN
            RAISE EXCEPTION 'NEXORA_CATALOG_ASSERTION: CAT-POLICY-METADATA:%',
                expected.assertion_id;
        END IF;
        policy_expression := lower(
            coalesce(actual_policy.qual, '') || coalesce(actual_policy.with_check, '')
        );
        normalized_policy := regexp_replace(
            policy_expression,
            '[[:space:]]', '', 'g'
        );
        IF expected.tablename = 'report_history'
           AND policy_expression ~ '(^|[^a-z0-9_])or([^a-z0-9_]|$)' THEN
            RAISE EXCEPTION 'NEXORA_CATALOG_ASSERTION: CAT-POLICY-USING-PREDICATE:%',
                expected.assertion_id;
        END IF;
        IF expected.using_pattern IS NOT NULL THEN
            FOREACH function_signature IN ARRAY string_to_array(expected.using_pattern, '&')
            LOOP
                IF normalized_policy !~ substring(function_signature FROM 2) THEN
                    RAISE EXCEPTION 'NEXORA_CATALOG_ASSERTION: CAT-POLICY-USING-PREDICATE:%',
                        expected.assertion_id;
                END IF;
            END LOOP;
        END IF;
        IF expected.check_pattern IS NOT NULL THEN
            FOREACH function_signature IN ARRAY string_to_array(expected.check_pattern, '&')
            LOOP
                IF normalized_policy !~ substring(function_signature FROM 2) THEN
                    RAISE EXCEPTION 'NEXORA_CATALOG_ASSERTION: CAT-POLICY-WITH-CHECK:%',
                        expected.assertion_id;
                END IF;
            END LOOP;
        END IF;
        IF (expected.command = 'SELECT' AND actual_policy.with_check IS NOT NULL)
           OR (expected.command = 'INSERT' AND actual_policy.qual IS NOT NULL) THEN
            RAISE EXCEPTION 'NEXORA_CATALOG_ASSERTION: CAT-POLICY-CLAUSE-SHAPE:%',
                expected.assertion_id;
        END IF;
        IF expected.tablename <> 'users'
           AND position('u.auth_user_id=(selectauth.uid()' IN normalized_policy) = 0 THEN
            RAISE EXCEPTION 'NEXORA_CATALOG_ASSERTION: CAT-AUTH-UUID-BINDING:%',
                expected.assertion_id;
        END IF;
    END LOOP;
    IF EXISTS (
        SELECT 1
        FROM pg_policies p
        WHERE p.schemaname = 'public'
          AND p.tablename IN (
              'users', 'organizations', 'clients', 'recommendations',
              'report_history', 'cloud_cost_import', 'cloud_cost_import_part',
              'cloud_account_mapping', 'cloud_cost_reconciliation'
          )
          AND NOT (
              (p.tablename, p.policyname) IN (
                  ('users', 'users_select_self'),
                  ('organizations', 'organizations_select_own'),
                  ('clients', 'clients_select_own_org'),
                  ('recommendations', 'recommendations_select_own_org'),
                  ('recommendations', 'recommendations_insert_own_org'),
                  ('report_history', 'report_history_select_own_org'),
                  ('report_history', 'report_history_insert_own_org'),
                  ('cloud_cost_import', 'cloud_cost_import_select_own_org'),
                  ('cloud_cost_import_part', 'cloud_cost_import_part_select_own_org'),
                  ('cloud_account_mapping', 'cloud_account_mapping_select_own_org'),
                  ('cloud_cost_reconciliation', 'cloud_cost_reconciliation_select_own_org')
              )
          )
    ) THEN
        RAISE EXCEPTION 'NEXORA_CATALOG_ASSERTION: CAT-UNEXPECTED-POLICY';
    END IF;

    IF EXISTS (
        SELECT 1 FROM pg_policies p
        WHERE p.schemaname = 'public'
          AND p.tablename IN (
              'users', 'organizations', 'clients', 'recommendations',
              'report_history', 'cloud_cost_import', 'cloud_cost_import_part',
              'cloud_account_mapping', 'cloud_cost_reconciliation'
          )
          AND (coalesce(p.qual, '') || ' ' || coalesce(p.with_check, ''))
              ILIKE '%email%'
    ) THEN
        RAISE EXCEPTION 'NEXORA_CATALOG_ASSERTION: CAT-LEGACY-EMAIL-POLICY';
    END IF;

    FOREACH function_signature IN ARRAY ARRAY[
        'public.pvt003c1_can_read_organization(uuid)',
        'public.fg002_resolve_cloud_account(uuid,text,text,jsonb,text,boolean,text)',
        'public.fg002_bulk_resolve_cloud_accounts(uuid,jsonb,jsonb,text,boolean)'
    ]
    LOOP
        function_oid := to_regprocedure(function_signature);
        IF function_oid IS NULL THEN
            RAISE EXCEPTION 'NEXORA_CATALOG_ASSERTION: CAT-FUNCTION-MISSING';
        END IF;
        IF NOT EXISTS (
            SELECT 1 FROM pg_proc p
            WHERE p.oid = function_oid AND p.prosecdef
              AND p.proconfig @> ARRAY['search_path=pg_catalog, public']
        ) THEN
            RAISE EXCEPTION 'NEXORA_CATALOG_ASSERTION: CAT-SECURITY-DEFINER-SEARCH-PATH';
        END IF;
        IF EXISTS (
            SELECT 1
            FROM pg_proc p
            CROSS JOIN LATERAL aclexplode(
                coalesce(p.proacl, acldefault('f', p.proowner))
            ) acl
            WHERE p.oid = function_oid
              AND acl.grantee = 0 AND acl.privilege_type = 'EXECUTE'
        ) OR has_function_privilege('anon', function_oid, 'EXECUTE') THEN
            RAISE EXCEPTION 'NEXORA_CATALOG_ASSERTION: CAT-FUNCTION-PUBLIC-EXECUTE';
        END IF;
        IF NOT has_function_privilege('authenticated', function_oid, 'EXECUTE')
           OR NOT has_function_privilege('service_role', function_oid, 'EXECUTE') THEN
            RAISE EXCEPTION 'NEXORA_CATALOG_ASSERTION: CAT-FUNCTION-GRANT';
        END IF;
    END LOOP;

    IF EXISTS (
        SELECT 1 FROM pg_trigger t
        WHERE t.tgrelid = auth_users_oid AND NOT t.tgisinternal
          AND t.tgname = 'on_auth_user_created'
    ) THEN
        RAISE EXCEPTION 'NEXORA_CATALOG_ASSERTION: CAT-AUTH-TRIGGER-REMAINS';
    END IF;

    SELECT count(*) INTO actual_count
    FROM pg_constraint
    WHERE conrelid = users_oid AND contype = 'f' AND confrelid = auth_users_oid;
    IF actual_count <> 1 THEN
        RAISE EXCEPTION 'NEXORA_CATALOG_ASSERTION: CAT-AUTH-FK-COUNT';
    END IF;
END
$assert$;
"""


SYNTHETIC_TENANT_ASSERTIONS = r"""
-- These checks exercise PostgreSQL RLS with synthetic claims only; they do not
-- validate Supabase JWT signatures, PostgREST role setup, or Supabase Auth.
BEGIN;
INSERT INTO auth.users (id) VALUES
    ('a1000000-0000-4000-8000-000000000001'),
    ('b2000000-0000-4000-8000-000000000002'),
    ('c3000000-0000-4000-8000-000000000003');
INSERT INTO public.organizations (id, name) VALUES
    ('a1000000-0000-4000-8000-000000000011', 'Synthetic Tenant A'),
    ('b2000000-0000-4000-8000-000000000022', 'Synthetic Tenant B');
INSERT INTO public.cloud_cost_tenant_scope (organization_id, tenant_id) VALUES
    ('a1000000-0000-4000-8000-000000000011', 'a1000000-0000-4000-8000-000000000011'),
    ('b2000000-0000-4000-8000-000000000022', 'b2000000-0000-4000-8000-000000000022');
INSERT INTO public.users (id, email, name, role, org_id, auth_user_id) VALUES
    ('a1000000-0000-4000-8000-000000000101', 'user-a@example.invalid',
     'Synthetic User A', 'finance', 'a1000000-0000-4000-8000-000000000011',
     'a1000000-0000-4000-8000-000000000001'),
    ('b2000000-0000-4000-8000-000000000202', 'user-b@example.invalid',
     'Synthetic User B', 'finance', 'b2000000-0000-4000-8000-000000000022',
     'b2000000-0000-4000-8000-000000000002'),
    ('c3000000-0000-4000-8000-000000000303', 'unbound@example.invalid',
     'Synthetic Unbound User', 'finance', 'a1000000-0000-4000-8000-000000000011',
     NULL);
INSERT INTO public.recommendations (id, org_id, service, description, status) VALUES
    ('a1000000-0000-4000-8000-000000000111',
     'a1000000-0000-4000-8000-000000000011',
     'synthetic', 'Synthetic A record', 'pending'),
    ('b2000000-0000-4000-8000-000000000222',
     'b2000000-0000-4000-8000-000000000022',
     'synthetic', 'Synthetic B record', 'pending');
INSERT INTO public.clients (id, name, org_id) VALUES
    ('a1000000-0000-4000-8000-000000000121', 'Synthetic A client',
     'a1000000-0000-4000-8000-000000000011'),
    ('b2000000-0000-4000-8000-000000000232', 'Synthetic B client',
     'b2000000-0000-4000-8000-000000000022');
INSERT INTO public.report_history (id, org_id, tenant_id, report_name) VALUES
    ('a1000000-0000-4000-8000-000000000131',
     'a1000000-0000-4000-8000-000000000011',
     'a1000000-0000-4000-8000-000000000011', 'Synthetic A report'),
    ('b2000000-0000-4000-8000-000000000242',
     'b2000000-0000-4000-8000-000000000022',
     'b2000000-0000-4000-8000-000000000022', 'Synthetic B report');
INSERT INTO public.cloud_cost_import (
    import_id, organization_id, tenant_id, import_key, payer_account_id,
    billing_period_start, billing_period_end, source_file_name, source_file_sha256,
    compression, parser_profile, status
) VALUES
    ('a1000000-0000-4000-8000-000000000141',
     'a1000000-0000-4000-8000-000000000011',
     'a1000000-0000-4000-8000-000000000011', 'synthetic-a', 'payer-a',
     '2026-01-01', '2026-01-31', 'synthetic-a.csv', repeat('a', 64),
     'csv', 'synthetic', 'received'),
    ('b2000000-0000-4000-8000-000000000252',
     'b2000000-0000-4000-8000-000000000022',
     'b2000000-0000-4000-8000-000000000022', 'synthetic-b', 'payer-b',
     '2026-01-01', '2026-01-31', 'synthetic-b.csv', repeat('b', 64),
     'csv', 'synthetic', 'received');
INSERT INTO public.cloud_cost_import_part (
    import_part_id, organization_id, tenant_id, import_id, part_key,
    part_name, part_sha256, row_start, status
) VALUES
    ('a1000000-0000-4000-8000-000000000151',
     'a1000000-0000-4000-8000-000000000011',
     'a1000000-0000-4000-8000-000000000011',
     'a1000000-0000-4000-8000-000000000141', 'part-a', 'part-a.csv',
     repeat('c', 64), 1, 'pending'),
    ('b2000000-0000-4000-8000-000000000262',
     'b2000000-0000-4000-8000-000000000022',
     'b2000000-0000-4000-8000-000000000022',
     'b2000000-0000-4000-8000-000000000252', 'part-b', 'part-b.csv',
     repeat('d', 64), 1, 'pending');
INSERT INTO public.cloud_account_mapping (
    cloud_account_mapping_id, organization_id, tenant_id, provider,
    payer_account_id, account_id, account_kind, status, effective_from,
    mapping_source
) VALUES
    ('a1000000-0000-4000-8000-000000000161',
     'a1000000-0000-4000-8000-000000000011',
     'a1000000-0000-4000-8000-000000000011', 'aws', 'payer-a', 'account-a',
     'payer', 'active', '2026-01-01', 'synthetic'),
    ('b2000000-0000-4000-8000-000000000272',
     'b2000000-0000-4000-8000-000000000022',
     'b2000000-0000-4000-8000-000000000022', 'aws', 'payer-b', 'account-b',
     'payer', 'active', '2026-01-01', 'synthetic');
INSERT INTO public.cloud_cost_reconciliation (
    cloud_cost_reconciliation_id, organization_id, tenant_id, import_id,
    billing_period_start, billing_period_end, payer_account_id,
    source_row_count, normalized_row_count, rejected_row_count,
    duplicate_row_count, status
) VALUES
    ('a1000000-0000-4000-8000-000000000171',
     'a1000000-0000-4000-8000-000000000011',
     'a1000000-0000-4000-8000-000000000011',
     'a1000000-0000-4000-8000-000000000141',
     '2026-01-01', '2026-01-31', 'payer-a', 1, 1, 0, 0, 'pending'),
    ('b2000000-0000-4000-8000-000000000282',
     'b2000000-0000-4000-8000-000000000022',
     'b2000000-0000-4000-8000-000000000022',
     'b2000000-0000-4000-8000-000000000252',
     '2026-01-01', '2026-01-31', 'payer-b', 1, 1, 0, 0, 'pending');

SET LOCAL ROLE authenticated;
DO $assert$
DECLARE
    contract record;
    principal record;
    visible_count integer;
BEGIN
    FOR principal IN
        SELECT * FROM (VALUES
            ('{"sub":"a1000000-0000-4000-8000-000000000001","role":"authenticated"}', 'A'),
            ('{"sub":"b2000000-0000-4000-8000-000000000002","role":"authenticated"}', 'B'),
            ('{"sub":"c3000000-0000-4000-8000-000000000003","role":"authenticated"}', 'UNBOUND'),
            ('{"role":"authenticated"}', 'MISSING')
        ) AS principals(claims, principal_name)
    LOOP
        PERFORM set_config('request.jwt.claims', principal.claims, true);
        FOR contract IN
            SELECT * FROM (VALUES
                ('public.users', 'id',
                 'a1000000-0000-4000-8000-000000000101',
                 'b2000000-0000-4000-8000-000000000202'),
                ('public.organizations', 'id',
                 'a1000000-0000-4000-8000-000000000011',
                 'b2000000-0000-4000-8000-000000000022'),
                ('public.clients', 'id',
                 'a1000000-0000-4000-8000-000000000121',
                 'b2000000-0000-4000-8000-000000000232'),
                ('public.recommendations', 'id',
                 'a1000000-0000-4000-8000-000000000111',
                 'b2000000-0000-4000-8000-000000000222'),
                ('public.report_history', 'id',
                 'a1000000-0000-4000-8000-000000000131',
                 'b2000000-0000-4000-8000-000000000242'),
                ('public.cloud_cost_import', 'import_id',
                 'a1000000-0000-4000-8000-000000000141',
                 'b2000000-0000-4000-8000-000000000252'),
                ('public.cloud_cost_import_part', 'import_part_id',
                 'a1000000-0000-4000-8000-000000000151',
                 'b2000000-0000-4000-8000-000000000262'),
                ('public.cloud_account_mapping', 'cloud_account_mapping_id',
                 'a1000000-0000-4000-8000-000000000161',
                 'b2000000-0000-4000-8000-000000000272'),
                ('public.cloud_cost_reconciliation', 'cloud_cost_reconciliation_id',
                 'a1000000-0000-4000-8000-000000000171',
                 'b2000000-0000-4000-8000-000000000282')
            ) AS tenant_contract(tablename, id_column, tenant_a_id, tenant_b_id)
        LOOP
            IF principal.principal_name = 'A' THEN
                EXECUTE format(
                    'SELECT count(*) FROM %s WHERE %I::text = %L',
                    contract.tablename, contract.id_column, contract.tenant_a_id
                ) INTO visible_count;
                IF visible_count <> 1 THEN
                    RAISE EXCEPTION 'Tenant A cannot read own row in %', contract.tablename;
                END IF;
                EXECUTE format(
                    'SELECT count(*) FROM %s WHERE %I::text = %L',
                    contract.tablename, contract.id_column, contract.tenant_b_id
                ) INTO visible_count;
                IF visible_count <> 0 THEN
                    RAISE EXCEPTION 'Tenant A read Tenant B row in %', contract.tablename;
                END IF;
            ELSIF principal.principal_name = 'B' THEN
                EXECUTE format(
                    'SELECT count(*) FROM %s WHERE %I::text = %L',
                    contract.tablename, contract.id_column, contract.tenant_b_id
                ) INTO visible_count;
                IF visible_count <> 1 THEN
                    RAISE EXCEPTION 'Tenant B cannot read own row in %', contract.tablename;
                END IF;
                EXECUTE format(
                    'SELECT count(*) FROM %s WHERE %I::text = %L',
                    contract.tablename, contract.id_column, contract.tenant_a_id
                ) INTO visible_count;
                IF visible_count <> 0 THEN
                    RAISE EXCEPTION 'Tenant B read Tenant A row in %', contract.tablename;
                END IF;
            ELSE
                EXECUTE format(
                    'SELECT count(*) FROM %s WHERE %I::text IN (%L, %L)',
                    contract.tablename, contract.id_column,
                    contract.tenant_a_id, contract.tenant_b_id
                ) INTO visible_count;
                IF visible_count <> 0 THEN
                    RAISE EXCEPTION '% principal saw tenant rows in %',
                        principal.principal_name, contract.tablename;
                END IF;
            END IF;
            IF principal.principal_name IN ('A', 'B')
               AND contract.tablename = 'public.users' THEN
                SELECT count(*) INTO visible_count
                FROM public.users
                WHERE id = 'c3000000-0000-4000-8000-000000000303';
                IF visible_count <> 0 THEN
                    RAISE EXCEPTION 'Tenant principal saw an unbound profile';
                END IF;
            END IF;
        END LOOP;
    END LOOP;

    PERFORM set_config(
        'request.jwt.claims',
        '{"sub":"a1000000-0000-4000-8000-000000000001","role":"authenticated"}',
        true
    );
    BEGIN
        INSERT INTO public.recommendations (org_id, service, description, status)
        VALUES (
            'b2000000-0000-4000-8000-000000000022',
            'synthetic', 'Forbidden synthetic write', 'pending'
        );
        RAISE EXCEPTION 'Tenant A wrote a Tenant B recommendation';
    EXCEPTION WHEN insufficient_privilege THEN
        NULL;
    END;
    INSERT INTO public.recommendations (org_id, service, description, status)
    VALUES (
        'a1000000-0000-4000-8000-000000000011',
        'synthetic', 'Allowed synthetic write', 'pending'
    );
    BEGIN
        INSERT INTO public.report_history (id, org_id, tenant_id, report_name)
        VALUES (
            'a1000000-0000-4000-8000-000000000191',
            'b2000000-0000-4000-8000-000000000022',
            'b2000000-0000-4000-8000-000000000022',
            'Forbidden synthetic report'
        );
        RAISE EXCEPTION 'Tenant A wrote a Tenant B report';
    EXCEPTION WHEN insufficient_privilege THEN
        NULL;
    END;
    INSERT INTO public.report_history (id, org_id, tenant_id, report_name)
    VALUES (
        'a1000000-0000-4000-8000-000000000181',
        'a1000000-0000-4000-8000-000000000011',
        'a1000000-0000-4000-8000-000000000011',
        'Allowed synthetic report'
    );
END
$assert$;
ROLLBACK;
"""


def normalized_sql_sha256(path: Path) -> str:
    try:
        text = path.read_bytes().decode("utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise ReplayError(f"cannot read migration input: {path.name}") from exc
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def load_manifest(root: Path) -> dict:
    try:
        return json.loads((root / MANIFEST_PATH).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ReplayError("migration manifest is missing or invalid JSON") from exc


def _expected_public_paths(root: Path) -> list[str]:
    return sorted(
        f"supabase/migrations/{path.name}"
        for path in (root / "supabase/migrations").glob("*.sql")
        if path.is_file()
    )


def _expected_data_fabric_paths(root: Path) -> list[str]:
    paths = sorted(
        f"migrations/data_fabric/{path.name}"
        for path in (root / "migrations/data_fabric").glob("*.sql")
        if path.is_file()
    )
    expected_names = [f"{number:04d}_" for number in range(1, 24)]
    if [Path(path).name[:5] for path in paths] != expected_names:
        raise ReplayError("Data Fabric migration files are not exactly ordered 0001-0023")
    return paths


def validate_manifest(root: Path, manifest: dict | None = None) -> list[str]:
    manifest = manifest if manifest is not None else load_manifest(root)
    if not isinstance(manifest, dict):
        raise ReplayError("migration manifest root must be a JSON object")
    contract = manifest.get("contract", {})
    if not isinstance(contract, dict):
        raise ReplayError("migration manifest contract is malformed")
    if (
        manifest.get("status") != "BLOCKED"
        or manifest.get("executable") is not False
        or contract.get("status") != "BLOCKED"
        or contract.get("postgres_replay")
        != "PASS_TEST_ONLY_LOCAL_NETWORK_DISABLED"
    ):
        raise ReplayError(
            "manifest must remain BLOCKED with test-only replay evidence"
        )

    steps = manifest.get("steps")
    if not isinstance(steps, list) or len(steps) != len(MANIFEST_STEP_NAMES):
        raise ReplayError("manifest step inventory is not the expected six-step chain")
    if not all(isinstance(step, dict) for step in steps):
        raise ReplayError("manifest migration steps are malformed")
    if tuple(step.get("name") for step in steps) != MANIFEST_STEP_NAMES:
        raise ReplayError("manifest contains unexpected or additional PostgreSQL steps")
    if [step.get("order") for step in steps] != list(range(1, len(steps) + 1)):
        raise ReplayError("manifest step ordering metadata is invalid")
    if steps[0].get("name") != "public_bootstrap":
        raise ReplayError("public bootstrap must be the first PostgreSQL input")
    if steps[0].get("path") != "supabase/bootstrap/public_prerequisites.sql":
        raise ReplayError("unexpected public bootstrap path")
    if steps[1].get("name") != PUBLIC_STEP or steps[2].get("name") != DATA_FABRIC_STEP:
        raise ReplayError("PostgreSQL migration step order is invalid")
    if any(step.get("engine", "postgres") != "postgres" for step in steps[:3]):
        raise ReplayError("PostgreSQL step engine metadata is invalid")
    if any(step.get("engine") != "sqlite" for step in steps[3:]):
        raise ReplayError("non-PostgreSQL manifest steps must remain explicitly SQLite")
    if steps[0].get("status") != "SCHEMA_ONLY_CURRENT_CHAIN_PREREQUISITES":
        raise ReplayError("public bootstrap status metadata is invalid")
    if any("path" in step for step in steps[1:3]):
        raise ReplayError("migration list steps must use their files arrays")

    expected_public = _expected_public_paths(root)
    expected_fabric = _expected_data_fabric_paths(root)
    if len(expected_public) != 19:
        raise ReplayError("expected exactly 19 current public migrations")
    public_entries = steps[1].get("files")
    fabric_entries = steps[2].get("files")
    if not isinstance(public_entries, list) or not isinstance(fabric_entries, list):
        raise ReplayError("manifest migration file lists are malformed")
    if not all(isinstance(item, dict) for item in [*public_entries, *fabric_entries]):
        raise ReplayError("manifest migration entries are malformed")
    public_paths = [item.get("path") for item in public_entries]
    fabric_paths = [item.get("path") for item in fabric_entries]
    if public_paths != expected_public or public_paths != sorted(public_paths):
        raise ReplayError("public migration path inventory or order mismatch")
    if fabric_paths != expected_fabric:
        raise ReplayError("Data Fabric migration path inventory or order mismatch")

    entries = [
        {"path": steps[0]["path"], "sha256": steps[0].get("sha256")},
        *public_entries,
        *fabric_entries,
    ]
    paths = [entry["path"] for entry in entries]
    if len(paths) != 43 or len(set(paths)) != 43:
        raise ReplayError("manifest must contain exactly 43 unique PostgreSQL inputs")

    resolved_root = root.resolve()
    for entry in entries:
        relative = entry.get("path")
        expected_hash = entry.get("sha256")
        if not isinstance(relative, str) or not re.fullmatch(r"[0-9a-f]{64}", str(expected_hash)):
            raise ReplayError("manifest path or SHA-256 digest is malformed")
        source = (root / relative).resolve()
        if not source.is_relative_to(resolved_root) or not source.is_file():
            raise ReplayError(
                f"migration input is missing or escapes the repository: {Path(relative).name}"
            )
        if any(char in str(source) for char in (",", "\r", "\n")):
            raise ReplayError("migration input path is unsafe for a Docker bind mount")
        if normalized_sql_sha256(source) != expected_hash:
            raise ReplayError(f"migration hash mismatch: {Path(relative).name}")
    return paths


def validate_image_ref(image: str) -> None:
    if image != APPROVED_IMAGE:
        raise ReplayError("image must be the approved local PostgreSQL digest")


def build_container_args(root: Path, image: str, name: str, invocation_id: str) -> list[str]:
    validate_image_ref(image)
    if not re.fullmatch(rf"{re.escape(CONTAINER_PREFIX)}[0-9a-f]{{16}}", name):
        raise ReplayError("ephemeral container name is invalid")
    if not re.fullmatch(r"[0-9a-f]{32}", invocation_id):
        raise ReplayError("invocation identity is invalid")
    migration_paths = validate_manifest(root)
    args = [
        "docker",
        "run",
        "--detach",
        "--pull=never",
        "--name",
        name,
        "--label",
        f"{OWNERSHIP_LABEL}={invocation_id}",
        "--network",
        "none",
        "--read-only",
        "--user",
        "postgres",
        "--security-opt",
        "no-new-privileges",
        "--cap-drop",
        "ALL",
        "--pids-limit",
        "256",
        "--memory",
        "3g",
        "--tmpfs",
        "/var/lib/postgresql/data:rw,noexec,nosuid,nodev,size=2g,uid=999,gid=999,mode=0700",
        "--tmpfs",
        "/inputs:rw,noexec,nosuid,nodev,size=1m,uid=999,gid=999,mode=0700",
        "--tmpfs",
        "/var/run/postgresql:rw,noexec,nosuid,nodev,size=16m,uid=999,gid=999,mode=0700",
        "--tmpfs",
        "/tmp:rw,noexec,nosuid,nodev,size=64m,uid=999,gid=999,mode=1777",
        "--env",
        "POSTGRES_HOST_AUTH_METHOD=trust",
        "--env",
        "POSTGRES_USER=postgres",
        "--env",
        "POSTGRES_DB=postgres",
    ]
    target_names = [Path(path).name for path in migration_paths]
    if len(target_names) != len(set(target_names)) or AUTH_FIXTURE.name in target_names:
        raise ReplayError("migration basenames are not unique for isolated input mounts")
    for path in migration_paths:
        source = (root / path).resolve()
        args.extend(
            [
                "--mount",
                f"type=bind,source={source},target=/inputs/{Path(path).name},readonly",
            ]
        )
    fixture = (root / AUTH_FIXTURE).resolve()
    if not fixture.is_file() or not fixture.is_relative_to(root.resolve()):
        raise ReplayError("test-only Auth fixture is missing or outside the repository")
    if any(char in str(fixture) for char in (",", "\r", "\n")):
        raise ReplayError("Auth fixture path is unsafe for a Docker bind mount")
    args.extend(
        [
            "--mount",
            f"type=bind,source={fixture},target=/inputs/{AUTH_FIXTURE.name},readonly",
            image,
        ]
    )
    return args


def validate_container_configuration(args: Sequence[str]) -> None:
    if (
        "--pull=never" not in args
        or "--read-only" not in args
        or "--network" not in args
        or args[args.index("--network") + 1] != "none"
        or "--privileged" in args
        or "--publish" in args
        or "-p" in args
        or "--volume" in args
        or "-v" in args
        or "--read-write" in args
        or args[-1] != APPROVED_IMAGE
    ):
        raise ReplayError("container runtime configuration is unsafe")
    tmpfs_paths = [
        args[index + 1].split(":", 1)[0]
        for index, value in enumerate(args[:-1])
        if value == "--tmpfs"
    ]
    if not {
        "/var/lib/postgresql/data",
        "/var/run/postgresql",
        "/tmp",
    }.issubset(tmpfs_paths):
        raise ReplayError("container temporary storage configuration is incomplete")
    for index, value in enumerate(args[:-1]):
        if value == "--mount":
            mount = args[index + 1]
            if not mount.startswith("type=bind,") or not mount.endswith(",readonly"):
                raise ReplayError("container input mount configuration is unsafe")


class ReplayHarness:
    def __init__(
        self,
        root: Path = ROOT,
        *,
        runner: Runner | None = None,
        name_factory: Callable[[], str] | None = None,
        identity_factory: Callable[[], str] | None = None,
        sleeper: Callable[[float], None] = time.sleep,
        environment: Mapping[str, str] | None = None,
    ) -> None:
        self.root = root.resolve()
        self.runner = runner or subprocess.run
        self.name_factory = name_factory or (lambda: CONTAINER_PREFIX + uuid.uuid4().hex[:16])
        self.identity_factory = identity_factory or (lambda: uuid.uuid4().hex)
        self.sleeper = sleeper
        self.environment = dict(os.environ if environment is None else environment)
        self.docker_environment = {
            key: value
            for key, value in self.environment.items()
            if not key.upper().startswith("DOCKER_")
        }
        self.docker_context: str | None = None
        self.docker_host: str | None = None

    def _run_process(
        self, args: Sequence[str], stage: str, *, timeout: int
    ) -> subprocess.CompletedProcess[str]:
        try:
            result = self.runner(
                list(args),
                cwd=self.root,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
                env=self.docker_environment,
            )
        except subprocess.TimeoutExpired as exc:
            raise DockerCommandTimeout(f"{stage} timed out") from exc
        except OSError as exc:
            raise ReplayError(f"{stage} could not start the local Docker CLI") from exc
        return result

    def _check_endpoint_overrides(self) -> None:
        configured = {key.upper() for key in self.environment}
        if configured.intersection(DOCKER_ENDPOINT_ENV):
            raise ReplayError("Docker endpoint override is configured; refusing replay")

    @staticmethod
    def _validate_local_endpoint(host: str) -> None:
        if not host or any(char in host for char in "\r\n\t"):
            raise ReplayError("Docker endpoint is missing or ambiguous")
        parsed = urlsplit(host)
        if parsed.scheme == "unix":
            if parsed.netloc or not parsed.path.startswith("/") or parsed.query or parsed.fragment:
                raise ReplayError("Docker endpoint is not a verified local socket")
            return
        if host.startswith("npipe://"):
            if (
                parsed.netloc
                or not re.fullmatch(r"//\./pipe/[A-Za-z0-9_.-]+", parsed.path)
                or parsed.query
                or parsed.fragment
            ):
                raise ReplayError("Docker endpoint is not a verified local named pipe")
            return
        raise ReplayError("Docker endpoint is remote-capable or unsupported")

    def _read_context_host(self, context: str) -> str:
        result = self._run_process(
            [
                "docker",
                "context",
                "inspect",
                context,
                "--format",
                "{{json .Endpoints.docker.Host}}",
            ],
            "Docker context verification",
            timeout=20,
        )
        if result.returncode != 0:
            raise ReplayError("Docker context could not be verified")
        try:
            host = json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            raise ReplayError("Docker context endpoint metadata is invalid") from exc
        if not isinstance(host, str):
            raise ReplayError("Docker context endpoint metadata is ambiguous")
        self._validate_local_endpoint(host)
        return host

    def _verify_local_endpoint(self) -> None:
        self._check_endpoint_overrides()
        if self.docker_context is None:
            result = self._run_process(
                ["docker", "context", "show"],
                "Docker context discovery",
                timeout=20,
            )
            if result.returncode != 0:
                raise ReplayError("active Docker context could not be verified")
            context = result.stdout.strip()
            if not context or not re.fullmatch(r"[A-Za-z0-9_.-]+", context):
                raise ReplayError("active Docker context name is invalid")
            self.docker_context = context
            self.docker_host = self._read_context_host(context)
            return

        if self.docker_host is None:
            raise ReplayError("validated Docker endpoint state is incomplete")
        current_host = self._read_context_host(self.docker_context)
        if current_host != self.docker_host:
            raise ReplayError("Docker endpoint changed after local verification")

    def assert_name_available(self, name: str) -> None:
        result = self.invoke(
            ["ps", "-a", "--format", "{{.Names}}"],
            "container-name collision check",
        )
        if name in result.stdout.splitlines():
            raise ReplayError("ephemeral container name already exists")

    def docker_result(
        self, args: Sequence[str], stage: str, *, timeout: int = MAX_SQL_TIMEOUT_SECONDS
    ) -> subprocess.CompletedProcess[str]:
        self._verify_local_endpoint()
        if self.docker_host is None:
            raise ReplayError("local Docker endpoint was not established")
        return self._run_process(
            ["docker", "--host", self.docker_host, *args],
            stage,
            timeout=timeout,
        )

    def invoke(
        self, args: Sequence[str], stage: str, *, timeout: int = MAX_SQL_TIMEOUT_SECONDS
    ) -> subprocess.CompletedProcess[str]:
        result = self.docker_result(args, stage, timeout=timeout)
        if result.returncode != 0:
            assertion_detail = ""
            if stage == "catalog assertions":
                match = re.search(
                    r"\bNEXORA_CATALOG_ASSERTION:\s*(CAT-[A-Z0-9-]+(?::[a-z0-9_.]+)?)\b",
                    result.stderr,
                )
                if match and match.group(1) in CATALOG_ASSERTION_IDS:
                    assertion_detail = f"; assertion={match.group(1)}"
            raise ReplayError(f"{stage} failed (exit {result.returncode}{assertion_detail})")
        return result

    def assert_local_image(self, image: str) -> None:
        validate_image_ref(image)
        result = self.invoke(
            ["image", "inspect", image, "--format", "{{json .RepoDigests}}"],
            "local PostgreSQL image inspection",
            timeout=30,
        )
        try:
            digests = json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            raise ReplayError("local PostgreSQL image metadata is invalid") from exc
        if not isinstance(digests, list) or image not in digests:
            raise ReplayError("approved PostgreSQL image digest is not available locally")

    def _exec_psql_file(self, container: str, path: str, stage: str) -> None:
        self.invoke(
            [
                "exec",
                container,
                "psql",
                "--no-psqlrc",
                "--set",
                "ON_ERROR_STOP=1",
                "--username",
                "postgres",
                "--dbname",
                "postgres",
                "--file",
                path,
            ],
            stage,
        )

    def _exec_psql_sql(self, container: str, sql: str, stage: str) -> None:
        self.invoke(
            [
                "exec",
                container,
                "psql",
                "--no-psqlrc",
                "--set",
                "ON_ERROR_STOP=1",
                "--username",
                "postgres",
                "--dbname",
                "postgres",
                "--command",
                sql,
            ],
            stage,
        )

    def _wait_until_ready(self, container: str) -> None:
        deadline = time.monotonic() + CONTAINER_READY_TIMEOUT_SECONDS
        command = ["exec", container, "pg_isready", "--username", "postgres"]
        while time.monotonic() < deadline:
            try:
                result = self.docker_result(command, "PostgreSQL readiness check", timeout=5)
            except DockerCommandTimeout:
                result = None
            if result is not None and result.returncode == 0:
                return
            self.sleeper(1)
        raise ReplayError("isolated PostgreSQL did not become ready")

    def _inspect_owned_container(self, container_id: str, name: str, invocation_id: str) -> bool:
        if not re.fullmatch(r"[0-9a-f]{64}", container_id):
            return False
        result = self.invoke(
            [
                "inspect",
                "--format",
                f'{{{{.Id}}}}|{{{{.Name}}}}|{{{{index .Config.Labels "{OWNERSHIP_LABEL}"}}}}',
                container_id,
            ],
            "container ownership verification",
        )
        fields = result.stdout.strip().split("|")
        return (
            len(fields) == 3
            and fields[0] == container_id
            and fields[1].removeprefix("/") == name
            and fields[2] == invocation_id
        )

    def _find_owned_container(self, name: str, invocation_id: str) -> str | None:
        result = self.invoke(
            [
                "ps",
                "-a",
                "--no-trunc",
                "--filter",
                f"label={OWNERSHIP_LABEL}={invocation_id}",
                "--format",
                f'{{{{.ID}}}}|{{{{.Names}}}}|{{{{.Label "{OWNERSHIP_LABEL}"}}}}',
            ],
            "startup ownership reconciliation",
        )
        matches: list[str] = []
        rows = [line for line in result.stdout.splitlines() if line]
        for row in rows:
            fields = row.split("|")
            if (
                len(fields) != 3
                or fields[1] != name
                or fields[2] != invocation_id
                or not re.fullmatch(r"[0-9a-f]{64}", fields[0])
            ):
                raise ReplayError("startup ownership is ambiguous; manual reconciliation required")
            matches.append(fields[0])
        if len(matches) > 1:
            raise ReplayError("multiple matching containers found; manual reconciliation required")
        if not matches:
            return None
        if not self._inspect_owned_container(matches[0], name, invocation_id):
            raise ReplayError(
                "container ownership could not be verified; manual reconciliation required"
            )
        return matches[0]

    def _remove_owned_container(self, container_id: str, name: str, invocation_id: str) -> None:
        if not self._inspect_owned_container(container_id, name, invocation_id):
            raise ReplayError("refusing cleanup without verified invocation ownership")
        try:
            self.invoke(["rm", "--force", container_id], "owned-container cleanup")
        except ReplayError as exc:
            raise ReplayError(
                "owned-container cleanup failed; manual reconciliation required"
            ) from exc

    def cleanup(self, container_id: str, *, name: str, invocation_id: str) -> None:
        self._remove_owned_container(container_id, name, invocation_id)

    def _reconcile_uncertain_start(self, name: str, invocation_id: str) -> None:
        try:
            container_id = self._find_owned_container(name, invocation_id)
            if container_id is not None:
                self._remove_owned_container(container_id, name, invocation_id)
        except ReplayError as exc:
            raise ReplayError(
                "startup outcome is uncertain; manual reconciliation required; "
                "no unverified container was removed"
            ) from exc

    def run(self, image: str, *, authorize_test_only: bool) -> None:
        if not authorize_test_only:
            raise ReplayError("explicit test-only authorization is required")
        validate_image_ref(image)
        migration_paths = validate_manifest(self.root)
        name = self.name_factory()
        invocation_id = self.identity_factory()
        if not re.fullmatch(rf"{re.escape(CONTAINER_PREFIX)}[0-9a-f]{{16}}", name):
            raise ReplayError("ephemeral container name generator returned an invalid name")
        if not re.fullmatch(r"[0-9a-f]{32}", invocation_id):
            raise ReplayError("invocation identity generator returned an invalid identity")

        self.assert_local_image(image)
        self.assert_name_available(name)
        container_args = build_container_args(self.root, image, name, invocation_id)
        validate_container_configuration(container_args)
        try:
            result = self.invoke(
                container_args[1:],
                "container startup",
                timeout=CONTAINER_START_TIMEOUT_SECONDS,
            )
        except (ReplayError, KeyboardInterrupt) as exc:
            self._reconcile_uncertain_start(name, invocation_id)
            if isinstance(exc, KeyboardInterrupt):
                raise
            raise ReplayError("container startup failed; invocation ownership reconciled") from exc

        container_id = result.stdout.strip()
        if not re.fullmatch(r"[0-9a-f]{64}", container_id):
            self._reconcile_uncertain_start(name, invocation_id)
            raise ReplayError("Docker returned no valid container ID; startup reconciled")
        if not self._inspect_owned_container(container_id, name, invocation_id):
            raise ReplayError(
                "Docker returned a container without verified invocation ownership; "
                "manual reconciliation required"
            )
        try:
            self._wait_until_ready(container_id)
            self._exec_psql_file(
                container_id,
                f"/inputs/{AUTH_FIXTURE.name}",
                "test-only Auth fixture",
            )
            for index, path in enumerate(migration_paths, start=1):
                self._exec_psql_file(
                    container_id,
                    f"/inputs/{Path(path).name}",
                    f"migration {index}/43",
                )
            self._exec_psql_sql(container_id, CATALOG_ASSERTIONS, "catalog assertions")
            self._exec_psql_sql(
                container_id, SYNTHETIC_TENANT_ASSERTIONS, "synthetic tenant assertions"
            )
        finally:
            self.cleanup(container_id, name=name, invocation_id=invocation_id)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--authorize-test-only",
        action="store_true",
        help="explicitly authorize a disposable, local test-only replay",
    )
    parser.add_argument(
        "--image",
        required=True,
        help="approved locally cached PostgreSQL image pinned by digest",
    )
    args = parser.parse_args(argv)
    try:
        ReplayHarness().run(args.image, authorize_test_only=args.authorize_test_only)
    except ReplayError as exc:
        print(f"Replay stopped safely: {exc}")
        return 2
    print("Isolated test-only replay completed; this is not production or Supabase certification.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
