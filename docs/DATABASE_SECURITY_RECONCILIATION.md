# Nexora Database Security Reconciliation

Status: Repository reconciliation ready for review; not applied

Environment reconciled: `AI-Cloud-Advisor-Dev`

Date: 2026-07-23

## Safety Boundary

This work inspected repository artifacts only. It did not connect to DEV or
Production, execute SQL, apply a migration, modify a database object, change
organization identity semantics, convert identifier types, weaken RLS, or
expose a service-role credential.

The proposed migration is:

`supabase/migrations/202607230001_public_security_reconciliation.sql`

It must not be applied until it receives database/security review and a
separate deployment authorization.

## Confirmed Authentication and Tenant Chain

```text
Authentication
    ↓
Supabase JWT
    ↓
JWT email
    ↓
public.users.email
    ↓
public.users.org_id
    ↓
Tenant RLS
    ↓
Tenant-owned public records
```

The tenant policies resolve the authenticated JWT email against
`public.users.email`. The resulting `public.users.org_id` is the tenant
authority. JWT `tenant_id` and `org_id` claims are not accepted as independent
tenant authority by the reconciled policies.

`users_select_self` is the bootstrap boundary for this chain: an authenticated
user may select only the `public.users` record whose email matches the JWT
email.

## Service Role

`service_role` is a backend-only Supabase credential that bypasses RLS. Nexora
uses it for trusted scheduler and backend workflows, including recommendation
upserts and report-history persistence. It must:

- be held only in server-side secret storage;
- never be embedded in browser JavaScript, Streamlit client state, generated
  downloads, logs, screenshots, or public environment files;
- never be sent to a client as an authorization token;
- remain distinct from the anon and authenticated roles;
- be rotated through the approved secret-management process if exposure is
  suspected.

The security migration does not revoke backend CRUD or grant new service-role
access.

## Repository Audit Findings

### Active insecure-recreation path

The former `supabase/tenant_rls_policies.sql` dynamically created `FOR ALL`
policies and trusted JWT `tenant_id`/`org_id` claims directly. It could recreate
a posture different from the confirmed DEV email-to-user mapping. The script
is now fail-closed and points to the reviewed reconciliation migration.

### Historical schema backup

`backups/schema_v1.sql` contains executable insecure historical state:

- permissive `USING (true)` policies for organizations, clients, and
  recommendations at lines 1906–1926;
- anonymous recommendation insert access;
- `GRANT ALL` to `anon` and `authenticated` on clients at lines 2172–2173;
- `GRANT ALL` to `anon` and `authenticated` on recommendations at lines
  2388–2389;
- `GRANT ALL` to `anon` and `authenticated` on organizations at lines
  2454–2455;
- `GRANT ALL` to `anon` and `authenticated` on users at lines 2538–2539.

The file is a historical backup, not an approved deployment migration. Restoring
it without applying reviewed security reconciliation would recreate insecure
grants and policies.

`backup_unused/backup.sql` additionally records historical public-schema
default privileges for both `postgres` and `supabase_admin` that grant all
table privileges to `anon` and `authenticated` (lines 6319–6332). It also
records broad defaults for sequences and functions. Normal linked Supabase
migrations cannot modify `supabase_admin` default privileges: that role is
Supabase-managed/internal and is not the normal owner for Nexora application
objects. Nexora application objects must be created through normal migrations
under `postgres` ownership, whose table defaults are hardened here. Any object
unexpectedly owned or created by `supabase_admin` requires a separate ownership
and security review. Function and sequence privilege reconciliation remains a
separate review item because current requirements are not fully documented.

### Schema and bootstrap SQL

The public-schema SQL files largely create tables, indexes, functions, and seed
rows without establishing the confirmed sensitive-table RLS policies. Running
them alone does not reproduce the hardened state. The normalization/reporting
scripts preserve `report_history.org_id` and `report_history.tenant_id` as
`text`.

The Data Fabric migrations use a separate `data_fabric` schema. They enable RLS
and restrict mutation RPC execution to `service_role`; they are not the source
of the public-schema authenticated structural grants.

### Application and CI/CD

- `data/supabase_client.py` creates the trusted backend client from
  `SUPABASE_SERVICE_KEY` and aliases it as `supabase_admin`.
- Recommendation scheduler/generator paths upsert recommendations through that
  backend client.
- Backend report workflows select and insert `report_history`; the Reports page
  also updates report-generation status.
- Multiple repositories read recommendations.
- `data/queries.py` reads organizations.
- CI runs secret-free unit and structural tests. It does not provision or
  mutate a hosted public schema.
- CD builds/publishes images and optionally calls a deployment webhook. It does
  not apply Supabase migrations.

## Privilege Origin Analysis

The broad authenticated table privileges are directly evidenced by two
mechanisms:

1. **Explicit grants in the historical schema export.**
   `backups/schema_v1.sql` grants `ALL` table privileges to `authenticated` and
   `anon`. PostgreSQL expands table `ALL` to
   `SELECT, INSERT, UPDATE, DELETE, TRUNCATE, REFERENCES, TRIGGER`.
2. **Default privileges captured in the full backup.**
   `backup_unused/backup.sql` records `ALTER DEFAULT PRIVILEGES ... GRANT ALL
   ON TABLES` for both `postgres` and `supabase_admin` in `public`. Objects
   created later by either owner inherit the same broad table privilege set.
   Hosted evidence confirms Nexora's protected application tables are owned by
   `postgres`; `supabase_admin` is an internal managed role outside the
   supported linked-migration privilege boundary.

Supabase managed defaults likely established or preserved those default ACLs,
but the repository evidence is the pg_dump output, not an assumption about the
current hosted configuration.

Schema ownership is not the source of authenticated access. Public tables in
the backup are owned by `postgres`; owners inherently control their objects,
but ownership does not make `authenticated` an owner. The explicit and default
ACL grants are what conferred authenticated privileges.

RLS policies and ACL privileges are independent. A role needs the relevant
table privilege before RLS is evaluated. The permissive policies then allowed
the broadly granted operations to reach tenant data.

## CRUD Access Matrix

Classification applies to the `authenticated` application role unless the
service-role column says otherwise. `UNKNOWN` is intentionally retained where
repository evidence does not establish a safe requirement.

| Object | Application consumer | SELECT | INSERT | UPDATE | DELETE | Service-role only? | Tenant-scoped? | RLS protected? | Evidence/source |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `public.clients` | Authenticated tenant UI | REQUIRED | UNKNOWN | UNKNOWN | UNKNOWN | CRUD beyond SELECT: UNKNOWN | Yes, `org_id` | Yes | Confirmed `clients_select_own_org`; historical schema defines UUID `org_id` |
| `public.organizations` | Organization lookup | REQUIRED | UNKNOWN | UNKNOWN | UNKNOWN | Mutations: UNKNOWN | Yes, `id = users.org_id` | Yes | `data/queries.py::get_organizations`; confirmed `organizations_select_own` |
| `public.recommendations` | Dashboards, governance, cost, operations | REQUIRED | REQUIRED | UNKNOWN | UNKNOWN | Backend upsert/update: REQUIRED; client mutation beyond INSERT: UNKNOWN | Yes, `org_id` | Yes | Confirmed select/insert policies; repository SELECT consumers; scheduler/generator upsert; `data/queries.py::update_status` uses `supabase_admin` |
| `public.report_history` | Reports UI and backend reporting | REQUIRED | REQUIRED | UNKNOWN | UNKNOWN | Backend SELECT/INSERT/UPDATE: REQUIRED | Yes, text `org_id`/`tenant_id` | Yes | Confirmed select/insert policies; `backend/services/report_service.py`; `pages/reports.py` |
| `public.users` | Self lookup and tenant-resolution bootstrap | REQUIRED | UNKNOWN | UNKNOWN | UNKNOWN | Provisioning/mutations: UNKNOWN | Self by JWT email; `org_id` supplies tenant | Yes | Confirmed `users_select_self`; every tenant policy resolves through `users.email` |

Structural privileges for `anon` and `authenticated`:

| Privilege | Classification | Reason |
| --- | --- | --- |
| `TRUNCATE` | NOT REQUIRED | Destructive structural operation; no application consumer evidence |
| `REFERENCES` | NOT REQUIRED | Schema-definition capability; no runtime consumer requirement |
| `TRIGGER` | NOT REQUIRED | Trigger-definition capability; no runtime consumer requirement |

The migration deliberately does not revoke any CRUD privilege classified
`UNKNOWN`. It also does not add any CRUD grant.

## Migration Behavior

The migration is transactional and rerunnable. It:

- revokes only `TRUNCATE`, `REFERENCES`, and `TRIGGER` from `anon` and
  `authenticated` on current public tables;
- removes those structural privileges from future table defaults for
  `postgres`, the normal Nexora application-migration owner;
- does not attempt the unsupported mutation of Supabase-managed
  `supabase_admin` defaults; objects unexpectedly created by that internal role
  require separate ownership/security review;
- enables RLS on public ordinary/partitioned tables;
- removes repository-evidenced legacy permissive policies;
- recreates the seven confirmed DEV tenant policies;
- grants each policy only to `authenticated`;
- preserves `report_history` text identifiers and compares them to
  `users.org_id::text`;
- aborts if a sensitive table still exposes an anon/public or always-true
  policy;
- leaves CRUD grants unchanged.

## Security Regression Coverage

`tests/security/test_public_database_security.py` covers:

- Tenant A cannot read Tenant B clients;
- Tenant A cannot read or insert Tenant B recommendations;
- Tenant A cannot read Tenant B report history;
- a user cannot read another user's user record;
- anon is absent from protected tenant policies;
- authenticated lacks `TRUNCATE`, `REFERENCES`, and `TRIGGER`;
- future public tables do not inherit those structural privileges;
- CRUD grants are not mass-added or revoked;
- the report-history text/UUID mismatch is preserved;
- required service-role recommendation/report workflows remain present;
- the obsolete generic `FOR ALL` policy script fails closed.

These are repository-level deterministic tests. A separately authorized,
disposable DEV validation should later execute the migration and exercise
PostgREST with real anon, authenticated Tenant A/Tenant B, and service-role
tokens.

## Technical Debt and Remaining Risks

1. `report_history.org_id` and `report_history.tenant_id` are `text`, while
   `public.users.org_id` is UUID. The policies intentionally cast the UUID to
   text. Type conversion is deferred technical debt and is not part of this
   migration.
2. The backend `record_report_history` path does not always populate org/tenant
   fields in its payload. It currently relies on trusted service-role behavior.
   Application behavior was not changed in this reconciliation.
3. `config/settings.py` accepts service-role, service, generic, or anon keys
   through one fallback chain. This increases the risk of deploying a
   privileged key into a client-facing process. Separating backend and
   authenticated-client factories is recommended but would change application
   behavior and requires a separate review.
4. Historical backups remain executable and contain insecure grants/policies.
   They should be access-controlled, labeled non-deployable, and eventually
   replaced with sanitized backups under a separately approved retention
   change.
5. Function and sequence default privileges in the historical backup require a
   separate least-privilege inventory. This migration does not guess or mass
   revoke them.
6. CRUD requirements outside the five confirmed sensitive tables remain
   incomplete. They remain `UNKNOWN`.
7. Repository tests do not substitute for a real Postgres/PostgREST policy
   evaluation.

## Recommended Next Step

Review the migration and matrix, then authorize a disposable/DEV-only
validation that:

1. captures pre-migration ACLs and policies;
2. applies the migration to a disposable clone or approved DEV environment;
3. runs Tenant A/Tenant B, anon, and service-role PostgREST checks;
4. confirms required backend recommendation and report workflows;
5. verifies zero authenticated `TRUNCATE`, `REFERENCES`, and `TRIGGER` grants;
6. records rollback evidence without touching Production.
